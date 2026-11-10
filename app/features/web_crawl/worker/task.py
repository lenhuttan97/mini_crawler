"""Hàm xử lý task worker crawl (P01 Item 5).

Các hàm này là thao tác trên crawl job và được đăng ký
là Celery task. Chúng nhận SQLAlchemy session để kiểm thử đơn vị không
cần broker Redis thật.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.features.web_crawl.application.classifier import DocumentClassifier
from app.features.web_crawl.application import normalizer
from app.features.web_crawl.application.service import CrawlService
from app.features.web_crawl.infrastructure.static_fetcher import StaticFetcher
from app.platform.asset_storage.storage import StorageAdapter
from app.platform.job_orchestration.service import JobService
from app.platform.network_policy.policy import PolicyGate
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import CrawlJob, Job
from app.platform.document_storage.service import PersistenceService
from app.workers.celery_app import celery_app


def process_crawl_job(session: Session, job_id: str, crawl_service=None) -> str | None:
    """Xử lý một crawl job: claim → crawl → complete/fail.

    crawl_service có thể được truyền vào để kiểm thử đơn vị mà không cần
    khởi tạo toàn bộ StaticFetcher/Normalizer/Classifier/Persistence.
    """
    job = session.get(Job, job_id)
    if job is None or job.status != JobStatus.PENDING.value:
        return None
    job.status = JobStatus.QUEUED.value
    session.flush()

    crawl_job = session.get(CrawlJob, job_id)
    if crawl_job is None:
        job.status = JobStatus.FAILED.value
        session.flush()
        return None

    if crawl_service is None:
        raise ValueError("crawl_service là bắt buộc để xử lý crawl job")

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
        job.status = JobStatus.FAILED.value
    session.flush()
    return job.id


def _build_crawl_service(session: Session) -> CrawlService:
    """Compose crawl dependencies for a real worker process."""
    settings = Settings()
    return CrawlService(
        job_service=JobService(session),
        policy_gate=PolicyGate(),
        fetcher=StaticFetcher(),
        normalizer=normalizer,
        classifier=DocumentClassifier(),
        persistence=PersistenceService(
            session,
            StorageAdapter(endpoint_url=settings.minio_endpoint),
        ),
    )


def execute_crawl_job(
    job_id: str,
    *,
    session_factory=None,
    crawl_service_factory=None,
) -> str | None:
    """Worker entrypoint: load all state from a trusted persisted job ID."""
    session_factory = session_factory or create_session_factory(Settings())
    crawl_service_factory = crawl_service_factory or _build_crawl_service
    session = session_factory()
    try:
        result = process_crawl_job(
            session=session,
            job_id=job_id,
            crawl_service=crawl_service_factory(session),
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


celery_app.task(name="app.features.web_crawl.worker.task.process_crawl_job")(process_crawl_job)
celery_app.task(name="app.features.web_crawl.worker.task.execute_crawl_job")(execute_crawl_job)
