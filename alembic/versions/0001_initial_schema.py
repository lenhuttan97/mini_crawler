"""Initial schema for Mini Crawler (P01 Item 2).

Tạo các bảng cốt lõi mô tả ở implementation-plan.md §5.3:
jobs, audit_events, crawl_jobs, documents, media_jobs, media_job_items,
media_assets, search_requests.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "caller_id", "idempotency_key", name="uq_jobs_caller_id_idempotency_key"
        ),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_caller_id", "audit_events", ["caller_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "crawl_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("requested_url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("policy_status", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_crawl_jobs_canonical_url", "crawl_jobs", ["canonical_url"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("markdown_key", sa.String(length=512), nullable=True),
        sa.Column("document_type", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("classification_reason", sa.String(length=128), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])

    op.create_table(
        "media_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("policy_status", sa.String(length=32), nullable=True),
        sa.Column("drm_status", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_media_jobs_status", "media_jobs", ["policy_status"])
    op.create_index("ix_media_jobs_idempotency_key", "media_jobs", ["idempotency_key"])

    op.create_table(
        "media_job_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("media_job_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["media_job_id"], ["media_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_media_job_items_media_job_id_sequence",
        "media_job_items",
        ["media_job_id", "sequence"],
        unique=True,
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_media_assets_checksum", "media_assets", ["checksum"])
    op.create_index("ix_media_assets_object_key", "media_assets", ["object_key"])

    op.create_table(
        "source_registry_entries",
        sa.Column("domain", sa.String(length=255), primary_key=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("distribution_evidence", sa.String(length=512), nullable=False),
        sa.Column("feature_flags", sa.JSON(), nullable=False),
        sa.Column("review_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "search_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("query_hash", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_search_requests_created_at", "search_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("search_requests")
    op.drop_table("source_registry_entries")
    op.drop_table("media_assets")
    op.drop_table("media_job_items")
    op.drop_table("media_jobs")
    op.drop_table("documents")
    op.drop_table("crawl_jobs")
    op.drop_table("audit_events")
    op.drop_table("jobs")
