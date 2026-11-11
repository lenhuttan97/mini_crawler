"""Tests cho crawl worker (P02 Item 8).

process_crawl_job claim job → crawl_service.crawl → complete/fail. Dùng
SQLite + crawl_service bị mock, không cần Celery broker thật.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.features.web_crawl.worker.task import process_crawl_job
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Base, CrawlJob, Job


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


def test_process_crawl_job_rolls_back_pending_uploads_on_error(db_session, monkeypatch) -> None:
    """Crawl lỗi => object đã upload bị rollback trước khi job thành failed."""
    from app.features.web_crawl.application import execution

    _make_job(db_session, status="pending")
    crawl_service = AsyncMock()
    crawl_service.crawl.side_effect = Exception("network timeout")
    rolled_back = []
    monkeypatch.setattr(execution, "rollback_pending_document_uploads", rolled_back.append)

    process_crawl_job(session=db_session, job_id="job-worker-1", crawl_service=crawl_service)

    assert rolled_back == [db_session]
    assert db_session.get(Job, "job-worker-1").status == JobStatus.FAILED.value


def test_execute_crawl_job_loads_its_session_from_job_id(db_session) -> None:
    """Celery payload is only job_id; task creates its own session and service."""
    from app.features.web_crawl.worker.task import execute_crawl_job

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


def test_execute_crawl_job_confirms_uploads_after_commit(db_session, monkeypatch) -> None:
    """Upload chỉ được confirm sau khi commit thành công."""
    from app.features.web_crawl.application import execution
    from app.features.web_crawl.worker.task import execute_crawl_job

    _make_job(db_session, status="pending")
    crawl_service = AsyncMock()
    crawl_service.crawl.return_value = {"job_id": "job-worker-1"}
    events = []
    original_commit = db_session.commit

    def commit():
        events.append("commit")
        original_commit()

    monkeypatch.setattr(db_session, "commit", commit)
    monkeypatch.setattr(
        execution,
        "confirm_pending_document_uploads",
        lambda _session: events.append("confirm"),
    )
    monkeypatch.setattr(
        execution,
        "rollback_pending_document_uploads",
        lambda _session: events.append("rollback"),
    )

    execute_crawl_job(
        "job-worker-1",
        session_factory=lambda: db_session,
        crawl_service_factory=lambda _session: crawl_service,
    )

    assert events == ["commit", "confirm"]


def test_execute_crawl_job_rolls_back_uploads_after_commit_failure(db_session, monkeypatch) -> None:
    """Commit lỗi => rollback object đã upload và re-raise."""
    from app.features.web_crawl.application import execution
    from app.features.web_crawl.worker.task import execute_crawl_job

    _make_job(db_session, status="pending")
    crawl_service = AsyncMock()
    crawl_service.crawl.return_value = {"job_id": "job-worker-1"}
    monkeypatch.setattr(db_session, "commit", MagicMock(side_effect=RuntimeError("commit failed")))
    rolled_back = []
    monkeypatch.setattr(execution, "rollback_pending_document_uploads", rolled_back.append)

    with pytest.raises(RuntimeError, match="commit failed"):
        execute_crawl_job(
            "job-worker-1",
            session_factory=lambda: db_session,
            crawl_service_factory=lambda _session: crawl_service,
        )

    assert rolled_back == [db_session]
