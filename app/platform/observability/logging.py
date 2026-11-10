"""Structured logging with redaction and correlation ID (P00 Item 6).

Provides JSON-structured logging via structlog, a redaction processor that
masks secret-like keys and query tokens, and a correlation ID propagated
through contextvars so every log line in a request carries the same ID.
"""

from __future__ import annotations

import re
import sys
from contextvars import ContextVar
from typing import Any

import structlog

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_SECRET_KEYS = re.compile(
    r"(?i)\b("
    r"authorization|secret|secret_key|password|api_key|apikey|"
    r"token|access_token|refresh_token|private_key|client_secret"
    r")\b"
)
_QUERY_TOKEN = re.compile(
    r"[?&]([A-Za-z_]*(?:token|session|secret|key|password|api_key)[A-Za-z_]*)=[^&]*"
)


def get_correlation_id() -> str | None:
    """Return the correlation ID bound to the current context, if any."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: str | None) -> str | None:
    """Bind a correlation ID to the current context and return it."""
    _correlation_id.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    _correlation_id.set(None)


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        if _SECRET_KEYS.search(key):
            return "[REDACTED]"
        value = _QUERY_TOKEN.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def redact_event(event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact secret-like keys and query tokens from a log event dict."""
    return {key: _redact_value(key, value) for key, value in event_dict.items()}


def _redact_event_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog-compatible wrapper around :func:`redact_event`."""
    return redact_event(event_dict)


def _add_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def configure_logging() -> None:
    """Configure structlog with JSON output, redaction, and correlation ID."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_correlation_id,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_event_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a configured structlog bound logger for the given name."""
    return structlog.get_logger(name)
