"""Versioned durable contracts for worker v1 jobs and queue envelopes.

Queue messages carry only four delivery fields. Typed commands and result
payloads stay durable in PostgreSQL and never cross the broker.
"""

from __future__ import annotations

import ipaddress
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Queued execution payloads use these exact feature codes in MVP v1.
MVP_FEATURE_CODES = frozenset({"search", "web_crawl"})


class QueueMessageV1(BaseModel):
    """Safe broker envelope. Only delivery metadata crosses Redis/Celery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(min_length=1)
    feature_code: str
    contract_version: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    @field_validator("feature_code")
    @classmethod
    def _validate_feature_code(cls, value: str) -> str:
        if value not in MVP_FEATURE_CODES:
            raise ValueError(f"feature_code not permitted in MVP v1: {value}")
        return value


class BaseCommand(BaseModel):
    """Common command fields. Raw URLs/queries stay durable; nothing secret here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    caller_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class SearchCommand(BaseCommand):
    """Typed input for one provider discovery execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=200)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)


class WebCrawlCommand(BaseCommand):
    """Typed input for one static crawl of a policy-approved URL."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_url: Annotated[str, Field(min_length=1, max_length=2048)]

    @field_validator("requested_url")
    @classmethod
    def _reject_private_target(cls, value: str) -> str:
        parts = urlsplit(value)
        host = parts.hostname or ""
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            addr = None
        if addr is not None and any(
            addr in net
            for net in (
                ipaddress.ip_network("127.0.0.0/8"),
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("169.254.0.0/16"),
                ipaddress.ip_network("::1/128"),
                ipaddress.ip_network("fc00::/7"),
                ipaddress.ip_network("fe80::/10"),
            )
        ):
            raise ValueError("private/loopback target is not permitted")
        return value


class ImageDownloadCommand(BaseCommand):
    """Typed input for per-item image download with quota context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_urls: list[str] = Field(min_length=1, max_length=50)


class ExecutionOutcome(BaseModel):
    """Typed feature execution result. Safe reason codes only, no payloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    result_reference: str | None = None
    reason_code: str | None = None
    error_code: str | None = None

    @classmethod
    def completed(cls, *, result_reference: str) -> ExecutionOutcome:
        return cls(status="completed", result_reference=result_reference)

    @classmethod
    def blocked(cls, *, reason_code: str) -> ExecutionOutcome:
        return cls(status="blocked_policy", reason_code=reason_code)

    @classmethod
    def failed(cls, *, error_code: str) -> ExecutionOutcome:
        return cls(status="failed", error_code=error_code)


def parse_uuid(value: Any) -> UUID:
    """Parse a durable identifier, keeping UUIDs out of queue messages."""
    return UUID(str(value))
