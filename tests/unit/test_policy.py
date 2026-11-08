"""Tests for Policy Gate (P01 Item 3).

Kiểm tra chính sách URL/SSRF không cần gọi mạng thật: scheme, user-info,
IP private/loopback/link-local/multicast, port, redirect.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from app.core.policy import PolicyCommand, evaluate_policy


def test_allowed_http_and_https() -> None:
    """http/https đến host công khai được phép."""
    for url in ("https://example.com/page", "http://example.org/resource"):
        decision = evaluate_policy(PolicyCommand(url=url, action="crawl", caller_id="user-1"))
        assert decision.allowed is True
        assert decision.reason_code is None


def test_blocked_dangerous_schemes() -> None:
    """file:, data:, javascript: và các scheme khác bị chặn."""
    for url in (
        "file:///etc/passwd",
        "data:text/html,<script>",
        "javascript:alert(1)",
        "ftp://example.com/file",
        "gopher://example.com",
    ):
        decision = evaluate_policy(PolicyCommand(url=url, action="crawl", caller_id="user-1"))
        assert decision.allowed is False
        assert decision.reason_code == "scheme_not_allowed"


def test_blocked_user_info() -> None:
    """URL chứa user-info (user:pass@host) bị chặn."""
    decision = evaluate_policy(
        PolicyCommand(
            url="http://user:secret@example.com/page",
            action="crawl",
            caller_id="user-1",
        )
    )
    assert decision.allowed is False
    assert decision.reason_code == "scheme_not_allowed"


def test_blocked_private_ipv4() -> None:
    """Các địa chỉ IPv4 private/loopback/link-local bị chặn."""
    for url in (
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",
        "http://224.0.0.1/",
        "http://0.0.0.0/",
    ):
        decision = evaluate_policy(PolicyCommand(url=url, action="crawl", caller_id="user-1"))
        assert decision.allowed is False, url
        assert decision.reason_code == "ssrf_private_ip", url


def test_blocked_private_ipv6() -> None:
    """IPv6 loopback/link-local/multicast bị chặn."""
    for url in (
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[ff02::1]/",
    ):
        decision = evaluate_policy(PolicyCommand(url=url, action="crawl", caller_id="user-1"))
        assert decision.allowed is False, url
        assert decision.reason_code == "ssrf_private_ip", url


def test_blocked_localhost_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hostname 'localhost' phân giải về loopback => bị chặn."""
    with patch(
        "app.core.policy.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    ):
        decision = evaluate_policy(
            PolicyCommand(url="http://localhost/", action="crawl", caller_id="user-1")
        )
        assert decision.allowed is False
        assert decision.reason_code == "ssrf_private_ip"


def test_blocked_redirect_to_private_ip() -> None:
    """URL chính là public nhưng redirect về IP private => bị chặn."""
    decision = evaluate_policy(
        PolicyCommand(
            url="http://example.com/redirect",
            action="crawl",
            caller_id="user-1",
            redirect_target="http://10.0.0.1/internal",
        )
    )
    assert decision.allowed is False
    assert decision.reason_code == "ssrf_redirect_private_ip"


def test_allowed_public_domain() -> None:
    """Tên miền công khai không trỏ IP private được phép."""
    with patch(
        "app.core.policy.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    ):
        decision = evaluate_policy(
            PolicyCommand(url="http://example.com/", action="crawl", caller_id="user-1")
        )
        assert decision.allowed is True
        assert decision.reason_code is None
