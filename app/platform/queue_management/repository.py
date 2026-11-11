"""Repository for worker v1 queue management durable state.

Builds safe broker envelopes and manages outbox publication state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.platform.persistence.models import OutboxEvent
from app.shared.contracts.jobs import QueueMessageV1


class QueueManagementRepository:
    """Durable state access for outbox events and queue message building."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def build_queue_message(
        self, job_id: str, feature_code: str, contract_version: str, correlation_id: str
    ) -> QueueMessageV1:
        """Build the four-field broker envelope. No raw URLs or commands cross the broker."""
        return QueueMessageV1(
            job_id=job_id,
            feature_code=feature_code,
            contract_version=contract_version,
            correlation_id=correlation_id,
        )

    def get_pending_outbox(self) -> list[dict[str, Any]]:
        """Return all pending outbox events for redelivery."""
        rows = (
            self._session.execute(
                select(OutboxEvent).where(OutboxEvent.status == "pending_publish")
            )
            .scalars()
            .all()
        )
        return [
            {
                "event_id": row.id,
                "event_type": row.event_type,
                "message_payload": row.message_payload,
            }
            for row in rows
        ]

    def mark_outbox_published(self, event_id: str) -> None:
        self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status="published", published_at=datetime.now(UTC))
        )
