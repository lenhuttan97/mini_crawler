"""Tests for static fetcher (P02 Item 3).

Kiểm tra HTTPX fetch: thành công, quá kích thước, content-type không cho phép,
và redirect thủ công — dùng respx giả lập HTTP, không gọi mạng thật.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.features.web_crawl.infrastructure.static_fetcher import (
    FetchError,
    FetchResult,
    StaticFetcher,
)


def _run(coro):
    return asyncio.run(coro)


def test_fetch_success() -> None:
    """Fetch HTML thành công trả nội dung, status, content-type."""
    fetcher = StaticFetcher(max_bytes=1_000_000)
    url = "https://example.com/page"
    html = "<html><body><h1>Hello</h1></body></html>"

    with respx.mock:
        respx.get(url).mock(
            return_value=httpx.Response(
                200, text=html, headers={"content-type": "text/html; charset=utf-8"}
            )
        )
        result = _run(fetcher.fetch(url))

    assert isinstance(result, FetchResult)
    assert result.status_code == 200
    assert result.content == html.encode()
    assert result.content_type == "text/html"
    assert "example.com" in result.url


def test_fetch_oversized_blocked() -> None:
    """Response quá max_bytes bị chặn."""
    fetcher = StaticFetcher(max_bytes=10)
    url = "https://example.com/big"
    with respx.mock:
        respx.get(url).mock(
            return_value=httpx.Response(
                200, content=b"x" * 100, headers={"content-type": "text/html"}
            )
        )
        with pytest.raises(FetchError, match="oversized|size|quota|lớn"):
            _run(fetcher.fetch(url))


def test_fetch_bad_content_type_blocked() -> None:
    """Content-type không cho phép (ứng dụng/octet-stream) bị chặn."""
    fetcher = StaticFetcher(max_bytes=1_000_000)
    url = "https://example.com/file.exe"
    with respx.mock:
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                content=b"binary",
                headers={"content-type": "application/octet-stream"},
            )
        )
        with pytest.raises(FetchError, match="content type|mime|không được phép"):
            _run(fetcher.fetch(url))


def test_fetch_follows_redirect_manually() -> None:
    """Fetch tuân theo redirect thủ công, xác thực mỗi hop (không auto-follow)."""
    fetcher = StaticFetcher(max_bytes=1_000_000)
    start = "https://example.com/start"
    target = "https://example.com/final"
    html = "<html><body>Final</body></html>"

    with respx.mock:
        respx.get(start).mock(
            return_value=httpx.Response(
                302,
                headers={"location": target, "content-type": "text/html"},
            )
        )
        respx.get(target).mock(
            return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
        )
        result = _run(fetcher.fetch(start))

    assert result.status_code == 200
    assert result.content == html.encode()
    assert result.url == target


def test_fetch_redirect_to_private_ip_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect về IP private bị chặn (Policy Gate kiểm tra mỗi hop)."""
    from app.platform.network_policy.policy import PolicyDecision

    fetcher = StaticFetcher(max_bytes=1_000_000)
    start = "https://example.com/start"

    # Chặn mọi redirect qua Policy Gate
    monkeypatch.setattr(
        "app.features.web_crawl.infrastructure.static_fetcher.evaluate_policy",
        lambda cmd: PolicyDecision(False, "ssrf_private_ip", "private redirect"),
    )

    with respx.mock:
        respx.get(start).mock(
            return_value=httpx.Response(302, headers={"location": "http://10.0.0.1/internal"})
        )
        with pytest.raises(FetchError, match="private|blocked|policy|chặn"):
            _run(fetcher.fetch(start))
