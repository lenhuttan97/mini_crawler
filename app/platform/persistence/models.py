"""SQLAlchemy ORM models cho bảng cốt lõi (P01 Item 2/4).

Các model ánh xạ 1-1 với schema trong migration `0001_initial_schema`
để service layer có thể truy vấn job, audit event,... qua ORM.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base cho mọi ORM model của ứng dụng."""


def _uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    """Bảng jobs — trạng thái chung của mọi job (P01 §5.2, §5.3)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    caller_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("caller_id", "idempotency_key", name="uq_jobs_caller_id_idempotency_key"),
    )


class AuditEvent(Base):
    """Bảng audit_events — ghi Entscheid, caller, trace_id (P01 §2, S03)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    caller_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CrawlJob(Base):
    """Bảng crawl_jobs — chi tiết job crawl (P01 §5.3, P02 §2)."""

    __tablename__ = "crawl_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requested_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    policy_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Document(Base):
    """Bảng documents — metadata tài liệu đã chuẩn hóa (P01 §5.3, P02 §2)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    markdown_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    classification_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MediaJob(Base):
    """Bảng media_jobs — job tải media (P01 §5.3, P03 §2)."""

    __tablename__ = "media_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    caller_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    policy_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    drm_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class MediaJobItem(Base):
    """Bảng media_job_items — trạng thái từng item trong batch (P01 §5.3)."""

    __tablename__ = "media_job_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    media_job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MediaAsset(Base):
    """Bảng media_assets — metadata tài sản đã tải (P01 §5.3)."""

    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class SearchRequest(Base):
    """Bảng search_requests — lịch sử truy vấn đã hash (P01 §5.3)."""

    __tablename__ = "search_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    caller_id: Mapped[str] = mapped_column(String(128), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceRegistryEntry(Base):
    """Approved-source evidence and independently gated P04 capabilities."""

    __tablename__ = "source_registry_entries"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    distribution_evidence: Mapped[str] = mapped_column(String(512), nullable=False)
    feature_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
