"""Worker v1 durable job tables (additive to 0001_initial_schema).

Creates feature_jobs, job_commands, outbox_events, job_leases, workflow_runs,
workflow_steps and search_result_sets. Legacy tables are untouched.
Downgrade removes only this revision's tables, in reverse dependency order.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_worker_v1_jobs"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("feature_code", sa.String(length=40), nullable=False),
        sa.Column("contract_version", sa.String(length=16), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_publish"),
        sa.Column("idempotency_scope", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancellation_state", sa.String(length=32), nullable=False, server_default="none"
        ),
        sa.Column("result_reference", sa.String(length=128), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "idempotency_scope",
            "idempotency_key",
            name="uq_feature_jobs_idempotency",
        ),
    )
    op.create_index("ix_feature_jobs_feature_code", "feature_jobs", ["feature_code"])
    op.create_index("ix_feature_jobs_status", "feature_jobs", ["status"])
    op.create_index("ix_feature_jobs_next_run_at", "feature_jobs", ["next_run_at"])
    op.create_index("ix_feature_jobs_idempotency_scope", "feature_jobs", ["idempotency_scope"])
    op.create_index("ix_feature_jobs_caller_id", "feature_jobs", ["caller_id"])

    op.create_table(
        "job_commands",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("feature_job_id", sa.String(length=36), nullable=False),
        sa.Column("command_type", sa.String(length=40), nullable=False),
        sa.Column("command_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["feature_job_id"], ["feature_jobs.job_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_commands_feature_job_id", "job_commands", ["feature_job_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message_payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending_publish",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])

    op.create_table(
        "job_leases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("feature_job_id", sa.String(length=36), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["feature_job_id"], ["feature_jobs.job_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_leases_feature_job_id", "job_leases", ["feature_job_id"])
    op.create_index("ix_job_leases_lease_expires_at", "job_leases", ["lease_expires_at"])

    op.create_table(
        "workflow_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("definition_version", sa.String(length=16), nullable=False, server_default="v1"),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("child_job_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("aggregate_result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "workflow_steps",
        sa.Column("step_id", sa.String(length=36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(length=36), nullable=False),
        sa.Column("input_ref", sa.String(length=128), nullable=False),
        sa.Column("coordinator", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("child_job_id", sa.String(length=36), nullable=True),
        sa.Column("output_ref", sa.String(length=128), nullable=True),
        sa.Column("error_ref", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.run_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workflow_steps_workflow_run_id", "workflow_steps", ["workflow_run_id"])

    op.create_table(
        "search_result_sets",
        sa.Column("result_set_id", sa.String(length=36), primary_key=True),
        sa.Column("query_hash", sa.String(length=128), nullable=False),
        sa.Column("results_ref", sa.String(length=128), nullable=True),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_search_result_sets_query_hash", "search_result_sets", ["query_hash"])
    op.create_index("ix_search_result_sets_caller_id", "search_result_sets", ["caller_id"])


def downgrade() -> None:
    op.drop_table("search_result_sets")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_runs")
    op.drop_table("job_leases")
    op.drop_table("outbox_events")
    op.drop_table("job_commands")
    op.drop_table("feature_jobs")
