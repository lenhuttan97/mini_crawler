"""Contracts for worker v1 workflows and job intents (P01/P02).

Workflow Orchestration is the only component allowed to create downstream
JobIntents. These tests pin the frozen boundary between caller intent, the
workflow graph, and durable feature-job handoff.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.shared.contracts.workflows import (
    MVP_WORKFLOW_TYPES,
    JobIntent,
    WorkflowRequest,
    WorkflowRun,
)


def test_workflow_request_holds_only_safe_caller_context() -> None:
    """A request carries type, URL/query, budget, and redacted caller context."""
    request = WorkflowRequest(
        workflow_type="search_and_extract",
        url_or_query="từ khóa test",
        output_goal="documents",
        child_job_budget=3,
        idempotency_key="idem-1",
        caller_context={"caller_id": "user-1"},
    )
    assert request.workflow_type == "search_and_extract"
    assert request.child_job_budget == 3
    assert request.browser_permission is False
    assert request.caller_context == {"caller_id": "user-1"}


def test_workflow_request_rejects_unregistered_type() -> None:
    """Media, recursive, or scheduled workflow types are rejected in MVP v1."""
    with pytest.raises(ValidationError):
        WorkflowRequest(
            workflow_type="extract_images",
            url_or_query="https://example.com/page",
            idempotency_key="idem-1",
        )


def test_workflow_request_rejects_browser_permission_in_mvp() -> None:
    """Browser action is not a permitted MVP v1 step."""
    with pytest.raises(ValidationError):
        WorkflowRequest(
            workflow_type="crawl_url",
            url_or_query="https://example.com/page",
            browser_permission=True,
            idempotency_key="idem-1",
        )


def test_job_intent_references_durable_command_not_payload() -> None:
    """A JobIntent points at a durable command ref, never the raw command itself."""
    intent = JobIntent(
        feature_code="web_crawl",
        command_ref="cmd-1",
        workflow_run_id="run-1",
        workflow_step_id="step-1",
        idempotency_scope="scope-1",
        idempotency_key="idem-1",
        caller_id="user-1",
        correlation_id="corr-1",
    )
    assert intent.feature_code == "web_crawl"
    assert intent.command_ref == "cmd-1"


def test_job_intent_rejects_unsupported_feature_code() -> None:
    """Image/Video intents are not created by MVP v1 workflow definitions."""
    with pytest.raises(ValidationError):
        JobIntent(
            feature_code="image_download",
            command_ref="cmd-1",
            workflow_run_id="run-1",
            idempotency_scope="scope-1",
            idempotency_key="idem-1",
            caller_id="user-1",
            correlation_id="corr-1",
        )


def test_workflow_run_starts_pending_and_accumulates_children() -> None:
    """A run begins pending and records child job IDs immutably."""
    run = WorkflowRun(definition_version="v1", state="pending")
    assert run.state == "pending"
    assert run.child_job_ids == []

    updated = run.add_child("job-1")
    assert updated.run_id == run.run_id
    assert updated.child_job_ids == ["job-1"]
    # Original is immutable.
    assert run.child_job_ids == []


def test_mvp_workflow_types_are_bounded() -> None:
    """Only search, crawl_url, and search_and_extract are executable in MVP v1."""
    assert MVP_WORKFLOW_TYPES == {"search", "crawl_url", "search_and_extract"}
