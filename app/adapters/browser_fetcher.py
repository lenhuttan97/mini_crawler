"""Browser fallback fetcher (P02 Item 4).

Stub-offline: đọc fixture HTML từ thư mục cục bộ thay vì chạy Playwright thật,
để kiểm thử đơn giản không cần cài browser binary. Khi triển khai thật,
thay bằng Crawl4AI/Playwright với action recipe đã review (xem
docs/plan/03-f01-crawl-url.md và docs/sample/mini_crawler_implementation_plan.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchResult:
    """Kết quả fetch từ browser fallback."""

    url: str
    status_code: int
    content: str
    content_type: str = "text/html"


class BrowserFetcher:
    """Fetch trang cần JavaScript bằng cách đọc fixture cục bộ (stub)."""

    def __init__(self, fixture_dir: str) -> None:
        self.fixture_dir = fixture_dir

    def fetch(self, url: str, caller_script: str | None = None) -> FetchResult:
        """Fetch URL. Từ chối caller_script (JavaScript/selector do caller/LLM cung cấp)."""
        if caller_script is not None:
            raise ValueError("không nhận JavaScript/selector từ caller hoặc LLM")
        # Ánh xạ URL -> tên tệp fixture (lấy hostname + path, thay '/' bằng '_')
        safe = url.replace("://", "_").replace("/", "_").replace("?", "_")
        path = os.path.join(self.fixture_dir, f"{safe}.html")
        if not os.path.exists(path):
            raise FileNotFoundError(f"fixture không tồn tại: {path}")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        return FetchResult(url=url, status_code=200, content=content)
