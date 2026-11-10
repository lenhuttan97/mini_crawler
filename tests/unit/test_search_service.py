"""Tests cho search service (P05 Item 1).

Gọi SearXNG qua respx (giả lập), chuẩn hóa/dedupe kết quả, selected-result
goi crawl service F01. Không gọi mạng thật.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.features.search.application.service import (
    SearchQueryError,
    SearchService,
    SearchUpstreamError,
)


def test_search_valid_returns_normalized_results() -> None:
    """Truy vấn hợp lệ => danh sách kết quả đã chuẩn hóa, không lộ raw payload."""
    service = SearchService(searxng_url="https://searx.example.com")
    with respx.mock:
        route = respx.get("https://searx.example.com/search")
        route.mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Kết quả A",
                            "url": "https://example.com/a",
                            "content": "snippet A",
                            "engine": "engine1",
                        },
                        {
                            "title": "Kết quả A trùng",
                            "url": "https://example.com/a",
                            "content": "snippet A",
                            "engine": "engine2",
                        },
                        {
                            "title": "Kết quả B",
                            "url": "https://example.com/b",
                            "content": "snippet B",
                            "engine": "engine1",
                        },
                    ]
                },
            )
        )
        results = service.search(query="từ khóa test", page=1, limit=10)

    assert len(results) == 2  # dedupe URL
    assert results[0]["title"] == "Kết quả A"
    assert results[0]["url"] == "https://example.com/a"
    assert results[1]["url"] == "https://example.com/b"
    # Không lộ raw provider payload (không có field engine nội bộ)
    assert "engine" not in results[0]


def test_search_query_too_long_raises() -> None:
    """Query quá dài => SearchQueryError, không gọi provider."""
    service = SearchService(searxng_url="https://searx.example.com", max_query_len=50)
    with pytest.raises(SearchQueryError, match="quá dài|length"):
        service.search(query="x" * 100, page=1, limit=10)


def test_search_upstream_error_raises() -> None:
    """SearXNG lỗi 5xx => SearchUpstreamError."""
    service = SearchService(searxng_url="https://searx.example.com")
    with respx.mock:
        respx.get("https://searx.example.com/search").mock(
            return_value=httpx.Response(502, text="bad gateway")
        )
        with pytest.raises(SearchUpstreamError):
            service.search(query="từ khóa", page=1, limit=10)


def test_search_empty_query_raises() -> None:
    """Query rỗng => SearchQueryError."""
    service = SearchService(searxng_url="https://searx.example.com")
    with pytest.raises(SearchQueryError, match="trống|empty|quá dài|length"):
        service.search(query="", page=1, limit=10)


def test_crawl_selected_calls_crawl_service() -> None:
    """Chọn kết quả => gọi crawl service F01, không tạo crawler riêng."""
    assert inspect.iscoroutinefunction(SearchService.crawl_selected)

    crawl_service = AsyncMock()
    crawl_service.crawl.return_value = {"job_id": "job-1"}
    service = SearchService(searxng_url="https://searx.example.com", crawl_service=crawl_service)

    result = asyncio.run(
        service.crawl_selected(
            result_url="https://example.com/a",
            caller_id="user-1",
            idempotency_key="sel-1",
        )
    )

    crawl_service.crawl.assert_awaited_once_with(
        url="https://example.com/a", caller_id="user-1", idempotency_key="sel-1"
    )
    assert result["job_id"] == "job-1"


def test_search_not_auto_crawl() -> None:
    """Truy vấn search tự nó không tạo CrawlJob (chỉ khi crawl_selected)."""
    service = SearchService(searxng_url="https://searx.example.com")
    with respx.mock:
        respx.get("https://searx.example.com/search").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"title": "A", "url": "https://example.com/a", "content": "s"}]},
            )
        )
        service.search(query="từ khóa", page=1, limit=10)
    assert service.crawl_jobs_created == 0
