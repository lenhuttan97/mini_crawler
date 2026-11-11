"""Tests cho Crawl service (P02 Item 2).

Orchestrator: policy gate → tạo job (JobService) → fetch (StaticFetcher) →
chuẩn hóa (Normalizer) → phân loại (Classifier) → lưu (PersistenceService).
Tất cả dependency bị mock, không gọi mạng thật.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.web_crawl.application.service import CrawlService

JSON_LD = {"@type": "NewsArticle", "headline": "Tiêu đề"}
PUBLISHED_AT = datetime(2026, 11, 8, 9, 30, tzinfo=UTC)
UPDATED_AT = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)


def _make_service():
    job_service = MagicMock()
    job_service.create_job.return_value = MagicMock(id="job-1", status="pending")
    policy_gate = MagicMock()
    policy_gate.evaluate.return_value = MagicMock(allowed=True)
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(
        return_value=MagicMock(
            url="https://example.com/page",
            status_code=200,
            content="<html><body>Nội dung</body></html>".encode(),
            content_type="text/html",
        )
    )
    normalizer = MagicMock()
    normalizer.normalize_html.return_value = MagicMock(
        title="Tiêu đề",
        canonical_url="https://example.com/page",
        content_hash="hash-1",
        markdown="# Nội dung",
        clean_html="<article>Nội dung</article>",
        summary="Tóm tắt",
        authors=("Nguyễn Văn A",),
        published_at=PUBLISHED_AT,
        updated_at=UPDATED_AT,
        section="Kinh tế",
        language="vi",
        json_ld=JSON_LD,
        content_is_sufficient=True,
    )
    classifier = MagicMock()
    classifier.classify.return_value = MagicMock(
        document_type="news_article",
        confidence="high",
        classification_reason="json_ld:Article",
        needs_review=False,
    )
    persistence = MagicMock()
    persistence.save_document.return_value = MagicMock(document_id="doc-1", created=True)
    return CrawlService(
        job_service=job_service,
        policy_gate=policy_gate,
        fetcher=fetcher,
        normalizer=normalizer,
        classifier=classifier,
        persistence=persistence,
    ), {
        "job_service": job_service,
        "policy_gate": policy_gate,
        "fetcher": fetcher,
        "normalizer": normalizer,
        "classifier": classifier,
        "persistence": persistence,
    }


def test_crawl_success_full_flow() -> None:
    """Luồng crawl thành công: policy → job → fetch → normalize → classify → persist."""
    service, deps = _make_service()
    result = asyncio.run(
        service.crawl(
            url="https://example.com/page",
            caller_id="user-1",
            idempotency_key="idem-1",
        )
    )

    # Policy gate được gọi trước mọi thứ
    deps["policy_gate"].evaluate.assert_called_once()
    # Tạo job
    deps["job_service"].create_job.assert_called_once()
    # Fetch, normalize, classify, persist
    deps["fetcher"].fetch.assert_awaited_once()
    deps["normalizer"].normalize_html.assert_called_once()
    deps["classifier"].classify.assert_called_once()
    deps["persistence"].save_document.assert_called_once()

    assert result["job_id"] == "job-1"
    assert result["status"] == "completed"
    assert result["document_id"] == "doc-1"


def test_crawl_blocked_by_policy() -> None:
    """Policy chặn => không tạo job, không fetch, nêu lý do."""
    service, deps = _make_service()
    deps["policy_gate"].evaluate.return_value = MagicMock(
        allowed=False, reason_code="ssrf_private_ip", reason_message="IP private"
    )

    with pytest.raises(Exception, match="chính sách|blocked|policy"):
        asyncio.run(
            service.crawl(
                url="http://127.0.0.1/",
                caller_id="user-1",
                idempotency_key="idem-2",
            )
        )

    deps["job_service"].create_job.assert_not_called()
    deps["fetcher"].fetch.assert_not_called()


def test_crawl_idempotency_same_key() -> None:
    """Cùng idempotency_key => tạo job một lần (JobService idempotent)."""
    service, deps = _make_service()
    asyncio.run(
        service.crawl(url="https://example.com/p", caller_id="user-1", idempotency_key="idem-3")
    )
    asyncio.run(
        service.crawl(url="https://example.com/p", caller_id="user-1", idempotency_key="idem-3")
    )
    assert deps["job_service"].create_job.call_count == 2  # JobService xử lý idempotency nội bộ


def test_crawl_passes_json_ld_and_quality_to_classifier() -> None:
    """Classifier nhận JSON-LD đã trích và cờ chất lượng nội dung."""
    service, deps = _make_service()
    asyncio.run(
        service.crawl(
            url="https://example.com/page",
            caller_id="user-1",
            idempotency_key="idem-4",
        )
    )

    kwargs = deps["classifier"].classify.call_args.kwargs
    assert kwargs["json_ld"] == JSON_LD
    assert kwargs["content_is_sufficient"] is True


def test_crawl_maps_all_article_metadata_to_persistence() -> None:
    """Mọi metadata bài viết được map tường minh sang persistence."""
    service, deps = _make_service()
    asyncio.run(
        service.crawl(
            url="https://example.com/page",
            caller_id="user-1",
            idempotency_key="idem-5",
        )
    )

    saved = deps["persistence"].save_document.call_args.kwargs
    assert saved["summary"] == "Tóm tắt"
    assert saved["authors"] == ("Nguyễn Văn A",)
    assert saved["published_at"] == PUBLISHED_AT
    assert saved["updated_at"] == UPDATED_AT
    assert saved["section"] == "Kinh tế"
    assert saved["language"] == "vi"
    assert saved["clean_html"] == "<article>Nội dung</article>"
