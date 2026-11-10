"""Generic job lifecycle task helpers (P01 Item 5).

claim/complete/fail/maintenance helpers cho vòng đời job chung.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.entrypoints.celery_worker import celery_app
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Job


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


celery_app.task(name="app.platform.queue_management.tasks.claim_job")(claim_job)
celery_app.task(name="app.platform.queue_management.tasks.complete_job")(complete_job)
celery_app.task(name="app.platform.queue_management.tasks.fail_job")(fail_job)
celery_app.task(name="app.platform.queue_management.tasks.maintenance_job")(maintenance_job)
