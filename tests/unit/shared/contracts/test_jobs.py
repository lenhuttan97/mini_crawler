"""Contracts for worker v1 durable commands and safe queue envelopes (P01/P02).

These tests pin the frozen serialization boundary: queue messages carry only
the four delivery fields, commands stay durable, and outcome references are
safe identifiers — never raw URLs, queries, cookies, or tokens.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.shared.contracts.jobs import (
    ExecutionOutcome,
    ImageDownloadCommand,
    QueueMessageV1,
    SearchCommand,
    WebCrawlCommand,
)


def test_queue_message_v1_serializes_only_four_fields() -> None:
    """A queue envelope carries exactly job_id, feature_code, contract_version, correlation_id."""
    message = QueueMessageV1(
        job_id="job-1",
        feature_code="search",
        contract_version="v1",
        correlation_id="corr-1",
    )
    data = message.model_dump()
    assert set(data.keys()) == {"job_id", "feature_code", "contract_version", "correlation_id"}
    assert data["job_id"] == "job-1"
    assert data["feature_code"] == "search"
    assert data["contract_version"] == "v1"
    assert data["correlation_id"] == "corr-1"


def test_queue_message_v1_rejects_extra_fields() -> None:
    """Unknown fields must not be accepted in a queue envelope."""
    with pytest.raises(ValidationError):
        QueueMessageV1(
            job_id="job-1",
            feature_code="search",
            contract_version="v1",
            correlation_id="corr-1",
            url="https://example.com/",
        )


def test_queue_message_v1_can_round_trip_json() -> None:
    """JSON serialization must preserve all four fields and nothing else."""
    message = QueueMessageV1(
        job_id="job-1",
        feature_code="web_crawl",
        contract_version="v1",
        correlation_id="corr-1",
    )
    restored = QueueMessageV1.model_validate_json(message.model_dump_json())
    assert restored == message


def test_search_command_holds_only_typed_query_context() -> None:
    """Search command holds query/page/limit plus redacted caller context, no provider internals."""
    command = SearchCommand(
        query="từ khóa test",
        page=1,
        limit=10,
        caller_id="user-1",
        idempotency_key="idem-1",
    )
    assert command.query == "từ khóa test"
    assert command.page == 1
    assert command.limit == 10
    assert command.caller_id == "user-1"
    assert command.idempotency_key == "idem-1"


def test_search_command_rejects_empty_query() -> None:
    """An empty query is invalid and must not be durable."""
    with pytest.raises(ValidationError):
        SearchCommand(
            query="",
            page=1,
            limit=10,
            caller_id="user-1",
            idempotency_key="idem-1",
        )


def test_web_crawl_command_holds_only_approved_url_and_caller() -> None:
    """Crawl command holds the requested URL and redacted caller context."""
    command = WebCrawlCommand(
        requested_url="https://example.com/page",
        caller_id="user-1",
        idempotency_key="idem-1",
    )
    assert str(command.requested_url) == "https://example.com/page"
    assert command.caller_id == "user-1"


def test_web_crawl_command_rejects_private_target() -> None:
    """A command targeting a private IP is rejected at the contract boundary."""
    with pytest.raises(ValidationError):
        WebCrawlCommand(
            requested_url="http://127.0.0.1/internal",
            caller_id="user-1",
            idempotency_key="idem-1",
        )


def test_image_command_holds_per_item_urls() -> None:
    """Image download command holds per-item URLs and caller/quota context."""
    command = ImageDownloadCommand(
        source_urls=["https://example.com/a.png", "https://example.com/b.png"],
        caller_id="user-1",
        idempotency_key="idem-1",
    )
    assert len(command.source_urls) == 2


def test_execution_outcome_completed_uses_safe_reference() -> None:
    """A completed outcome exposes only a safe result reference, never raw URLs."""
    outcome = ExecutionOutcome.completed(result_reference="doc-1")
    assert outcome.status == "completed"
    assert outcome.result_reference == "doc-1"
    assert outcome.reason_code is None


def test_execution_outcome_blocked_uses_safe_reason_code() -> None:
    """A blocked outcome carries a safe reason code and no payload."""
    outcome = ExecutionOutcome.blocked(reason_code="ssrf_private_ip")
    assert outcome.status == "blocked_policy"
    assert outcome.reason_code == "ssrf_private_ip"
    assert outcome.result_reference is None


def test_execution_outcome_failed_records_transient_error() -> None:
    """A failed outcome carries a safe error code for retry classification."""
    outcome = ExecutionOutcome.failed(error_code="timeout")
    assert outcome.status == "failed"
    assert outcome.error_code == "timeout"
