"""Durable asynchronous submission of crawl jobs (P02)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.platform.persistence.models import CrawlJob
from app.platform.job_orchestration.service import JobService


@dataclass(frozen=True)
class CrawlJobSubmission:
    """Immediate result returned after a crawl job is persisted and queued."""

    job_id: str
    status: str


class CrawlJobSubmitter:
    """Create an idempotent crawl job and enqueue its ID after commit."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        enqueue: Callable[[str], None],
    ) -> None:
        self._session_factory = session_factory
        self._enqueue = enqueue

    def submit(self, *, url: str, caller_id: str, idempotency_key: str) -> CrawlJobSubmission:
        """Persist the shared job and crawl detail before emitting a task message."""
        session = self._session_factory()
        try:
            job = JobService(session).create_job(
                caller_id=caller_id,
                action="crawl",
                url=url,
                idempotency_key=idempotency_key,
            )
            crawl_job = session.get(CrawlJob, job.id)
            enqueue_required = crawl_job is None
            if enqueue_required:
                session.add(
                    CrawlJob(
                        job_id=job.id,
                        requested_url=url,
                        canonical_url=None,
                        policy_status="allowed",
                        error_code=None,
                    )
                )
            session.commit()
            submission = CrawlJobSubmission(job_id=job.id, status=job.status)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        if enqueue_required:
            self._enqueue(submission.job_id)
        return submission
