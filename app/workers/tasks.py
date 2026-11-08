"""Hàm xử lý task worker (P01 Item 5).

Các hàm này là thao tác trên job (claim/complete/fail) và được đăng ký
là Celery task. Chúng nhận SQLAlchemy session để kiểm thử đơn vị không
cần broker Redis thật.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.static_fetcher import StaticFetcher
from app.adapters.storage import StorageAdapter
from app.core.database import create_session_factory
from app.core.policy import PolicyGate
from app.core.settings import Settings
from app.domain.enums import JobStatus
from app.domain.models import CrawlJob, Job
from app.services import normalizer
from app.services.classifier import DocumentClassifier
from app.services.crawl_service import CrawlService
from app.services.jobs import JobService
from app.services.persistence import PersistenceService
from app.workers.celery_app import celery_app


def claim_job(session: Session, job_type: str) -> str | None:
    """Claim nguyên tử một job pending của loại job_type; trả job_id hoặc None."""
    pending_id = session.execute(
        select(Job.id)
        .where(Job.type == job_type, Job.status == JobStatus.PENDING.value)
        .order_by(Job.created_at)
        .limit(1)
    ).scalar_one_or_none()
    if pending_id is None:
        return None
    session.execute(
        update(Job)
        .where(Job.id == pending_id)
        .values(status=JobStatus.QUEUED.value, attempts=Job.attempts + 1)
    )
    session.flush()
    return str(pending_id)


def complete_job(session: Session, job_id: str) -> None:
    """Đánh job hoàn tất."""
    job = session.get(Job, job_id)
    if job is not None:
        job.status = JobStatus.COMPLETED.value
        session.flush()


def fail_job(session: Session, job_id: str, error_code: str) -> None:
    """Đánh job thất bại với mã lỗi."""
    job = session.get(Job, job_id)
    if job is not None:
        job.status = JobStatus.FAILED.value
        session.flush()


def maintenance_job(session: Session) -> None:
    """Task bảo trì (placeholder cho cleanup/object orphan)."""
    session.flush()


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


# Đăng ký như Celery task (giữ nguyên hàm gốc để kiểm thử đơn vị trực tiếp).
celery_app.task(name="app.workers.tasks.claim_job")(claim_job)
celery_app.task(name="app.workers.tasks.complete_job")(complete_job)
celery_app.task(name="app.workers.tasks.fail_job")(fail_job)
celery_app.task(name="app.workers.tasks.maintenance_job")(maintenance_job)
celery_app.task(name="app.workers.tasks.process_crawl_job")(process_crawl_job)
celery_app.task(name="app.workers.tasks.execute_crawl_job")(execute_crawl_job)
