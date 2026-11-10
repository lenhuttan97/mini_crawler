"""Tests for durable, asynchronous crawl-job submission (P02)."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.network_policy.policy import PolicyDecision, PolicyGate
from app.platform.persistence.models import Base, CrawlJob, Job


def test_submit_persists_crawl_job_before_enqueuing(tmp_path) -> None:
    """Queue receives only a committed job ID, never a URL or a live session."""
    from app.services.crawl_submission import CrawlJobSubmitter

    engine = create_engine(f"sqlite:///{tmp_path / 'submission.db'}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    enqueued_job_ids: list[str] = []

    def enqueue(job_id: str) -> None:
        with session_factory() as verification_session:
            assert verification_session.get(Job, job_id) is not None
            assert verification_session.get(CrawlJob, job_id) is not None
        enqueued_job_ids.append(job_id)

    submitter = CrawlJobSubmitter(session_factory=session_factory, enqueue=enqueue)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        result = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )

    assert result.status == "pending"
    assert enqueued_job_ids == [result.job_id]


def test_submit_is_idempotent_and_does_not_enqueue_twice(tmp_path) -> None:
    """The existing caller/idempotency job is returned without a duplicate task."""
    from app.services.crawl_submission import CrawlJobSubmitter

    engine = create_engine(f"sqlite:///{tmp_path / 'idempotency.db'}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    enqueued_job_ids: list[str] = []
    submitter = CrawlJobSubmitter(session_factory=session_factory, enqueue=enqueued_job_ids.append)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        first = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )
        second = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )

    assert second == first
    assert enqueued_job_ids == [first.job_id]
