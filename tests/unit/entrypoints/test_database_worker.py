"""Tests for the single-process database-only local worker."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.entrypoints.database_worker import run_once
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Base, CrawlJob, Job, MediaJob, MediaJobItem


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    yield factory
    engine.dispose()


def _create_pending_crawl(session_factory) -> str:
    with session_factory() as session:
        session.add(
            Job(
                id="crawl-job-1",
                type="crawl",
                status=JobStatus.PENDING.value,
                caller_id="caller-1",
                idempotency_key="crawl-key-1",
            )
        )
        session.add(
            CrawlJob(
                job_id="crawl-job-1",
                requested_url="https://example.com/article",
                canonical_url=None,
                policy_status="allowed",
                error_code=None,
            )
        )
        session.commit()
    return "crawl-job-1"


def _create_pending_media(session_factory) -> str:
    with session_factory() as session:
        session.add(
            MediaJob(
                id="media-job-1",
                caller_id="caller-1",
                input_type="direct",
                status=JobStatus.PENDING.value,
                source_url="https://example.com/a.png",
                idempotency_key="media-key-1",
            )
        )
        session.add(
            MediaJobItem(
                id="media-item-1",
                media_job_id="media-job-1",
                sequence=1,
                source_url="https://example.com/a.png",
                status="pending",
            )
        )
        session.commit()
    return "media-job-1"


def _complete_crawl(session_factory):
    def execute(job_id: str) -> None:
        with session_factory() as session:
            job = session.get(Job, job_id)
            assert job.status == JobStatus.QUEUED.value
            job.status = JobStatus.COMPLETED.value
            session.commit()

    return execute


def _complete_media(session_factory):
    def execute(job_id: str) -> None:
        with session_factory() as session:
            job = session.get(MediaJob, job_id)
            assert job.status == JobStatus.QUEUED.value
            job.status = JobStatus.COMPLETED.value
            session.commit()

    return execute


def test_run_once_claims_pending_crawl_and_completes_it(session_factory) -> None:
    """A pending crawl is claimed before its executor runs and completes."""
    _create_pending_crawl(session_factory)

    worked = run_once(
        session_factory=session_factory,
        crawl_executor=_complete_crawl(session_factory),
        media_executor=_complete_media(session_factory),
    )

    assert worked is True
    with session_factory() as session:
        assert session.get(Job, "crawl-job-1").status == JobStatus.COMPLETED.value


def test_run_once_claims_pending_media_and_completes_it(session_factory) -> None:
    """A pending media job is claimed and completes without a broker."""
    _create_pending_media(session_factory)

    worked = run_once(
        session_factory=session_factory,
        crawl_executor=_complete_crawl(session_factory),
        media_executor=_complete_media(session_factory),
    )

    assert worked is True
    with session_factory() as session:
        assert session.get(MediaJob, "media-job-1").status == JobStatus.COMPLETED.value


def test_run_once_returns_false_when_no_pending_work(session_factory) -> None:
    """An idle database does not repeatedly execute terminal records."""
    _create_pending_crawl(session_factory)
    with session_factory() as session:
        session.get(Job, "crawl-job-1").status = JobStatus.COMPLETED.value
        session.commit()

    worked = run_once(
        session_factory=session_factory,
        crawl_executor=_complete_crawl(session_factory),
        media_executor=_complete_media(session_factory),
    )

    assert worked is False


def test_run_once_marks_unexpected_crawl_failure(session_factory) -> None:
    """An executor crash leaves a safe failed state instead of a queued record."""
    _create_pending_crawl(session_factory)

    def fail(_job_id: str) -> None:
        raise RuntimeError("worker crashed")

    worked = run_once(
        session_factory=session_factory,
        crawl_executor=fail,
        media_executor=_complete_media(session_factory),
    )

    assert worked is True
    with session_factory() as session:
        assert session.get(Job, "crawl-job-1").status == JobStatus.FAILED.value


def test_claimed_crawl_job_can_move_queued_to_terminal() -> None:
    """The shared executor accepts a runner-claimed queued crawl job."""
    from unittest.mock import AsyncMock, MagicMock

    from app.features.web_crawl.application.execution import process_crawl_job

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    session = factory()
    try:
        session.add(
            Job(
                id="crawl-job-2",
                type="crawl",
                status=JobStatus.QUEUED.value,
                caller_id="caller-1",
                idempotency_key="crawl-key-2",
            )
        )
        session.add(CrawlJob(job_id="crawl-job-2", requested_url="https://example.com/article"))
        session.flush()
        crawl_service = AsyncMock()
        crawl_service.crawl.return_value = MagicMock(job_id="crawl-job-2")

        result = process_crawl_job(session, "crawl-job-2", crawl_service)

        assert result == "crawl-job-2"
        assert session.get(Job, "crawl-job-2").status == JobStatus.COMPLETED.value
    finally:
        session.close()
        engine.dispose()
