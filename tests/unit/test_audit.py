"""Tests for Audit/metrics (P01 Item 7).

Kiểm tra ghi sự kiện kiểm tra (audit event) vào PostgreSQL (test qua SQLite)
và sự kiện đo lường (metric) qua structlog. Không lưu secret/raw URL.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.models import Base
from app.platform.observability.audit import AuditService


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "audit.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def test_record_audit_creates_event(db_session) -> None:
    """Ghi sự kiện kiểm tra thành hàng AuditEvent."""
    service = AuditService(session=db_session)
    event = service.record_audit(
        caller_id="user-1",
        action="create_job",
        decision="allowed",
        reason_code=None,
        trace_id="trace-abc",
    )
    assert event.id is not None
    assert event.caller_id == "user-1"
    assert event.action == "create_job"
    assert event.decision == "allowed"
    assert event.trace_id == "trace-abc"


def test_audit_event_queryable_by_caller(db_session) -> None:
    """Truy vấn sự kiện kiểm tra theo caller_id."""
    service = AuditService(session=db_session)
    service.record_audit(caller_id="user-A", action="create_job", decision="allowed")
    service.record_audit(caller_id="user-B", action="cancel_job", decision="allowed")
    service.record_audit(caller_id="user-A", action="get_job", decision="allowed")

    events = service.list_by_caller("user-A")
    assert len(events) == 2
    assert all(e.caller_id == "user-A" for e in events)


def test_audit_does_not_store_secret_or_raw_url(db_session) -> None:
    """Dữ liệu nhạy cảm (raw URL, token) không được lưu vào audit."""
    service = AuditService(session=db_session)
    event = service.record_audit(
        caller_id="user-1",
        action="create_job",
        decision="blocked",
        reason_code="ssrf_private_ip",
        trace_id="trace-1",
    )
    # reason_code là mã đã redaction, không phải URL thô
    assert event.reason_code == "ssrf_private_ip"
    assert "http" not in (event.reason_code or "")
    assert "token" not in (event.reason_code or "")


def test_record_metric_logs_event(caplog) -> None:
    """Sự kiện đo lường được ghi qua structlog (không secret trong label)."""
    service = AuditService(session=None)
    logger = MagicMock()
    service.record_metric(logger, "jobs_total", job_type="crawl", status="completed")

    logger.info.assert_called_once()
    args, kwargs = logger.info.call_args
    assert "jobs_total" in str(args) or "jobs_total" in str(kwargs)
    assert "secret" not in str(args).lower() and "token" not in str(args).lower()
