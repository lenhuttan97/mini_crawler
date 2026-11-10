"""Durable asynchronous submission of direct and batch media jobs (P03)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.platform.persistence.models import MediaJob
from app.features.image_download.application.service import MediaService


@dataclass(frozen=True)
class MediaJobSubmission:
    """Immediate response after media job persistence and enqueue."""

    job_id: str
    status: str


class MediaJobSubmitter:
    """Persist a policy-approved media job before emitting its trusted ID."""

    def __init__(
        self, *, session_factory: Callable[[], Any], enqueue: Callable[[str], None]
    ) -> None:
        self._session_factory = session_factory
        self._enqueue = enqueue

    def submit(
        self,
        *,
        caller_id: str,
        input_type: str,
        source_url: str | None,
        idempotency_key: str,
        items: list[dict[str, Any]] | None = None,
    ) -> MediaJobSubmission:
        """Commit media job/items before enqueueing a single media job ID."""
        session = self._session_factory()
        try:
            existing = (
                session.query(MediaJob)
                .filter_by(caller_id=caller_id, idempotency_key=idempotency_key)
                .first()
            )
            enqueue_required = existing is None
            job = existing or MediaService(session).create_media_job(
                caller_id=caller_id,
                input_type=input_type,
                source_url=source_url,
                idempotency_key=idempotency_key,
                items=items,
            )
            session.commit()
            submission = MediaJobSubmission(job_id=job.id, status=job.status)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        if enqueue_required:
            self._enqueue(submission.job_id)
        return submission
