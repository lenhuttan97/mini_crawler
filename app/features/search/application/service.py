"""Search service — F03 Search rồi Crawl (P05 Item 1).

Gọi SearXNG qua HTTPX, chuẩn hóa/dedupe kết quả, selected-result gọi lại
crawl service F01 (không tạo crawler riêng). Search tự nó không auto-crawl.
"""

from __future__ import annotations

from typing import Any

import httpx

SAFE_SCHEMES = frozenset({"http", "https"})


class SearchQueryError(Exception):
    """Lỗi truy vấn tìm kiếm (query rỗng/quá dài,...)."""


class SearchUpstreamError(Exception):
    """Lỗi từ provider tìm kiếm (SearXNG)."""


class SearchService:
    """Tìm kiếm qua SearXNG và chọn kết quả để crawl."""

    def __init__(
        self,
        searxng_url: str,
        max_query_len: int = 200,
        crawl_service: Any = None,
    ) -> None:
        self.searxng_url = searxng_url.rstrip("/")
        self.max_query_len = max_query_len
        self.crawl_service = crawl_service
        self.crawl_jobs_created = 0

    def search(self, *, query: str, page: int = 1, limit: int = 10) -> list[dict]:
        """Tìm kiếm và trả danh sách kết quả đã chuẩn hóa (không auto-crawl)."""
        self._validate_query(query)
        url = f"{self.searxng_url}/search"
        params = {"q": query, "page": page, "limit": limit, "format": "json"}
        try:
            response = httpx.get(url, params=params, timeout=10.0)
        except httpx.RequestError as exc:  # pragma: no cover - network
            raise SearchUpstreamError(f"không kết nối được SearXNG: {exc}") from exc
        if response.status_code >= 400:
            raise SearchUpstreamError(f"SearXNG trả {response.status_code}")
        data = response.json()
        return self._normalize_results(data.get("results", []) or [], limit)

    async def crawl_selected(
        self,
        *,
        result_url: str,
        caller_id: str,
        idempotency_key: str,
    ) -> dict:
        """Chọn một kết quả search => tạo crawl job qua F01 (không crawler riêng)."""
        self._validate_url(result_url)
        result = await self._create_crawl_job(
            url=result_url, caller_id=caller_id, idempotency_key=idempotency_key
        )
        self.crawl_jobs_created += 1
        return result

    async def _create_crawl_job(self, *, url: str, caller_id: str, idempotency_key: str) -> dict:
        """Gọi crawl service F01. Có thể bị monkeypatch trong kiểm thử."""
        if self.crawl_service is None:
            raise SearchUpstreamError("chưa cấu hình crawl service F01")
        return await self.crawl_service.crawl(
            url=url, caller_id=caller_id, idempotency_key=idempotency_key
        )

    def _validate_query(self, query: str) -> None:
        if not query or not query.strip():
            raise SearchQueryError("query tìm kiếm không được để trống")
        if len(query) > self.max_query_len:
            raise SearchQueryError("query tìm kiếm quá dài")

    @staticmethod
    def _validate_url(url: str) -> None:
        if not url or "://" not in url:
            raise SearchQueryError("URL kết quả không hợp lệ")
        scheme = url.split("://", 1)[0].lower()
        if scheme not in SAFE_SCHEMES:
            raise SearchQueryError("scheme URL không được phép")

    @staticmethod
    def _normalize_results(results: list[dict], limit: int) -> list[dict]:
        seen: set[str] = set()
        normalized: list[dict] = []
        for item in results:
            link = item.get("url") or ""
            if link in seen:
                continue
            seen.add(link)
            normalized.append(
                {
                    "title": item.get("title") or "",
                    "url": link,
                    "snippet": item.get("content") or item.get("snippet") or "",
                }
            )
            if len(normalized) >= limit:
                break
        return normalized
