"""HTML normalizer/extractor (P02 Item 5).

Trích xuất tiêu đề, URL chuẩn, nội dung chính từ HTML; loại bỏ nhiễm
(nav, footer, quảng cáo, script, style); chuyển thành Markdown và tính
content hash. Không gọi mạng thật.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import urljoin

import markdownify
from selectolax.parser import HTMLParser

# Phần tử/lớp CSS được coi là nhiễm và loại bỏ khỏi nội dung chính.
NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header nav",
    ".ad",
    ".ads",
    ".advertisement",
    ".advert",
    ".sidebar",
    ".related",
    ".share",
]


@dataclass(frozen=True)
class NormalizedDocument:
    """Kết quả chuẩn hóa một trang HTML."""

    title: str | None
    canonical_url: str | None
    content_hash: str
    markdown: str
    clean_html: str
    links: list[str]


def normalize_html(html: str, base_url: str) -> NormalizedDocument:
    """Chuẩn hóa HTML thành document LLM-ready.

    Trả về title, URL chuẩn, Markdown nội dung chính, HTML sạch, danh sách
    liên kết và content hash (SHA-256 của Markdown).
    """
    parser = HTMLParser(html)

    # 1. Tiêu đề từ thẻ <title>.
    title_node = parser.css_first("title")
    title = title_node.text(strip=True) if title_node is not None else None

    # 2. URL chuẩn từ <link rel="canonical">.
    canonical_url = None
    canonical_node = parser.css_first('link[rel="canonical"]')
    if canonical_node is not None:
        href = canonical_node.attributes.get("href")
        if href:
            canonical_url = urljoin(base_url, href)

    # 3. Trích xuất tất cả liên kết (trước khi lo nhiễm, để giữ liên kết dẫn
    #    ra ngoài nội dung chính).
    links: list[str] = []
    for a in parser.css("a[href]"):
        href = a.attributes.get("href")
        if href:
            links.append(urljoin(base_url, href))

    # 4. Loại bỏ các phần tử nhiễm.
    for selector in NOISE_SELECTORS:
        for node in parser.css(selector):
            node.decompose()

    # 5. HTML sạch và chuyển sang Markdown.
    clean_html = parser.html
    markdown = markdownify.markdownify(clean_html)

    # 6. Content hash (SHA-256 của Markdown).
    content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    return NormalizedDocument(
        title=title,
        canonical_url=canonical_url,
        content_hash=content_hash,
        markdown=markdown,
        clean_html=clean_html,
        links=links,
    )
