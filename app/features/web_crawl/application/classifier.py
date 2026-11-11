"""Document classifier (P02 Item 6).

Gán một document_type chính từ metadata có cấu trúc (JSON-LD, Open Graph),
mẫu nội dung/DOM, mẫu URL; caller hint chỉ là tín hiệu, không overriding.
Ưu tiên: structured metadata → DOM/content pattern → URL pattern → caller hint.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

TAXONOMY = frozenset(
    {
        "news_article",
        "learning_material",
        "course_page",
        "technical_documentation",
        "api_reference",
        "academic_article",
        "blog_article",
        "book_chapter",
        "listing_page",
        "navigation_page",
        "media_page",
        "generic_page",
        "unknown",
    }
)

# JSON-LD @type → document_type (confidence high).
JSONLD_TYPE_MAP = {
    "Article": "news_article",
    "NewsArticle": "news_article",
    "BlogPosting": "blog_article",
    "LiveBlogPosting": "blog_article",
    "TechArticle": "technical_documentation",
    "ScholarlyArticle": "academic_article",
    "Course": "course_page",
    "CourseInstance": "course_page",
    "LearningResource": "learning_material",
    "Book": "book_chapter",
    "Clip": "media_page",
    "Episode": "media_page",
}

# URL pattern → document_type (confidence medium).
URL_PATTERNS = [
    (r"/news/", "news_article"),
    (r"/blog/", "blog_article"),
    (r"/docs/", "technical_documentation"),
    (r"/documentation/", "technical_documentation"),
    (r"/api/", "api_reference"),
    (r"/course/", "course_page"),
    (r"/category/", "listing_page"),
    (r"/tag/", "listing_page"),
    (r"/archive/", "listing_page"),
    (r"/media/", "media_page"),
    (r"/video/", "media_page"),
]


@dataclass(frozen=True)
class ClassificationResult:
    """Kết quả phân loại một document."""

    document_type: str
    confidence: str
    classification_reason: str
    needs_review: bool


class DocumentClassifier:
    """Phân loại document vào một type trong taxonomy MVP."""

    def classify(
        self,
        *,
        title: str | None,
        url: str,
        html: str,
        json_ld: dict | list | None,
        caller_hint: str | None = None,
        content_is_sufficient: bool = True,
    ) -> ClassificationResult:
        # Nội dung trích xuất không đủ: không dùng metadata/URL để đoán bài báo.
        if not content_is_sufficient:
            text = re.sub(r"<[^>]+>", "", html or "")
            return ClassificationResult(
                document_type="generic_page" if text.strip() else "unknown",
                confidence="low",
                classification_reason="insufficient_content",
                needs_review=True,
            )

        # Ưu tiên 1: structured metadata (JSON-LD / Open Graph).
        result = self._from_structured_metadata(json_ld)
        if result is not None:
            return result

        # Ưu tiên 2: DOM/content pattern.
        result = self._from_dom(html, title)
        if result is not None:
            return result

        # Ưu tiên 3: URL pattern.
        result = self._from_url(url)
        if result is not None:
            return result

        # Ưu tiên 4: caller hint (chỉ là tín hiệu, confidence thấp, needs_review).
        if caller_hint and caller_hint in TAXONOMY:
            return ClassificationResult(
                document_type=caller_hint,
                confidence="low",
                classification_reason="caller_hint",
                needs_review=True,
            )

        # Fallback: unknown nếu không có tiêu đề và nội dung, ngược lại generic_page.
        text = re.sub(r"<[^>]+>", "", html or "")
        has_title = bool(title and title.strip())
        has_content = bool(text.strip())
        if not has_title and not has_content:
            return ClassificationResult(
                document_type="unknown",
                confidence="low",
                classification_reason="no_signal",
                needs_review=True,
            )
        return ClassificationResult(
            document_type="generic_page",
            confidence="low",
            classification_reason="no_signal",
            needs_review=True,
        )

    def _from_structured_metadata(self, json_ld):
        if not json_ld:
            return None
        data = json_ld
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                return None
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            return None
        jtype = data.get("@type") or data.get("type")
        if isinstance(jtype, list):
            jtype = jtype[0]
        if not isinstance(jtype, str):
            return None
        mapped = JSONLD_TYPE_MAP.get(jtype)
        if mapped:
            return ClassificationResult(
                document_type=mapped,
                confidence="high",
                classification_reason=f"json_ld:{jtype}",
                needs_review=False,
            )
        return None

    def _from_dom(self, html: str, title: str | None):
        html_lower = (html or "").lower()
        if "<article" in html_lower:
            has_time = "<time" in html_lower or "datetime" in html_lower
            has_author = "author" in html_lower or "byline" in html_lower
            dtype = "news_article" if (has_time or has_author) else "blog_article"
            return ClassificationResult(
                document_type=dtype,
                confidence="medium",
                classification_reason="dom:article",
                needs_review=False,
            )
        if "<nav" in html_lower:
            return ClassificationResult(
                document_type="navigation_page",
                confidence="low",
                classification_reason="dom:nav",
                needs_review=True,
            )
        return None

    def _from_url(self, url: str):
        url_lower = (url or "").lower()
        for pattern, dtype in URL_PATTERNS:
            if re.search(pattern, url_lower):
                return ClassificationResult(
                    document_type=dtype,
                    confidence="medium",
                    classification_reason=f"url:{pattern}",
                    needs_review=False,
                )
        return None
