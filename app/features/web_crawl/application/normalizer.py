"""HTML normalizer/extractor (P02 Item 5).

Chọn một content root (article/main/role=main/body), trích metadata bài viết
có cấu trúc (JSON-LD, OpenGraph, meta, DOM), loại bỏ nhiễm (nav, header,
footer, aside, quảng cáo, related, share, comment...), chuyển thành Markdown
và tính content hash. Không gọi mạng thật.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import markdownify
from selectolax.parser import HTMLParser

# JSON-LD @type được coi là bài viết có metadata đáng tin cậy.
ARTICLE_TYPES = frozenset(
    {
        "Article",
        "NewsArticle",
        "BlogPosting",
        "LiveBlogPosting",
        "TechArticle",
        "ScholarlyArticle",
        "Report",
        "Review",
    }
)

# Tag cấu trúc không bao giờ thuộc nội dung bài viết.
STRUCTURAL_NOISE_TAGS = frozenset(
    {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"}
)

# Token class/id/aria-label đánh dấu boilerplate; match theo token, không substring.
NOISE_TOKENS = frozenset(
    {
        "ad",
        "ads",
        "advert",
        "advertisement",
        "sponsor",
        "sponsored",
        "share",
        "sharing",
        "social",
        "related",
        "recommended",
        "recommendation",
        "newsletter",
        "subscribe",
        "subscription",
        "comment",
        "comments",
        "pagination",
        "pager",
        "breadcrumb",
        "breadcrumbs",
        "tag",
        "tags",
        "cookie",
        "cookies",
        "banner",
        "popup",
        "modal",
        "promo",
        "sidebar",
    }
)

TEXT_BLOCK_TAGS = frozenset({"p", "li", "blockquote", "pre", "figcaption", "td"})

MIN_CONTENT_CHARS = 200
MIN_TEXT_BLOCKS = 2

_MISSING = "missing"
_CONFLICT = "conflict"


@dataclass(frozen=True)
class NormalizedDocument:
    """Kết quả chuẩn hóa một trang HTML."""

    title: str | None
    canonical_url: str | None
    content_hash: str
    markdown: str
    clean_html: str
    summary: str | None = None
    authors: tuple[str, ...] = ()
    published_at: datetime | None = None
    updated_at: datetime | None = None
    section: str | None = None
    language: str | None = None
    json_ld: dict | None = None
    content_is_sufficient: bool = True


def normalize_html(html: str, base_url: str) -> NormalizedDocument:
    """Chuẩn hóa HTML thành document LLM-ready.

    Trả về article body (Markdown + HTML sạch), metadata thực có và content
    hash (SHA-256 của Markdown). Metadata thiếu/mâu thuẫn để trống.
    """
    parser = HTMLParser(html)
    json_ld_items = _collect_json_ld_items(parser)
    root = _select_content_root(parser)

    found, title = _json_ld_field(
        json_ld_items, lambda item: _clean_text(item.get("headline") or item.get("name"))
    )
    if not found:
        title = _first_text(
            _meta_content(parser, property_="og:title"),
            _first_text_in(root, "h1"),
            _first_text_in(parser, "h1"),
            _first_text_in(parser, "title"),
        )

    found, summary = _json_ld_field(
        json_ld_items, lambda item: _clean_text(item.get("description"))
    )
    if not found:
        summary = _first_text(
            _meta_content(parser, property_="og:description"),
            _meta_content(parser, name="description"),
            _first_text_in(root, "p"),
        )

    found, authors = _json_ld_authors(json_ld_items)
    if not found:
        authors = _fallback_authors(parser, root)

    found, published_at = _json_ld_datetime(json_ld_items, "datePublished")
    if not found:
        published_at = _parse_datetime(
            _meta_content(parser, property_="article:published_time")
        ) or _first_datetime(root)

    found, updated_at = _json_ld_datetime(json_ld_items, "dateModified")
    if not found:
        updated_at = _parse_datetime(_meta_content(parser, property_="article:modified_time"))

    found, section = _json_ld_field(
        json_ld_items, lambda item: _clean_text(_first_of(item.get("articleSection")))
    )
    if not found:
        section = _clean_text(_meta_content(parser, property_="article:section"))

    canonical_url = _canonical_url(parser, base_url)
    language = _clean_text(_attribute(parser.css_first("html"), "lang"))

    _prune_root(root)
    clean_html = root.html or ""
    markdown = markdownify.markdownify(clean_html)
    content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    return NormalizedDocument(
        title=title,
        canonical_url=canonical_url,
        content_hash=content_hash,
        markdown=markdown,
        clean_html=clean_html,
        summary=summary,
        authors=authors,
        published_at=published_at,
        updated_at=updated_at,
        section=section,
        language=language,
        json_ld=json_ld_items[0] if json_ld_items else None,
        content_is_sufficient=_content_is_sufficient(root),
    )


def _walk_json_ld(data):
    if isinstance(data, list):
        for entry in data:
            yield from _walk_json_ld(entry)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for entry in graph:
                yield from _walk_json_ld(entry)


def _collect_json_ld_items(parser: HTMLParser) -> list[dict]:
    items: list[dict] = []
    for node in parser.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text() or "")
        except (ValueError, TypeError):
            continue
        for item in _walk_json_ld(data):
            if _article_type(item) in ARTICLE_TYPES:
                items.append(item)
    return items


def _article_type(item: dict) -> str | None:
    value = item.get("@type")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, str) else None


def _json_ld_field(items: list[dict], extractor) -> tuple[bool, str | None]:
    """Trả (có nguồn JSON-LD?, giá trị). Mâu thuẫn trả (True, None) để không fallback."""
    values = {value for item in items if (value := extractor(item))}
    if len(values) > 1:
        return True, None
    return (True, values.pop()) if values else (False, None)


def _json_ld_authors(items: list[dict]) -> tuple[bool, tuple[str, ...]]:
    values = {names for item in items if (names := _author_names(item.get("author")))}
    if len(values) > 1:
        return True, ()
    return (True, values.pop()) if values else (False, ())


def _json_ld_datetime(items: list[dict], key: str) -> tuple[bool, datetime | None]:
    values = {
        parsed
        for item in items
        if (parsed := _parse_datetime(item.get(key))) is not None
    }
    if len(values) > 1:
        return True, None
    return (True, values.pop()) if values else (False, None)


def _author_names(value) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    elif isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for entry in value:
        name = entry.get("name") if isinstance(entry, dict) else entry
        cleaned = _clean_text(name)
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return tuple(names)


def _parse_datetime(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _select_content_root(parser: HTMLParser):
    for selector in ("article", "main", '[role="main"]'):
        candidates = parser.css(selector)
        if candidates:
            return max(candidates, key=lambda node: _non_space_length(node.text()))
    return parser.css_first("body") or parser.root


def _prune_root(root) -> None:
    for node in list(root.css("*")):
        if node is root:
            continue
        if _is_noise_element(node):
            node.decompose()


def _is_noise_element(node) -> bool:
    return str(node.tag) in STRUCTURAL_NOISE_TAGS or bool(_node_tokens(node) & NOISE_TOKENS)


def _node_tokens(node) -> set[str]:
    attributes = node.attributes
    raw = " ".join(
        filter(None, (attributes.get("class"), attributes.get("id"), attributes.get("aria-label")))
    )
    return set(re.split(r"[^a-z0-9]+", raw.lower())) - {""}


def _content_is_sufficient(root) -> bool:
    if _non_space_length(root.text()) < MIN_CONTENT_CHARS:
        return False
    blocks = [
        node
        for node in root.css("*")
        if str(node.tag) in TEXT_BLOCK_TAGS and _clean_text(node.text())
    ]
    return len(blocks) >= MIN_TEXT_BLOCKS


def _canonical_url(parser: HTMLParser, base_url: str) -> str | None:
    href = _attribute(parser.css_first('link[rel="canonical"]'), "href")
    return urljoin(base_url, href) if href else None


def _fallback_authors(parser: HTMLParser, root) -> tuple[str, ...]:
    meta_author = _clean_text(
        _attribute(parser.css_first('meta[name="author"]'), "content")
    )
    if meta_author:
        return (meta_author,)
    for selector in ('[rel="author"]', ".author", ".byline"):
        author = _first_text_in(root, selector)
        if author:
            return (author,)
    return ()


def _first_datetime(root) -> datetime | None:
    node = root.css_first("time[datetime]")
    return _parse_datetime(_attribute(node, "datetime"))


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _first_text_in(root, selector: str, *, attribute: str | None = None) -> str | None:
    node = root.css_first(selector) if root is not None else None
    if node is None:
        return None
    return _clean_text(_attribute(node, attribute)) if attribute else _clean_text(node.text())


def _first_of(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _meta_content(parser: HTMLParser, *, property_: str | None = None, name: str | None = None):
    if property_:
        node = parser.css_first(f'meta[property="{property_}"]')
        if node is not None:
            return _clean_text(_attribute(node, "content"))
    if name:
        node = parser.css_first(f'meta[name="{name}"]')
        if node is not None:
            return _clean_text(_attribute(node, "content"))
    return None


def _attribute(node, name: str) -> str | None:
    return node.attributes.get(name) if node is not None else None


def _non_space_length(text: str | None) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None
