"""Audit và metrics (P01 Item 7).

Ghi sự kiện kiểm tra (audit event) vào bảng audit_events và sự kiện đo
lường (metric) qua structlog. Không lưu secret, raw URL, hoặc dữ liệu nhạy
cảm vào audit/metric label.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.domain.models import AuditEvent


class AuditService:
    """Ghi sự kiện kiểm tra và sự kiện đo lường."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session
        self._logger = structlog.get_logger("mini-crawler.audit")

    def record_audit(
        self,
        *,
        caller_id: str,
        action: str,
        decision: str,
        reason_code: str | None = None,
        trace_id: str | None = None,
    ) -> AuditEvent:
        """Ghi một sự kiện kiểm tra; reason_code là mã đã redaction."""
        event = AuditEvent(
            caller_id=caller_id,
            action=action,
            decision=decision,
            reason_code=reason_code,
            trace_id=trace_id,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def list_by_caller(self, caller_id: str) -> list[AuditEvent]:
        """Truy vấn sự kiện kiểm tra theo caller_id."""
        return (
            self._session.query(AuditEvent)
            .filter_by(caller_id=caller_id)
            .order_by(AuditEvent.created_at.desc())
            .all()
        )

    def record_metric(self, logger: Any, name: str, **labels: Any) -> None:
        """Ghi sự kiện đo lường qua structlog/logger; labels không chứa secret."""
        self._logger.info("metric", name=name, **labels)
        logger.info("metric", name=name, **labels)
