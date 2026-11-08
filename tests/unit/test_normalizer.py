"""Tests for HTML normalizer/extractor (P02 Item 5).

Dùng fixture HTML do kiểm soát, không gọi mạng thật. Trích xuất title,
canonical URL, loại bỏ nhiễm (nav/ads/footer/script/style), chuyển sang
Markdown và tính content hash.
"""

from __future__ import annotations

from app.services.normalizer import normalize_html

NEWS_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Tiêu đề bài báo - Tin tức</title>
    <link rel="canonical" href="https://example.com/news/bai-bao">
    <meta property="og:title" content="Tiêu đề bài báo - Tin tức">
</head>
<body>
    <header>
        <nav><a href="/">Trang chủ</a> | <a href="/news">Tin tức</a></nav>
    </header>
    <article>
        <h1>Tiêu đề bài báo</h1>
        <p class="summary">Tóm tắt bài báo.</p>
        <div class="content">
            <p>Nội dung chính của bài báo.</p>
            <p>Đoạn thứ hai của nội dung.</p>
        </div>
        <span class="author">Nguyễn Văn A</span>
        <time datetime="2026-11-08">08/11/2026</time>
    </article>
    <footer><a href="/privacy">Bảo mật</a></footer>
    <div class="ad">Quảng cáo bên này sẽ bị loại</div>
    <script>console.log('tracking');</script>
    <style>body { margin: 0; }</style>
</body>
</html>"""


def test_extract_title_and_canonical() -> None:
    """Trích xuất tiêu đề và URL chuẩn từ HTML."""
    doc = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    assert doc.title == "Tiêu đề bài báo - Tin tức"
    assert doc.canonical_url == "https://example.com/news/bai-bao"


def test_remove_noise_elements() -> None:
    """Loại bỏ nav, footer, quảng cáo, script, style khỏi nội dung chính."""
    doc = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    lower = doc.markdown.lower()
    assert "quảng cáo bên này sẽ bị loại" not in lower
    assert "console.log" not in lower
    assert "margin: 0" not in lower
    assert "trang chủ" not in lower
    assert "bảo mật" not in lower


def test_keep_article_content() -> None:
    """Giữ lại nội dung bài báo, headline, tóm tắt, tác giả, thời điểm."""
    doc = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    lower = doc.markdown.lower()
    assert "tiêu đề bài báo" in lower
    assert "tóm tắt bài báo" in lower
    assert "nội dung chính của bài báo" in lower
    assert "nguyễn văn a" in lower


def test_content_hash_deterministic() -> None:
    """Content hash cố định cho cùng nội dung, thay đổi khi nội dung thay đổi."""
    doc1 = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    doc2 = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    assert doc1.content_hash == doc2.content_hash

    html_diff = NEWS_ARTICLE_HTML.replace("Nội dung chính", "Nội dung khác")
    doc3 = normalize_html(html_diff, "https://example.com/news/bai-bao")
    assert doc3.content_hash != doc1.content_hash


def test_extract_links() -> None:
    """Trích xuất các liên kết từ HTML."""
    doc = normalize_html(NEWS_ARTICLE_HTML, "https://example.com/news/bai-bao")
    assert "https://example.com/" in doc.links
    assert "https://example.com/news" in doc.links
