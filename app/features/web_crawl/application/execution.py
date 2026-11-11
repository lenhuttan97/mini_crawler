"""Broker-independent crawl execution used by workers and local runtime modes."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.features.web_crawl.application import normalizer
from app.features.web_crawl.application.classifier import DocumentClassifier
from app.features.web_crawl.application.service import CrawlService
from app.features.web_crawl.infrastructure.static_fetcher import StaticFetcher
from app.platform.asset_storage.local import LocalStorageAdapter
from app.platform.asset_storage.storage import StorageAdapter
from app.platform.document_storage.service import (
    PersistenceService,
    confirm_pending_document_uploads,
    rollback_pending_document_uploads,
)
from app.platform.job_orchestration.service import JobService
from app.platform.network_policy.policy import PolicyGate
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import CrawlJob, Job


def process_crawl_job(session: Session, job_id: str, crawl_service=None) -> str | None:
    """Xử lý một crawl job: claim → crawl → complete/fail."""
    job = session.get(Job, job_id)
    if job is None or job.status not in (JobStatus.PENDING.value, JobStatus.QUEUED.value):
        return None
    if job.status == JobStatus.PENDING.value:
        job.status = JobStatus.QUEUED.value
        session.flush()

    crawl_job = session.get(CrawlJob, job_id)
    if crawl_job is None:
        job.status = JobStatus.FAILED.value
        session.flush()
        return None

    if crawl_service is None:
        raise ValueError("crawl_service là bắt buộc để xử lý crawl job")

    job.status = JobStatus.RUNNING.value
    session.flush()
    try:
        asyncio.run(
            crawl_service.crawl(
                url=crawl_job.requested_url,
                caller_id=job.caller_id,
                idempotency_key=job.idempotency_key,
            )
        )
        job.status = JobStatus.COMPLETED.value
    except Exception:  # noqa: BLE001
        rollback_pending_document_uploads(session)
        job.status = JobStatus.FAILED.value
    session.flush()
    return job.id


def build_crawl_service(session: Session, settings: Settings | None = None) -> CrawlService:
    """Compose crawl dependencies for a broker or local execution boundary."""
    settings = settings or Settings()
    if settings.runtime_mode == "broker":
        storage = StorageAdapter(endpoint_url=settings.minio_endpoint)
    else:
        storage = LocalStorageAdapter(settings.local_storage_path)
    return CrawlService(
        job_service=JobService(session),
        policy_gate=PolicyGate(),
        fetcher=StaticFetcher(),
        normalizer=normalizer,
        classifier=DocumentClassifier(),
        persistence=PersistenceService(session, storage),
    )


def execute_crawl_job(
    job_id: str,
    *,
    session_factory=None,
    crawl_service_factory=None,
    settings: Settings | None = None,
) -> str | None:
    """Worker entrypoint: load all state from a trusted persisted job ID."""
    settings = settings or Settings()
    session_factory = session_factory or create_session_factory(settings)
    crawl_service_factory = crawl_service_factory or (
        lambda session: build_crawl_service(session, settings)
    )
    session = session_factory()
    try:
        result = process_crawl_job(
            session=session,
            job_id=job_id,
            crawl_service=crawl_service_factory(session),
        )
        session.commit()
        confirm_pending_document_uploads(session)
        return result
    except Exception:
        session.rollback()
        rollback_pending_document_uploads(session)
        raise
    finally:
        session.close()
