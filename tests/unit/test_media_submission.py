"""Durable asynchronous media-job submission tests (P03)."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.policy import PolicyDecision, PolicyGate
from app.domain.models import Base, MediaJob, MediaJobItem


def test_submit_persists_media_job_and_item_before_enqueuing(tmp_path) -> None:
    """Queue receives only a committed media job ID after policy-approved persistence."""
    from app.services.media_submission import MediaJobSubmitter

    engine = create_engine(f"sqlite:///{tmp_path / 'media-submission.db'}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    enqueued: list[str] = []

    def enqueue(job_id: str) -> None:
        with session_factory() as verification_session:
            assert verification_session.get(MediaJob, job_id).status == "pending"
            assert (
                verification_session.query(MediaJobItem).filter_by(media_job_id=job_id).count() == 1
            )
        enqueued.append(job_id)

    submitter = MediaJobSubmitter(session_factory=session_factory, enqueue=enqueue)
    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        result = submitter.submit(
            caller_id="caller-1",
            input_type="direct",
            source_url="https://example.com/a.png",
            idempotency_key="media-request-1",
        )

    assert result.status == "pending"
    assert enqueued == [result.job_id]
