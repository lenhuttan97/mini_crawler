"""Repository for worker v1 job orchestration durable state.

All queries touch PostgreSQL only. No broker, no worker, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.platform.persistence.models import FeatureJob, JobCommand, JobLease, OutboxEvent


class JobOrchestrationRepository:
    """Durable state access for FeatureJob, JobCommand, OutboxEvent and JobLease."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_job(self, job_id: str) -> FeatureJob | None:
        return self._session.get(FeatureJob, job_id)

    def get_job_by_idempotency(
        self, idempotency_scope: str, idempotency_key: str
    ) -> FeatureJob | None:
        return self._session.execute(
            select(FeatureJob).where(
                FeatureJob.idempotency_scope == idempotency_scope,
                FeatureJob.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def get_command(self, feature_job_id: str) -> JobCommand | None:
        return self._session.execute(
            select(JobCommand).where(JobCommand.feature_job_id == feature_job_id)
        ).scalar_one_or_none()

    def get_pending_outbox(self) -> OutboxEvent | None:
        return self._session.execute(
            select(OutboxEvent).where(OutboxEvent.status == "pending_publish").limit(1)
        ).scalar_one_or_none()

    def count_outbox(self, status: str) -> int:
        return (
            self._session.execute(select(OutboxEvent).where(OutboxEvent.status == status))
            .scalars()
            .all()
            .__len__()
        )

    def mark_outbox_published(self, event_id: str) -> None:
        self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status="published", published_at=datetime.now(UTC))
        )

    def acquire_lease(
        self, feature_job_id: str, worker_id: str, ttl_seconds: int = 300
    ) -> JobLease | None:
        """Atomically acquire a lease for a runnable job. One winner only."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        row = self._session.execute(
            update(FeatureJob)
            .where(
                FeatureJob.job_id == feature_job_id,
                FeatureJob.status.in_(("pending_publish", "queued", "retry_scheduled")),
                FeatureJob.cancellation_state == "none",
            )
            .values(status="running")
            .returning(FeatureJob.job_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        lease = JobLease(
            feature_job_id=feature_job_id,
            lease_owner=worker_id,
            lease_expires_at=expires_at,
        )
        self._session.add(lease)
        self._session.flush()
        return lease

    def get_lease(self, lease_id: str) -> JobLease | None:
        return self._session.get(JobLease, lease_id)

    @property
    def session(self) -> Session:
        return self._session

    def release_lease(self, lease_id: str) -> None:
        self._session.execute(
            update(JobLease)
            .where(JobLease.id == lease_id)
            .values(lease_expires_at=datetime.now(UTC))
        )

    def is_lease_active(self, lease_id: str, feature_job_id: str) -> bool:
        lease = self.get_lease(lease_id)
        if lease is None or lease.feature_job_id != feature_job_id:
            return False
        return lease.lease_expires_at > datetime.now(UTC)
