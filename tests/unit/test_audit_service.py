"""Audit trail service tests (P06 S03)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.models import AuditEvent, Base
from app.platform.observability.audit import AuditService


def test_audit_service_records_event_without_secret(tmp_path) -> None:
    """Ghi sự kiện kiểm soát: caller, action, decision, reason, trace_id; không lưu secret."""
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    service = AuditService(session)

    event = service.record_audit(
        caller_id="user-1",
        action="crawl.create",
        decision="allowed",
        reason_code=None,
        trace_id="trace-123",
    )

    assert event.id is not None
    assert event.caller_id == "user-1"
    assert event.action == "crawl.create"
    assert event.decision == "allowed"
    assert event.reason_code is None
    assert event.trace_id == "trace-123"
    assert event.created_at is not None

    stored = session.get(AuditEvent, event.id)
    assert stored is not None
    assert stored.decision == "allowed"
