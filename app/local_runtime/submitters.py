"""Inline submitters that execute a committed feature job in the API process."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.features.image_download.application.submission import (
    MediaJobSubmission,
    MediaJobSubmitter,
)
from app.features.web_crawl.application.submission import (
    CrawlJobSubmission,
    CrawlJobSubmitter,
)
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Job, MediaJob


class InlineCrawlJobSubmitter:
    """Persist a crawl job, execute it once, and return its persisted status."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        execute: Callable[[str], Any],
    ) -> None:
        self._session_factory = session_factory
        self._execute = execute

    def submit(self, *, url: str, caller_id: str, idempotency_key: str) -> CrawlJobSubmission:
        executed = False

        def run(job_id: str) -> None:
            nonlocal executed
            executed = True
            try:
                self._execute(job_id)
            except Exception:  # noqa: BLE001
                self._mark_failed(job_id)

        result = CrawlJobSubmitter(session_factory=self._session_factory, enqueue=run).submit(
            url=url,
            caller_id=caller_id,
            idempotency_key=idempotency_key,
        )
        if not executed:
            return result
        return CrawlJobSubmission(job_id=result.job_id, status=self._status(result.job_id))

    def _status(self, job_id: str) -> str:
        session = self._session_factory()
        try:
            job = session.get(Job, job_id)
            return job.status if job is not None else JobStatus.FAILED.value
        finally:
            session.close()

    def _mark_failed(self, job_id: str) -> None:
        session = self._session_factory()
        try:
            job = session.get(Job, job_id)
            if job is not None and not JobStatus(job.status).is_terminal():
                job.status = JobStatus.FAILED.value
                session.commit()
        finally:
            session.close()


class InlineMediaJobSubmitter:
    """Persist a media job, execute it once, and return its persisted status."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        execute: Callable[[str], Any],
    ) -> None:
        self._session_factory = session_factory
        self._execute = execute

    def submit(
        self,
        *,
        caller_id: str,
        input_type: str,
        source_url: str | None,
        idempotency_key: str,
        items: list[dict[str, Any]] | None = None,
    ) -> MediaJobSubmission:
        executed = False

        def run(job_id: str) -> None:
            nonlocal executed
            executed = True
            try:
                self._execute(job_id)
            except Exception:  # noqa: BLE001
                self._mark_failed(job_id)

        result = MediaJobSubmitter(session_factory=self._session_factory, enqueue=run).submit(
            caller_id=caller_id,
            input_type=input_type,
            source_url=source_url,
            idempotency_key=idempotency_key,
            items=items,
        )
        if not executed:
            return result
        return MediaJobSubmission(job_id=result.job_id, status=self._status(result.job_id))

    def _status(self, job_id: str) -> str:
        session = self._session_factory()
        try:
            job = session.get(MediaJob, job_id)
            return job.status if job is not None else JobStatus.FAILED.value
        finally:
            session.close()

    def _mark_failed(self, job_id: str) -> None:
        session = self._session_factory()
        try:
            job = session.get(MediaJob, job_id)
            if job is not None and not JobStatus(job.status).is_terminal():
                job.status = JobStatus.FAILED.value
                session.commit()
        finally:
            session.close()
