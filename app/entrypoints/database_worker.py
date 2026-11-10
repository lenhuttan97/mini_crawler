"""Single-process local worker that polls PostgreSQL/SQLite for pending jobs."""

from __future__ import annotations

import time
from functools import partial
from typing import Any

from sqlalchemy import select, update

from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.features.image_download.application.execution import execute_media_job
from app.features.web_crawl.application.execution import execute_crawl_job
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Job, MediaJob


def _claim_job(session, model, *conditions: Any) -> str | None:
    job_id = session.execute(
        select(model.id).where(*conditions).order_by(model.id).limit(1)
    ).scalar_one_or_none()
    if job_id is None:
        return None
    claimed = session.execute(
        update(model)
        .where(model.id == job_id, model.status == JobStatus.PENDING.value)
        .values(status=JobStatus.QUEUED.value)
        .returning(model.id)
    ).scalar_one_or_none()
    session.commit()
    return claimed


def _mark_failed(session_factory, model, job_id: str) -> None:
    session = session_factory()
    try:
        job = session.get(model, job_id)
        if job is not None and not JobStatus(job.status).is_terminal():
            job.status = JobStatus.FAILED.value
            session.commit()
    finally:
        session.close()


def run_once(*, session_factory, crawl_executor, media_executor) -> bool:
    """Claim and execute at most one pending crawl or media job."""
    session = session_factory()
    try:
        crawl_id = _claim_job(session, Job, Job.type == "crawl")
        if crawl_id is not None:
            model = Job
        else:
            media_id = _claim_job(session, MediaJob)
            model = MediaJob
    finally:
        session.close()

    if crawl_id is not None:
        try:
            crawl_executor(crawl_id)
        except Exception:  # noqa: BLE001
            _mark_failed(session_factory, model, crawl_id)
        return True
    if media_id is not None:
        try:
            media_executor(media_id)
        except Exception:  # noqa: BLE001
            _mark_failed(session_factory, model, media_id)
        return True
    return False


def main() -> None:
    """Run one local DB worker until interrupted; no broker or concurrency."""
    settings = Settings()
    if settings.runtime_mode != "db-worker":
        raise SystemExit("database_worker requires APP_RUNTIME_MODE=db-worker")
    session_factory = create_session_factory(settings)
    crawl_executor = partial(execute_crawl_job, session_factory=session_factory, settings=settings)
    media_executor = partial(execute_media_job, session_factory=session_factory, settings=settings)

    try:
        while True:
            if not run_once(
                session_factory=session_factory,
                crawl_executor=crawl_executor,
                media_executor=media_executor,
            ):
                time.sleep(settings.local_worker_poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
