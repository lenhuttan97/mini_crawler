"""Tests for HTML normalizer/extractor (P02 Item 5).

Dùng fixture HTML do kiểm soát, không gọi mạng thật. Trích xuất metadata bài
viết có cấu trúc, chọn đúng một content root, loại bỏ nhiễm (nav/ads/footer,
related/share/comment...), chuyển sang Markdown và tính content hash.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from app.features.web_crawl.application.normalizer import normalize_html

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

METADATA_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Tiêu đề trang - Tin tức</title>
    <meta property="og:title" content="Tiêu đề OpenGraph">
    <meta property="og:description" content="Tóm tắt OpenGraph.">
    <meta property="article:section" content="Lĩnh vực OpenGraph">
    <link rel="canonical" href="/news/bai-bao">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      "headline": "Tiêu đề JSON-LD",
      "description": "Tóm tắt JSON-LD.",
      "author": [
        {"@type": "Person", "name": "Nguyễn Văn A"},
        {"@type": "Person", "name": "Trần Thị B"}
      ],
      "datePublished": "2026-11-08T09:30:00+07:00",
      "dateModified": "2026-11-09T10:00:00Z",
      "articleSection": "Kinh tế"
    }
    </script>
</head>
<body>
    <article>
        <h1>Tiêu đề H1</h1>
        <p>Đoạn nội dung thứ nhất đủ dài để vượt qua ngưỡng chất lượng của bộ trích
        xuất nội dung bài viết, bao gồm đủ thông tin mô tả cho một bài báo thực tế.</p>
        <p>Đoạn nội dung thứ hai cũng đủ dài để bài viết được coi là có nội dung
        chính hợp lệ và có thể được phân loại đáng tin cậy.</p>
    </article>
</body>
</html>"""

GRAPH_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Tiêu đề trang</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {"@type": "Organization", "name": "Toà soạn"},
        {"@type": "NewsArticle", "headline": "Tiêu đề Graph",
         "author": [{"@type": "Person", "name": "Nguyễn Văn A"},
                    {"@type": "Person", "name": "Trần Thị B"}],
         "datePublished": "2026-11-08T09:30:00Z"}
      ]
    }
    </script>
</head>
<body>
    <article>
        <p>Đoạn thứ nhất của bài viết trong graph đủ dài để vượt qua ngưỡng chất lượng.</p>
        <p>Đoạn thứ hai của bài viết trong graph cũng đủ dài để có nội dung hợp lệ.</p>
    </article>
</body>
</html>"""

CONFLICT_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Tiêu đề trang</title>
    <script type="application/ld+json">
    [
      {"@type": "NewsArticle", "headline": "Tiêu đề A", "datePublished": "2026-01-01T00:00:00Z"},
      {"@type": "NewsArticle", "headline": "Tiêu đề B", "datePublished": "2026-01-01T00:00:00Z"}
    ]
    </script>
</head>
<body>
    <article>
        <h1>Tiêu đề H1</h1>
        <p>Đoạn thứ nhất của bài viết đủ dài để vượt qua ngưỡng chất lượng nội dung.</p>
        <p>Đoạn thứ hai của bài viết cũng đủ dài để bài viết có nội dung hợp lệ.</p>
    </article>
</body>
</html>"""

HIERARCHY_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Trang báo - Tin tức</title>
    <link rel="canonical" href="https://example.com/news/bai-bao">
</head>
<body>
    <header>
        <h1>Tiêu đề site</h1>
        <nav><a href="/">Trang chủ</a> | <a href="/news">Tin tức</a></nav>
    </header>
    <main>
        <article class="teaser">
            <h2>Teaser headline</h2>
            <p>Teaser paragraph.</p>
            <a href="/teaser">Teaser link</a>
        </article>
        <article class="story">
            <h1>Real headline</h1>
            <p>Đoạn mở đầu của bài báo thật, đủ dài để được xem là nội dung chính
            có ý nghĩa và không bị nhầm với teaser hay navigation của trang.</p>
            <figure>
                <img src="/anh.jpg" alt="Ảnh minh hoạ">
                <figcaption>Chú thích ảnh</figcaption>
            </figure>
            <p>Đoạn thứ hai của bài báo, có <a href="/in-article">liên kết trong bài</a>
            và tiếp tục cung cấp đủ nội dung cho bài viết.</p>
            <table><tr><td>Ô bảng</td></tr></table>
            <pre><code>print("x")</code></pre>
            <blockquote>Trích dẫn</blockquote>
            <aside>Aside content</aside>
            <div class="related">Related content <a href="/related">Related link</a></div>
            <div class="share">Share content <a href="/share">Share link</a></div>
            <div class="newsletter">Newsletter content</div>
            <section class="comments">Comment content</section>
            <div class="tags"><a href="/tag/x">Tag</a></div>
            <nav class="pagination"><a href="/page/2">Next</a></nav>
        </article>
    </main>
    <footer>Footer <a href="/privacy">Privacy</a></footer>
</body>
</html>"""

MALFORMED_JSON_LD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Short</title>
    <script type="application/ld+json">{not-json</script>
</head>
<body>
    <article>
        <h1>Short</h1>
        <p>Chỉ một đoạn ngắn.</p>
    </article>
</body>
</html>"""

ONE_LONG_PARAGRAPH_HTML = """<!DOCTYPE html>
<html lang="vi">
<head><title>Một đoạn</title></head>
<body>
    <article>
        <p>""" + ("Nội dung dài nhưng chỉ nằm trong một đoạn văn duy nhất. " * 6) + """</p>
    </article>
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


def test_structured_metadata_takes_precedence() -> None:
    """JSON-LD có ưu tiên cao nhất cho title/summary/author/date/section."""
    doc = normalize_html(METADATA_HTML, "https://example.com/news/bai-bao")

    assert doc.title == "Tiêu đề JSON-LD"
    assert doc.summary == "Tóm tắt JSON-LD."
    assert doc.authors == ("Nguyễn Văn A", "Trần Thị B")
    assert doc.published_at == datetime(
        2026, 11, 8, 9, 30, tzinfo=timezone(timedelta(hours=7))
    )
    assert doc.updated_at == datetime(2026, 11, 9, 10, 0, tzinfo=UTC)
    assert doc.section == "Kinh tế"
    assert doc.language == "vi"
    assert doc.canonical_url == "https://example.com/news/bai-bao"
    assert doc.json_ld is not None
    assert doc.json_ld["headline"] == "Tiêu đề JSON-LD"
    assert doc.content_is_sufficient is True


def test_conflicting_json_ld_values_leave_fields_unset() -> None:
    """Nhiều JSON-LD Article mâu thuẫn: field mâu thuẫn bị để trống, không đoán."""
    doc = normalize_html(CONFLICT_HTML, "https://example.com/news/bai-bao")

    assert doc.title is None
    assert doc.published_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert doc.json_ld is not None
    assert doc.json_ld["headline"] == "Tiêu đề A"


def test_json_ld_graph_items_are_collected() -> None:
    """JSON-LD dạng @graph vẫn trích được Article và metadata."""
    doc = normalize_html(GRAPH_HTML, "https://example.com/news/bai-bao")

    assert doc.title == "Tiêu đề Graph"
    assert doc.authors == ("Nguyễn Văn A", "Trần Thị B")
    assert doc.published_at == datetime(2026, 11, 8, 9, 30, tzinfo=UTC)


def test_selects_article_body_and_removes_boilerplate() -> None:
    """Chọn article lớn nhất, bỏ teaser và các khối boilerplate trong bài."""
    doc = normalize_html(HIERARCHY_HTML, "https://example.com/news/bai-bao")
    lower = doc.markdown.lower()

    assert "real headline" in lower
    assert "đoạn mở đầu của bài báo thật" in lower
    assert "chú thích ảnh" in lower
    assert "ô bảng" in lower
    assert "print" in lower
    assert "trích dẫn" in lower
    assert "liên kết trong bài" in lower

    for boilerplate in (
        "teaser headline",
        "teaser paragraph",
        "aside content",
        "related content",
        "share content",
        "newsletter content",
        "comment content",
        "footer",
        "trang chủ",
        "privacy",
    ):
        assert boilerplate not in lower
    for url in ("/teaser", "/related", "/share", "/tag/x", "/page/2", "/privacy"):
        assert url not in lower


def test_malformed_json_ld_is_ignored_and_short_content_flagged() -> None:
    """JSON-LD hỏng bị bỏ qua; nội dung quá ngắn không đủ chất lượng."""
    doc = normalize_html(MALFORMED_JSON_LD_HTML, "https://example.com/news/x")

    assert doc.json_ld is None
    assert doc.title == "Short"
    assert doc.content_is_sufficient is False


def test_one_long_text_block_is_not_sufficient() -> None:
    """Một đoạn văn dài duy nhất vẫn không đủ điều kiện nội dung bài."""
    doc = normalize_html(ONE_LONG_PARAGRAPH_HTML, "https://example.com/news/x")

    assert doc.content_is_sufficient is False


def test_content_hash_ignores_boilerplate_changes() -> None:
    """Hash chỉ đổi khi nội dung bài đổi, không đổi khi boilerplate đổi."""
    doc1 = normalize_html(HIERARCHY_HTML, "https://example.com/news/bai-bao")
    doc2 = normalize_html(HIERARCHY_HTML, "https://example.com/news/bai-bao")
    assert doc1.content_hash == doc2.content_hash

    boilerplate_changed = HIERARCHY_HTML.replace("Related content", "Related content mới")
    doc3 = normalize_html(boilerplate_changed, "https://example.com/news/bai-bao")
    assert doc3.content_hash == doc1.content_hash

    body_changed = HIERARCHY_HTML.replace("Real headline", "Real headline mới")
    doc4 = normalize_html(body_changed, "https://example.com/news/bai-bao")
    assert doc4.content_hash != doc1.content_hash
