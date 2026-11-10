"""Job service — vòng đời job chung cho F01/F02/F03 (P01 Item 4).

Chỉ tạo job khi Policy Gate `allowed`; idempotency key tránh job trùng;
mọi truy vấn job kiểm tra ownership theo caller_id; claim nguyên tử cho worker.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform.network_policy.policy import PolicyCommand, evaluate_policy
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Job


class JobNotFound(Exception):
    """Job không tồn tại."""


class JobOwnershipError(Exception):
    """Caller không sở hữu job (không được đọc/hủy)."""


class JobService:
    """Quản lý vòng đời job: tạo, đọc, hủy, claim nguyên tử."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_job(
        self,
        *,
        caller_id: str,
        action: str,
        url: str,
        idempotency_key: str,
    ) -> Job:
        """Tạo job nếu chính sách cho phép. Idempotent theo (caller_id, idempotency_key)."""
        decision = evaluate_policy(PolicyCommand(url=url, action=action, caller_id=caller_id))
        if not decision.allowed:
            raise ValueError(
                f"job bị chặn bởi chính sách: {decision.reason_code} — {decision.reason_message}"
            )

        # Idempotency: trả lại job đã có nếu cùng caller_id + idempotency_key.
        existing = (
            self._session.query(Job)
            .filter_by(caller_id=caller_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            return existing

        job = Job(
            type=action,
            status=JobStatus.PENDING.value,
            caller_id=caller_id,
            idempotency_key=idempotency_key,
        )
        try:
            self._session.add(job)
            self._session.flush()
        except IntegrityError:
            # Race condition: job đã được tạo bởi request khác — trả lại bản ghi hiện có.
            self._session.rollback()
            existing = (
                self._session.query(Job)
                .filter_by(caller_id=caller_id, idempotency_key=idempotency_key)
                .first()
            )
            if existing is None:
                raise
            return existing
        return job

    def get_job(self, job_id, caller_id: str) -> Job | None:
        """Đọc job nếu tồn tại và caller là chủ sở hữu; None nếu không sở hữu."""
        job = self._session.get(Job, job_id)
        if job is None:
            raise JobNotFound(f"job không tồn tại: {job_id}")
        if job.caller_id != caller_id:
            return None
        return job

    def cancel_job(self, job_id, caller_id: str) -> bool:
        """Hủy job nếu caller sở hữu và job chưa ở trạng thái cuối cùng."""
        job = self._session.get(Job, job_id)
        if job is None:
            raise JobNotFound(f"job không tồn tại: {job_id}")
        if job.caller_id != caller_id:
            raise JobOwnershipError(f"caller {caller_id} không sở hữu job {job_id}")
        if JobStatus(job.status).is_terminal():
            return False
        job.status = JobStatus.CANCELLED.value
        job.finished_at = datetime.now(UTC)
        self._session.flush()
        return True

    def claim_job(self, worker_id: str) -> Job | None:
        """Claim nguyên tử một job pending cho worker; trả None nếu không có job pending."""
        pending_id_subq = (
            select(Job.id)
            .where(Job.status == JobStatus.PENDING.value)
            .order_by(Job.created_at)
            .limit(1)
        )
        result = self._session.execute(
            update(Job)
            .where(Job.id.in_(pending_id_subq))
            .values(status=JobStatus.QUEUED.value, attempts=Job.attempts + 1)
            .returning(Job.id)
        )
        row = result.first()
        if row is None:
            return None
        self._session.flush()
        return self._session.get(Job, row[0])
