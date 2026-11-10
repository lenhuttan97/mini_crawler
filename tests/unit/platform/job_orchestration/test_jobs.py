"""Tests for Job service (P01 Item 4).

Chạy offline trên SQLite file: tạo job, idempotency, ownership, cancel,
claim atomically. Không cần PostgreSQL/Celery thật.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.platform.job_orchestration.service import JobNotFound, JobOwnershipError, JobService
from app.platform.network_policy.policy import PolicyDecision, PolicyGate
from app.platform.persistence.models import Job


@pytest.fixture
def db_session(tmp_path):
    """SQLAlchemy session trên SQLite file tạm, các bảng đã được tạo."""
    db_path = str(tmp_path / "jobs.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    from app.platform.persistence.models import Base

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _make_service(session: Session) -> JobService:
    return JobService(session=session)


def test_create_job_allowed(db_session: Session) -> None:
    """Chính sách allowed => tạo job với status pending."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-1",
            action="crawl",
            url="https://example.com/page",
            idempotency_key="key-1",
        )
    assert job.id is not None
    assert job.caller_id == "user-1"
    assert job.status == "pending"
    assert job.idempotency_key == "key-1"


def test_create_job_blocked(db_session: Session) -> None:
    """Chính sách blocked => không tạo job, nêu lý do."""
    service = _make_service(db_session)
    with (
        patch.object(
            PolicyGate,
            "evaluate",
            return_value=PolicyDecision(False, "ssrf_private_ip", "IP private"),
        ),
        pytest.raises(ValueError, match="chính sách"),
    ):
        service.create_job(
            caller_id="user-1",
            action="crawl",
            url="http://127.0.0.1/",
            idempotency_key="key-2",
        )
    # Không tạo job nào trong DB
    assert db_session.query(Job).count() == 0


def test_idempotency_same_key_returns_existing(db_session: Session) -> None:
    """Request lặp lại cùng idempotency_key + caller_id không tạo job trùng."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job1 = service.create_job(
            caller_id="user-1", action="crawl", url="https://example.com/", idempotency_key="idem-1"
        )
        job2 = service.create_job(
            caller_id="user-1", action="crawl", url="https://example.com/", idempotency_key="idem-1"
        )
    assert job1.id == job2.id


def test_get_job_owner_can_read(db_session: Session) -> None:
    """Caller sở hữu job có thể đọc."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-A",
            action="crawl",
            url="https://example.com/",
            idempotency_key="k-owner",
        )
    fetched = service.get_job(job.id, caller_id="user-A")
    assert fetched is not None
    assert fetched.id == job.id


def test_get_job_other_caller_cannot_read(db_session: Session) -> None:
    """Caller khác không thể đọc job của người khác."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-A", action="crawl", url="https://example.com/", idempotency_key="k-own2"
        )
    fetched = service.get_job(job.id, caller_id="user-B")
    assert fetched is None


def test_cancel_job_owner(db_session: Session) -> None:
    """Caller sở hữu có thể hủy job pending."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-A",
            action="crawl",
            url="https://example.com/",
            idempotency_key="k-cancel",
        )
    result = service.cancel_job(job.id, caller_id="user-A")
    assert result is True
    assert job.status == "cancelled"


def test_cancel_job_other_caller_fails(db_session: Session) -> None:
    """Caller khác không thể hủy job."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-A",
            action="crawl",
            url="https://example.com/",
            idempotency_key="k-cancel2",
        )
    with pytest.raises(JobOwnershipError):
        service.cancel_job(job.id, caller_id="user-B")


def test_claim_job_atomic(db_session: Session) -> None:
    """Worker claim job atomically: pending -> queued, một job chỉ được claim một lần."""
    service = _make_service(db_session)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        job = service.create_job(
            caller_id="user-A",
            action="crawl",
            url="https://example.com/",
            idempotency_key="k-claim",
        )
    claimed = service.claim_job(worker_id="worker-1")
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "queued"
    # Claim lại => None vì job đã không còn pending
    assert service.claim_job(worker_id="worker-2") is None


def test_get_job_not_found(db_session: Session) -> None:
    """Job không tồn tại => JobNotFound."""
    service = _make_service(db_session)
    with pytest.raises(JobNotFound):
        service.get_job(str(uuid.uuid4()), caller_id="user-1")
