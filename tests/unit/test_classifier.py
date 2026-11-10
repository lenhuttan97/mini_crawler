"""Tests for document classifier (P02 Item 6).

Phân loại một document_type chính từ metadata có cấu trúc (JSON-LD, Open
Graph), mẫu nội dung/DOM, mẫu URL; caller hint chỉ là tín hiệu, không ép
classifier. Không gọi mạng thật.
"""

from __future__ import annotations

from app.features.web_crawl.application.classifier import DocumentClassifier


def test_news_article_from_json_ld_article() -> None:
    """JSON-LD @type Article => news_article, confidence cao."""
    classifier = DocumentClassifier()
    result = classifier.classify(
        title="Bài báo mẫu",
        url="https://example.com/news/bai-bao",
        html="<html><body><article>Nội dung bài báo.</article></body></html>",
        json_ld={"@type": "Article", "headline": "Bài báo mẫu"},
        caller_hint="blog_article",
    )
    assert result.document_type == "news_article"
    assert result.confidence == "high"
    assert result.needs_review is False


def test_blog_article_from_dom() -> None:
    """Trang có <article> nhưng không có JSON-LD => blog_article, trung bình."""
    classifier = DocumentClassifier()
    result = classifier.classify(
        title="Bài viết blog",
        url="https://example.com/blog/post-1",
        html="<html><body><article>Nội dung bài viết cá nhân.</article></body></html>",
        json_ld=None,
        caller_hint=None,
    )
    assert result.document_type == "blog_article"
    assert result.confidence in ("medium", "low")


def test_generic_page_no_signal() -> None:
    """Không có tín hiệu đáng tin cậy => generic_page, needs_review."""
    classifier = DocumentClassifier()
    result = classifier.classify(
        title="Trang chung",
        url="https://example.com/page",
        html="<html><body><div>Nội dung thường.</div></body></html>",
        json_ld=None,
        caller_hint=None,
    )
    assert result.document_type == "generic_page"
    assert result.needs_review is True


def test_unknown_no_content() -> None:
    """Không đủ tín hiệu => unknown, needs_review."""
    classifier = DocumentClassifier()
    result = classifier.classify(
        title=None,
        url="https://example.com/",
        html="<html><body></body></html>",
        json_ld=None,
        caller_hint=None,
    )
    assert result.document_type == "unknown"
    assert result.needs_review is True


def test_caller_hint_does_not_override() -> None:
    """Caller hint chỉ là tín hiệu, classifier vẫn phân loại độc lập."""
    classifier = DocumentClassifier()
    # HTML không có tín hiệu báo chí, caller hint là news_article =>
    # classifier vẫn phân loại độc lập, không bị ép.
    result = classifier.classify(
        title="Trang thường",
        url="https://example.com/page",
        html="<html><body><div>Nội dung thường.</div></body></html>",
        json_ld=None,
        caller_hint="news_article",
    )
    assert result.document_type != "news_article" or result.confidence == "low"
    assert result.needs_review is True


def test_classification_always_has_type_confidence_reason() -> None:
    """Kết quả luôn có một type trong taxonomy, confidence và reason."""
    classifier = DocumentClassifier()
    result = classifier.classify(
        title="T",
        url="https://example.com/x",
        html="<html><body>N</body></html>",
        json_ld=None,
        caller_hint=None,
    )
    assert result.document_type
    assert result.confidence in ("high", "medium", "low")
    assert result.classification_reason
