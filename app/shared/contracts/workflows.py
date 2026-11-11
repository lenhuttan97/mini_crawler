"""Versioned durable contracts for worker v1 workflows and job intents.

Workflow Orchestration is the only component allowed to create downstream
JobIntents. Callers supply a WorkflowRequest; the orchestrator resolves it to
bounded feature jobs through registered, versioned definitions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.contracts.jobs import MVP_FEATURE_CODES

MVP_WORKFLOW_TYPES = frozenset({"search", "crawl_url", "search_and_extract"})


class WorkflowRequest(BaseModel):
    """Caller intent for an explicit bounded workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_type: str = Field(min_length=1)
    url_or_query: str = Field(min_length=1)
    output_goal: str | None = None
    requested_depth: int = Field(default=1, ge=1, le=1)
    child_job_budget: int = Field(default=5, ge=0, le=20)
    browser_permission: bool = False
    caller_context: dict[str, Any] | None = None
    idempotency_key: str = Field(min_length=1)

    @field_validator("workflow_type")
    @classmethod
    def _validate_workflow_type(cls, value: str) -> str:
        if value not in MVP_WORKFLOW_TYPES:
            raise ValueError(f"workflow type not permitted in MVP v1: {value}")
        return value

    @field_validator("browser_permission")
    @classmethod
    def _reject_browser_permission_in_mvp(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("browser action is not permitted in MVP v1")
        return value


class JobIntent(BaseModel):
    """Mapping from a workflow step to a feature job. Created only by Workflow Orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_code: str
    command_ref: str  # durable reference to JobCommand, not the payload itself
    workflow_run_id: str
    workflow_step_id: str | None = None
    idempotency_scope: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    caller_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    caller_context: dict[str, Any] | None = None

    @field_validator("feature_code")
    @classmethod
    def _validate_feature_code(cls, value: str) -> str:
        if value not in MVP_FEATURE_CODES:
            raise ValueError(f"feature_code not permitted in MVP v1: {value}")
        return value


class WorkflowRun(BaseModel):
    """Durable parent record for one workflow execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    definition_version: str = Field(min_length=1)
    state: str = Field(default="pending")
    child_job_ids: list[str] = Field(default_factory=list)
    aggregate_result: dict[str, Any] | None = None

    def add_child(self, job_id: str) -> WorkflowRun:
        return WorkflowRun(
            run_id=self.run_id,
            definition_version=self.definition_version,
            state=self.state,
            child_job_ids=[*self.child_job_ids, job_id],
            aggregate_result=self.aggregate_result,
        )


def parse_uuid(value: Any) -> UUID:
    """Parse a durable identifier, keeping UUIDs out of queue messages."""
    return UUID(str(value))
