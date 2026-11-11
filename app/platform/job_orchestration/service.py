"""Job service — vòng đời job chung cho F01/F02/F03 (P01 Item 4).

Chỉ tạo job khi Policy Gate `allowed`; idempotency key tránh job trùng;
mọi truy vấn job kiểm tra ownership theo caller_id; claim nguyên tử cho worker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform.network_policy.policy import PolicyCommand, evaluate_policy
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import FeatureJob, Job, JobCommand, OutboxEvent
from app.shared.contracts.jobs import MVP_FEATURE_CODES, ExecutionOutcome, QueueMessageV1
from app.shared.contracts.workflows import JobIntent


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


class JobOrchestrationService:
    """Worker v1 job orchestration: durable command, job, outbox — atomically.

    The only component allowed to create or transition FeatureJob for v1.
    Never invokes a worker, queue publisher or network client.
    """

    def __init__(self, repository) -> None:
        self._repo = repository
        self._session = repository.session

    def submit(self, intent: JobIntent) -> FeatureJob:
        """Persist FeatureJob, JobCommand and request OutboxEvent in one transaction.

        Idempotent on (idempotency_scope, idempotency_key): a repeat submit
        returns the existing job and creates no duplicate outbox event.
        """
        if intent.feature_code not in MVP_FEATURE_CODES:
            raise ValueError(f"feature_code not permitted in MVP v1: {intent.feature_code}")

        existing = self._repo.get_job_by_idempotency(
            intent.idempotency_scope, intent.idempotency_key
        )
        if existing is not None:
            return existing

        job = FeatureJob(
            job_id=str(uuid.uuid4()),
            feature_code=intent.feature_code,
            contract_version="v1",
            status="pending_publish",
            idempotency_scope=intent.idempotency_scope,
            idempotency_key=intent.idempotency_key,
            caller_id=intent.caller_id,
            correlation_id=intent.correlation_id,
        )
        self._session.add(job)
        self._session.flush()

        command = JobCommand(
            feature_job_id=job.job_id,
            command_type=intent.feature_code,
            command_payload={"workflow_run_id": intent.workflow_run_id},
        )
        self._session.add(command)

        outbox = OutboxEvent(
            event_type=f"{intent.feature_code}.job_requested.v1",
            message_payload=QueueMessageV1(
                job_id=job.job_id,
                feature_code=intent.feature_code,
                contract_version="v1",
                correlation_id=intent.correlation_id,
            ).model_dump(),
            status="pending_publish",
        )
        self._session.add(outbox)
        self._session.flush()
        return job

    def request_cancel(self, job_id: str, caller_id: str) -> FeatureJob:
        """Mark cancellation_requested; caller must own the job."""
        job = self._repo.get_job(job_id)
        if job is None:
            raise JobNotFound(f"job không tồn tại: {job_id}")
        if job.caller_id != caller_id:
            raise JobOwnershipError(f"caller {caller_id} không sở hữu job {job_id}")
        if job.status in {
            "completed",
            "cancelled",
            "blocked_policy",
            "blocked_drm",
            "blocked_permission",
            "expired",
        }:
            return job
        job.cancellation_state = "requested"
        self._session.flush()
        return job

    def commit_outcome(self, job_id: str, lease_id: str, outcome: ExecutionOutcome) -> FeatureJob:
        """Commit a typed ExecutionOutcome and append a result outbox event.

        Requires an active lease; the result reference is a safe durable ID.
        """
        if not self._repo.is_lease_active(lease_id, job_id):
            raise ValueError("lease không còn hoạt động hoặc không khớp job")
        job = self._repo.get_job(job_id)
        if job is None:
            raise JobNotFound(f"job không tồn tại: {job_id}")

        job.status = outcome.status
        job.result_reference = outcome.result_reference
        job.reason_code = outcome.reason_code
        job.finished_at = datetime.now(UTC)

        result_outbox = OutboxEvent(
            event_type=f"{job.feature_code}.job_completed.v1",
            message_payload=QueueMessageV1(
                job_id=job.job_id,
                feature_code=job.feature_code,
                contract_version="v1",
                correlation_id=job.correlation_id,
            ).model_dump(),
            status="pending_publish",
        )
        self._session.add(result_outbox)
        self._session.flush()
        return job
