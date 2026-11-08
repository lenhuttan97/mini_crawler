"""Tests cho Crawl service (P02 Item 2).

Orchestrator: policy gate → tạo job (JobService) → fetch (StaticFetcher) →
chuẩn hóa (Normalizer) → phân loại (Classifier) → lưu (PersistenceService).
Tất cả dependency bị mock, không gọi mạng thật.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.crawl_service import CrawlService


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
        links=[],
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
