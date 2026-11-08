"""Tests cho crawl worker (P02 Item 8).

process_crawl_job claim job → crawl_service.crawl → complete/fail. Dùng
SQLite + crawl_service bị mock, không cần Celery broker thật.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.enums import JobStatus
from app.domain.models import Base, CrawlJob, Job
from app.workers.tasks import process_crawl_job


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "crawlworker.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _make_job(session, status="pending", requested_url="https://example.com/page"):
    job = Job(
        id="job-worker-1",
        type="crawl",
        status=status,
        caller_id="user-1",
        idempotency_key="idem-worker-1",
    )
    session.add(job)
    session.flush()
    cj = CrawlJob(
        job_id="job-worker-1",
        requested_url=requested_url,
        canonical_url=None,
        policy_status=None,
        error_code=None,
    )
    session.add(cj)
    session.commit()
    return job


def test_process_crawl_job_marks_completed(db_session) -> None:
    """Claim pending → crawl_service.crawl → đánh completed."""
    job = _make_job(db_session, status="pending")
    crawl_service = AsyncMock()
    crawl_service.crawl.return_value = MagicMock(job_id="job-worker-1", document_id="doc-1")

    result = process_crawl_job(
        session=db_session, job_id="job-worker-1", crawl_service=crawl_service
    )

    assert result == "job-worker-1"
    crawl_service.crawl.assert_awaited_once_with(
        url="https://example.com/page", caller_id="user-1", idempotency_key="idem-worker-1"
    )
    db_session.expire_all()
    job = db_session.get(Job, "job-worker-1")
    assert job.status == JobStatus.COMPLETED.value


def test_process_crawl_job_not_pending_returns_none(db_session) -> None:
    """Job không phải pending => trả None, không crawl."""
    _make_job(db_session, status="completed")
    crawl_service = AsyncMock()

    result = process_crawl_job(
        session=db_session, job_id="job-worker-1", crawl_service=crawl_service
    )

    assert result is None
    crawl_service.crawl.assert_not_called()


def test_process_crawl_job_marks_failed_on_error(db_session) -> None:
    """Crawl service ném lỗi => đánh failed."""
    job = _make_job(db_session, status="pending")
    crawl_service = AsyncMock()
    crawl_service.crawl.side_effect = Exception("network timeout")

    result = process_crawl_job(
        session=db_session, job_id="job-worker-1", crawl_service=crawl_service
    )

    assert result == "job-worker-1"
    db_session.expire_all()
    job = db_session.get(Job, "job-worker-1")
    assert job.status == JobStatus.FAILED.value


def test_execute_crawl_job_loads_its_session_from_job_id(db_session) -> None:
    """Celery payload is only job_id; task creates its own session and service."""
    from app.workers.tasks import execute_crawl_job

    _make_job(db_session, status="pending")
    session_factory = lambda: db_session
    crawl_service = AsyncMock()
    crawl_service.crawl.return_value = {"job_id": "job-worker-1", "document_id": "doc-1"}

    result = execute_crawl_job(
        "job-worker-1",
        session_factory=session_factory,
        crawl_service_factory=lambda _session: crawl_service,
    )

    assert result == "job-worker-1"
    crawl_service.crawl.assert_awaited_once()
    db_session.expire_all()
    assert db_session.get(Job, "job-worker-1").status == JobStatus.COMPLETED.value
