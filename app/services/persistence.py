"""Persistence layer (P02 Item 7).

Lưu document vào PostgreSQL (documents, crawl_jobs) và Markdown/raw HTML vào
MinIO qua StorageAdapter. Dedupe theo content_hash: cùng nội dung không tạo
document trùng. Object key do server tạo (UUID), không suy từ tiêu đề người dùng.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.adapters.storage import StorageAdapter
from app.domain.models import CrawlJob, Document


def _object_key(prefix: str) -> str:
    return f"{prefix}/{uuid.uuid4()}"


@dataclass(frozen=True)
class PersistenceResult:
    """Kết quả lưu document."""

    document_id: str
    created: bool


class PersistenceService:
    """Lưu document và liên kết với crawl job."""

    def __init__(self, session, storage: StorageAdapter) -> None:
        self._session = session
        self._storage = storage

    def save_document(
        self,
        *,
        job_id: str,
        requested_url: str,
        canonical_url: str,
        title: str | None,
        markdown: str,
        clean_html: str,
        content_hash: str,
        document_type: str | None,
        confidence: str | None,
        classification_reason: str | None,
        needs_review: bool,
    ) -> PersistenceResult:
        """Lưu document (dedupe theo content_hash) và upload Markdown/raw HTML."""
        # Dedupe: nội dung đã có → trả lại document hiện có, không upload lại.
        existing = self._session.query(Document).filter_by(content_hash=content_hash).first()
        if existing is not None:
            self._link_job_to_document(job_id, existing.id)
            return PersistenceResult(document_id=existing.id, created=False)

        # Tạo object key phía server (không suy từ title do người dùng).
        markdown_key = _object_key("documents/markdown")
        html_key = _object_key("documents/html")

        # Lỗi upload không đánh completed; StorageError sẽ lan truyền và
        # document không được tạo.
        self._storage.upload_object(
            bucket="documents",
            key=markdown_key,
            data=markdown.encode("utf-8"),
            content_type="text/markdown",
        )
        self._storage.upload_object(
            bucket="documents",
            key=html_key,
            data=clean_html.encode("utf-8"),
            content_type="text/html",
        )

        document = Document(
            canonical_url=canonical_url,
            title=title,
            content_hash=content_hash,
            markdown_key=markdown_key,
            document_type=document_type,
            confidence=confidence,
            classification_reason=classification_reason,
            needs_review=needs_review,
        )
        self._session.add(document)
        self._session.flush()

        self._link_job_to_document(job_id, document.id)

        return PersistenceResult(document_id=document.id, created=True)

    def _link_job_to_document(self, job_id: str, document_id: str) -> None:
        """Đảm bảo có hàng crawl_jobs cho job_id (tạo mới nếu chưa có)."""
        crawl_job = self._session.get(CrawlJob, job_id)
        if crawl_job is None:
            crawl_job = CrawlJob(
                job_id=job_id,
                requested_url="",
                canonical_url="",
            )
            self._session.add(crawl_job)
        self._session.flush()
