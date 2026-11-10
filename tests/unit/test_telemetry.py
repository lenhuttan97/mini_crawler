"""Tests for observability logging (P00 Item 6)."""

from __future__ import annotations

from importlib import import_module


def _import_logging():
    return import_module("app.platform.observability.logging")


def test_redaction_processor_strips_secrets() -> None:
    """Redaction processor must mask secret-like keys and query tokens."""
    logging = _import_logging()
    event = {
        "event": "request",
        "authorization": "Bearer super-secret-token",
        "secret_key": "sk-1234567890",
        "password": "hunter2",
        "api_key": "key-abcdef",
        "url": "https://example.com/path?token=abc&session=xyz",
        "safe_field": "visible",
    }

    redacted = logging.redact_event(event)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["secret_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert "token=abc" not in redacted["url"]
    assert "session=xyz" not in redacted["url"]
    assert redacted["safe_field"] == "visible"


def test_correlation_id_is_bindable() -> None:
    """Correlation ID should be present and bindable via contextvars."""
    logging = _import_logging()
    cid = logging.bind_correlation_id("corr-123")
    assert logging.get_correlation_id() == "corr-123"
    assert cid == "corr-123"
    logging.clear_correlation_id()
    assert logging.get_correlation_id() is None
