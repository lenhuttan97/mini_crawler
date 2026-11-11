"""Persistence layer (P02 Item 7).

Lưu document vào PostgreSQL (documents, crawl_jobs) và Markdown/article HTML
vào MinIO qua StorageAdapter. Dedupe theo content_hash: cùng nội dung không
tạo document trùng. Object key do server tạo (UUID), không suy từ tiêu đề.

Object đã upload được ghi nhận trên session hiện tại; transaction owner gọi
`confirm_pending_document_uploads` sau commit hoặc
`rollback_pending_document_uploads` khi huỷ để không để lại object mồ côi.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.platform.asset_storage.storage import StorageAdapter
from app.platform.persistence.models import CrawlJob, Document

_PENDING_UPLOADS = "pending_document_uploads"
_BUCKET = "documents"


def _object_key(prefix: str) -> str:
    return f"{prefix}/{uuid.uuid4()}"


def _pending_uploads(session) -> list[tuple[StorageAdapter, str, str]]:
    return session.info.setdefault(_PENDING_UPLOADS, [])


def confirm_pending_document_uploads(session) -> None:
    """Commit đã thành công: bỏ registry, giữ nguyên object."""
    session.info.pop(_PENDING_UPLOADS, None)


def rollback_pending_document_uploads(session) -> None:
    """Xoá mọi object đã upload trong transaction thất bại (idempotent)."""
    for storage, bucket, key in session.info.pop(_PENDING_UPLOADS, []):
        with contextlib.suppress(Exception):  # cleanup không được che lỗi gốc
            storage.delete_object(bucket=bucket, key=key)


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
        summary: str | None = None,
        authors: tuple[str, ...] = (),
        published_at: datetime | None = None,
        updated_at: datetime | None = None,
        section: str | None = None,
        language: str | None = None,
    ) -> PersistenceResult:
        """Lưu document (dedupe theo content_hash) và upload Markdown/article HTML."""
        # Dedupe: nội dung đã có → trả lại document hiện có, không upload lại.
        existing = self._session.query(Document).filter_by(content_hash=content_hash).first()
        if existing is not None:
            self._link_job_to_document(job_id, existing.id)
            return PersistenceResult(document_id=existing.id, created=False)

        # Tạo object key phía server (không suy từ title do người dùng).
        markdown_key = _object_key("documents/markdown")
        html_key = _object_key("documents/html")

        try:
            self._upload(markdown_key, markdown.encode("utf-8"), "text/markdown")
            self._upload(html_key, clean_html.encode("utf-8"), "text/html")

            document = Document(
                canonical_url=canonical_url,
                title=title,
                summary=summary,
                authors=list(authors),
                published_at=published_at,
                updated_at=updated_at,
                section=section,
                language=language,
                content_hash=content_hash,
                markdown_key=markdown_key,
                article_html_key=html_key,
                document_type=document_type,
                confidence=confidence,
                classification_reason=classification_reason,
                needs_review=needs_review,
            )
            self._session.add(document)
            self._session.flush()

            self._link_job_to_document(job_id, document.id)
        except Exception:
            rollback_pending_document_uploads(self._session)
            raise

        return PersistenceResult(document_id=document.id, created=True)

    def _upload(self, key: str, data: bytes, content_type: str) -> None:
        """Upload một object và ghi nhận để có thể xoá nếu transaction thất bại."""
        self._storage.upload_object(bucket=_BUCKET, key=key, data=data, content_type=content_type)
        _pending_uploads(self._session).append((self._storage, _BUCKET, key))

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
