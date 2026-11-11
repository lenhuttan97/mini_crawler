"""Crawl service — orchestrator F01 (P02 Item 2).

Luồng: Policy Gate → tạo job (JobService) → fetch tĩnh (StaticFetcher) →
chuẩn hóa (Normalizer) → phân loại (Classifier) → lưu (PersistenceService).
Không để controller gọi HTTPX hoặc bộ trích xuất trực tiếp.
"""

from __future__ import annotations

from app.platform.network_policy.policy import PolicyCommand
from app.platform.persistence.enums import JobStatus


class CrawlService:
    """Điều phối toàn bộ quy trình crawl một URL."""

    def __init__(
        self,
        job_service,
        policy_gate,
        fetcher,
        normalizer,
        classifier,
        persistence,
    ) -> None:
        self._job_service = job_service
        self._policy_gate = policy_gate
        self._fetcher = fetcher
        self._normalizer = normalizer
        self._classifier = classifier
        self._persistence = persistence

    async def crawl(self, *, url: str, caller_id: str, idempotency_key: str) -> dict:
        """Crawl một URL và trả thông tin job + document.

        Nếu Policy Gate chặn, nêu ValueError và không tạo job.
        """
        # 1. Policy Gate trước mọi thao tác.
        decision = self._policy_gate.evaluate(
            PolicyCommand(url=url, action="crawl", caller_id=caller_id)
        )
        if not decision.allowed:
            raise ValueError(
                f"job bị chặn bởi chính sách: {decision.reason_code} — {decision.reason_message}"
            )

        # 2. Tạo job (idempotent qua idempotency_key trong JobService).
        job = self._job_service.create_job(
            caller_id=caller_id,
            action="crawl",
            url=url,
            idempotency_key=idempotency_key,
        )

        # 3. Fetch trang tĩnh.
        fetch_result = await self._fetcher.fetch(url)

        # 4. Chuẩn hóa HTML thành Markdown + trích xuất metadata.
        normalized = self._normalizer.normalize_html(fetch_result.content, fetch_result.url)

        # 5. Phân loại document.
        classification = self._classifier.classify(
            title=normalized.title,
            url=normalized.canonical_url or url,
            html=normalized.clean_html,
            json_ld=normalized.json_ld,
            caller_hint=None,
            content_is_sufficient=normalized.content_is_sufficient,
        )

        # 6. Lưu document (dedupe theo content_hash) và liên kết job.
        persistence_result = self._persistence.save_document(
            job_id=job.id,
            requested_url=url,
            canonical_url=normalized.canonical_url or url,
            title=normalized.title,
            markdown=normalized.markdown,
            clean_html=normalized.clean_html,
            content_hash=normalized.content_hash,
            document_type=classification.document_type,
            confidence=classification.confidence,
            classification_reason=classification.classification_reason,
            needs_review=classification.needs_review,
            summary=normalized.summary,
            authors=normalized.authors,
            published_at=normalized.published_at,
            updated_at=normalized.updated_at,
            section=normalized.section,
            language=normalized.language,
        )

        return {
            "job_id": job.id,
            "status": JobStatus.COMPLETED.value,
            "document_id": persistence_result.document_id,
            "created": persistence_result.created,
        }
