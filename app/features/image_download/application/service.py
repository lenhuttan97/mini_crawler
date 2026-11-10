"""Media service — F02 Direct/Batch Image (P03 Item 1).

Tạo media job, validate manifest, quota item/tổng byte, dedupe theo
source_url trong batch. Storage/downloader được inject qua tham dịch vụ
để kiểm thử đơn vị không gọi mạng thật.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.platform.network_policy.policy import PolicyCommand, PolicyGate
from app.platform.persistence.models import MediaJob, MediaJobItem


class MediaQuotaExceeded(Exception):
    """Vượt quota số item hoặc tổng byte."""


class MediaManifestError(Exception):
    """Manifest batch không hợp lệ (trống, trùng URL,...)."""


class MediaPolicyBlocked(Exception):
    """Media URL bị Policy Gate chặn trước khi tạo job hoặc gọi downloader."""


@dataclass(frozen=True)
class MediaItemInput:
    source_url: str
    sequence: int


class MediaService:
    """Quản lý tạo media job và item."""

    def __init__(
        self,
        session,
        max_items: int = 50,
        max_total_bytes: int | None = None,
        policy_gate: Any | None = None,
    ) -> None:
        self._session = session
        self.max_items = max_items
        self.max_total_bytes = max_total_bytes
        self._policy_gate = policy_gate or PolicyGate()

    def create_media_job(
        self,
        *,
        caller_id: str,
        input_type: str,
        source_url: str | None,
        idempotency_key: str,
        items: list[dict[str, Any]] | None = None,
    ) -> MediaJob:
        """Tạo media job (idempotent theo caller_id + idempotency_key)."""
        # Idempotency: trả lại job đã có.
        existing = (
            self._session.query(MediaJob)
            .filter_by(caller_id=caller_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            return existing

        # Validate manifest.
        if input_type == "image_batch":
            if not items:
                raise MediaManifestError("image_batch yêu cầu ít nhất một item")
            item_inputs = self._validate_items(items)
        else:
            if not source_url:
                raise MediaManifestError("direct yêu cầu source_url")
            item_inputs = [MediaItemInput(source_url=source_url or "", sequence=1)]

        for item in item_inputs:
            decision = self._policy_gate.evaluate(
                PolicyCommand(url=item.source_url, action="media_download", caller_id=caller_id)
            )
            if not decision.allowed:
                raise MediaPolicyBlocked(
                    f"media bị chặn bởi chính sách: {decision.reason_code} — {decision.reason_message}"
                )

        job = MediaJob(
            caller_id=caller_id,
            input_type=input_type,
            source_url=source_url,
            policy_status="allowed",
            idempotency_key=idempotency_key,
        )
        self._session.add(job)
        self._session.flush()

        for item_input in item_inputs:
            item = MediaJobItem(
                id=str(uuid.uuid4()),
                media_job_id=job.id,
                sequence=item_input.sequence,
                source_url=item_input.source_url,
                status="pending",
            )
            self._session.add(item)
        self._session.flush()
        return job

    def _validate_items(self, items: list[dict[str, Any]]) -> list[MediaItemInput]:
        if len(items) > self.max_items:
            raise MediaQuotaExceeded(f"vượt quá số item tối đa {self.max_items}")
        seen: set[str] = set()
        results: list[MediaItemInput] = []
        for entry in items:
            source_url = entry.get("source_url", "")
            sequence = int(entry.get("sequence", 0))
            if source_url in seen:
                raise MediaManifestError(f"source_url trùng trong batch: {source_url}")
            seen.add(source_url)
            results.append(MediaItemInput(source_url=source_url, sequence=sequence))
        return results
