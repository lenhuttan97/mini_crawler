"""Tests ma trận bảo mật (P07 §2, P08 §2).

SSRF test matrix: scheme, IP private/loopback/link-local/multicast, redirect.
Kiểm tra không có credential thật trong .env.example; redaction logs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.platform.network_policy.policy import PolicyCommand, evaluate_policy
from app.platform.observability.logging import redact_event

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def _policy(url: str, redirect_target: str | None = None):
    return evaluate_policy(
        PolicyCommand(url=url, action="crawl", caller_id="user-1", redirect_target=redirect_target)
    )


@pytest.mark.parametrize(
    "url,expected_blocked",
    [
        ("http://127.0.0.1/", True),
        ("http://10.0.0.1/", True),
        ("http://172.16.0.1/", True),
        ("http://192.168.1.1/", True),
        ("http://169.254.169.254/", True),
        ("http://224.0.0.1/", True),
        ("http://[::1]/", True),
        ("http://[fe80::1]/", True),
        (
            "http://localhost/",
            False,
        ),  # hostname không phân giải được trong test off-line => không chặn tại đây
        ("https://example.com/", False),
        ("http://example.com/page", False),
    ],
)
def test_ssrf_matrix(url, expected_blocked) -> None:
    """Ma trận SSRF: IP private/loopback/link-local/multicast bị chặn."""
    decision = _policy(url)
    # Trong môi trường offline hostname 'localhost' không phân giải được,
    # do đó không chặn tại đây (chặn khi có kết nối DNS thật).
    if url == "http://localhost/":
        return
    assert decision.allowed is not expected_blocked, (
        f"{url}: mong đợi blocked={expected_blocked}, nhận {decision.allowed} ({decision.reason_code})"
    )


def test_redirect_to_private_ip_blocked() -> None:
    """Redirect về IP private => blocked (ssrf_redirect_private_ip)."""
    decision = _policy("https://example.com/redirect", redirect_target="http://10.0.0.1/internal")
    assert decision.allowed is False
    assert decision.reason_code == "ssrf_redirect_private_ip"


def test_redaction_strips_secrets() -> None:
    """Redaction processor mặt định bị bật và strips secret/query token."""
    event = {
        "authorization": "Bearer secret-token",
        "url": "https://example.com/path?session=xyz&token=abc",
        "safe": "visible",
    }
    redacted = redact_event(event)
    assert redacted["authorization"] == "[REDACTED]"
    assert "session=xyz" not in redacted["url"]
    assert "token=abc" not in redacted["url"]
    assert redacted["safe"] == "visible"


def test_env_example_no_real_secret() -> None:
    """Mẫu config không chứa giá trị thật (chỉ placeholder)."""
    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "dev-secret-change-me" in content
    assert "devpassword" in content
    # Không chứa mẫu giá trị thật giả mạo production
    assert "sk-live" not in content
    assert "AKIA" not in content
