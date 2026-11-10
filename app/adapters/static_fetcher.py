"""Static fetcher cho trang HTML/JSON (P02 Item 3).

Dùng HTTPX streaming: timeout, giới hạn kích thước, content-type allowlist,
và tuân theo redirect thủ công (mỗi hop được Policy Gate xác thực) thay vì
auto-follow. Không gọi mạng trong unit test (dùng respx giả lập).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.platform.network_policy.policy import PolicyCommand, evaluate_policy


class FetchError(Exception):
    """Lỗi khi fetch trang tĩnh (quá kích thước, content-type không cho phép, SSRF redirect...)."""


@dataclass(frozen=True)
class FetchResult:
    """Kết quả fetch một trang tĩnh."""

    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    content_type: str


# Content-type cho phép crawl (trang web, JSON API, văn bản thuần).
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "application/json",
        "text/plain",
    }
)


class StaticFetcher:
    """Fetch trang tĩnh qua HTTPX, không auto-follow redirect."""

    def __init__(
        self,
        max_bytes: int = 5_000_000,
        timeout: float = 30.0,
        max_redirects: int = 5,
    ) -> None:
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.max_redirects = max_redirects

    async def fetch(self, url: str) -> FetchResult:
        """Fetch URL, theo dõi redirect thủ công và xác thực mỗi hop qua Policy Gate."""
        current_url = url
        for _ in range(self.max_redirects + 1):
            result = await self._fetch_once(current_url)
            if result.status_code in (301, 302, 303, 307, 308):
                location = result.headers.get("location") or result.headers.get("Location")
                if not location:
                    raise FetchError("redirect không có trường Location")
                next_url = urljoin(current_url, location)
                decision = evaluate_policy(
                    PolicyCommand(url=next_url, action="crawl", caller_id="system")
                )
                if not decision.allowed:
                    raise FetchError(f"redirect bị chặn bởi chính sách: {decision.reason_code}")
                current_url = next_url
                continue
            return result
        raise FetchError("quá nhiều redirect")

    async def _fetch_once(self, url: str) -> FetchResult:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.get(url)

            # Kiểm tra Content-Length header trước khi đọc body.
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > self.max_bytes:
                        raise FetchError(
                            f"response quá lớn: {content_length} bytes > {self.max_bytes}"
                        )
                except ValueError:
                    pass

            # Bỏ qua kiểm tra content-type cho phản hồi redirect (3xx).
            is_redirect = response.status_code in (301, 302, 303, 307, 308)
            if not is_redirect:
                content_type = self._parse_content_type(response.headers.get("content-type", ""))
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise FetchError(f"content type không được phép: {content_type}")
            else:
                content_type = ""

            # Đọc body stream với giới hạn max_bytes.
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > self.max_bytes:
                    raise FetchError(f"response quá lớn: vượt quá {self.max_bytes} bytes")
                chunks.append(chunk)
            content = b"".join(chunks)

            return FetchResult(
                url=str(response.url),
                status_code=response.status_code,
                headers=dict(response.headers),
                content=content,
                content_type=content_type,
            )

    @staticmethod
    def _parse_content_type(header: str) -> str:
        return header.split(";")[0].strip().lower()
