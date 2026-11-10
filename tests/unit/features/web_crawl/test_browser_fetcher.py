"""Tests for browser fallback fetcher (P02 Item 4).

Dùng fixture local giả lập, không gọi mạng thật, không cần browser binary thật.
"""

from __future__ import annotations

import pytest

from app.features.web_crawl.infrastructure.browser_fetcher import BrowserFetcher, FetchResult


def test_browser_fetcher_returns_fixture_content(tmp_path) -> None:
    """Browser fetcher đọc fixture HTML từ tệp cục bộ, trả FetchResult."""
    html = "<html><body><h1>Rendered by JS</h1></body></html>"
    fixture = tmp_path / "https_example.com_js-page.html"
    fixture.write_text(html, encoding="utf-8")

    fetcher = BrowserFetcher(fixture_dir=str(tmp_path))
    result = fetcher.fetch("https://example.com/js-page")

    assert isinstance(result, FetchResult)
    assert result.url == "https://example.com/js-page"
    assert result.status_code == 200
    assert "Rendered by JS" in result.content


def test_browser_fetcher_rejects_caller_js(tmp_path) -> None:
    """Không nhận JavaScript/selector tùy ý từ caller hoặc LLM."""
    fetcher = BrowserFetcher(fixture_dir=str(tmp_path))
    with pytest.raises(ValueError, match="script|selector|caller"):
        fetcher.fetch(
            "https://example.com/x",
            caller_script="alert(1)",
        )


def test_browser_fetcher_missing_raises(tmp_path) -> None:
    """Fixture không tồn tại => nêu lỗi rõ ràng."""
    fetcher = BrowserFetcher(fixture_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        fetcher.fetch("https://example.com/missing")
