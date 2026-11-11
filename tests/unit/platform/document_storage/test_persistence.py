"""Tests cho persistence layer (P02 Item 7).

Lưu document vào PostgreSQL (documents, crawl_jobs) và Markdown/raw HTML vào
MinIO (StorageAdapter bị mock). Dedupe theo content hash: cùng nội dung không
tạo document trùng.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.asset_storage.storage import StorageError
from app.platform.document_storage.service import (
    PersistenceResult,
    PersistenceService,
    confirm_pending_document_uploads,
    rollback_pending_document_uploads,
)
from app.platform.persistence.models import Base, Document

ARTICLE = {
    "summary": "Tóm tắt bài báo.",
    "authors": ("Nguyễn Văn A", "Trần Thị B"),
    "published_at": datetime(2026, 11, 8, 9, 30, tzinfo=UTC),
    "updated_at": datetime(2026, 11, 9, 10, 0, tzinfo=UTC),
    "section": "Kinh tế",
    "language": "vi",
}


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "persist.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def test_save_document_creates_row_and_uploads(db_session) -> None:
    """Lưu document tạo hàng documents + crawl_jobs, upload Markdown lên MinIO."""
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(
        bucket="bucket", key="md/uuid-1", size=100, content_type="text/markdown", etag="abc"
    )
    service = PersistenceService(session=db_session, storage=storage)

    result = service.save_document(
        job_id="job-1",
        requested_url="https://example.com/page",
        canonical_url="https://example.com/page",
        title="Tiêu đề",
        markdown="# Nội dung",
        clean_html="<article>Nội dung</article>",
        content_hash="hash-123",
        document_type="news_article",
        confidence="high",
        classification_reason="json_ld:Article",
        needs_review=False,
        **ARTICLE,
    )

    assert isinstance(result, PersistenceResult)
    assert result.document_id is not None
    assert result.created is True
    # Upload Markdown và article HTML
    assert storage.upload_object.call_count == 2
    # Truy vấn lại document
    doc = db_session.get(Document, result.document_id)
    assert doc is not None
    assert doc.title == "Tiêu đề"
    assert doc.content_hash == "hash-123"
    assert doc.summary == "Tóm tắt bài báo."
    assert doc.authors == ["Nguyễn Văn A", "Trần Thị B"]
    assert doc.published_at.replace(tzinfo=None) == datetime(2026, 11, 8, 9, 30)
    assert doc.updated_at.replace(tzinfo=None) == datetime(2026, 11, 9, 10, 0)
    assert doc.section == "Kinh tế"
    assert doc.language == "vi"
    assert doc.markdown_key.startswith("documents/markdown/")
    assert doc.article_html_key.startswith("documents/html/")


def test_save_document_dedupe_by_content_hash(db_session) -> None:
    """Cùng content hash không tạo document trùng."""
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(
        bucket="bucket", key="md/x", size=1, content_type="t", etag="e"
    )
    service = PersistenceService(session=db_session, storage=storage)

    service.save_document(
        job_id="job-1",
        requested_url="https://example.com/p",
        canonical_url="https://example.com/p",
        title="T",
        markdown="# N",
        clean_html="<p>N</p>",
        content_hash="same-hash",
        document_type="generic_page",
        confidence="low",
        classification_reason="no_signal",
        needs_review=True,
    )
    result2 = service.save_document(
        job_id="job-2",
        requested_url="https://example.com/q",
        canonical_url="https://example.com/q",
        title="T2",
        markdown="# N2",
        clean_html="<p>N2</p>",
        content_hash="same-hash",
        document_type="generic_page",
        confidence="low",
        classification_reason="no_signal",
        needs_review=True,
    )

    assert result2.created is False
    assert result2.document_id is not None  # trả về document đã có
    assert db_session.query(Document).filter_by(content_hash="same-hash").count() == 1


def _save_kwargs(**overrides):
    values = {
        "job_id": "job-1",
        "requested_url": "https://example.com/page",
        "canonical_url": "https://example.com/page",
        "title": "Tiêu đề",
        "markdown": "# Nội dung",
        "clean_html": "<article>Nội dung</article>",
        "content_hash": "hash-1",
        "document_type": "news_article",
        "confidence": "high",
        "classification_reason": "json_ld:Article",
        "needs_review": False,
    }
    values.update(overrides)
    return values


def test_second_upload_failure_deletes_first_object(db_session) -> None:
    """Upload HTML lỗi thì object Markdown đã upload bị xoá, lỗi gốc vẫn lan truyền."""
    storage = MagicMock()
    storage.upload_object.side_effect = [MagicMock(), StorageError("html upload failed")]
    service = PersistenceService(session=db_session, storage=storage)

    with pytest.raises(StorageError):
        service.save_document(**_save_kwargs())

    markdown_key = storage.upload_object.call_args_list[0].kwargs["key"]
    storage.delete_object.assert_called_once_with(bucket="documents", key=markdown_key)
    assert db_session.query(Document).count() == 0


def test_flush_failure_deletes_all_uploaded_objects(db_session) -> None:
    """Flush DB lỗi thì xoá cả hai object đã upload và re-raise lỗi gốc."""
    storage = MagicMock()
    service = PersistenceService(session=db_session, storage=storage)
    db_session.autoflush = False
    db_session.flush = MagicMock(side_effect=RuntimeError("flush failed"))

    with pytest.raises(RuntimeError, match="flush failed"):
        service.save_document(**_save_kwargs())

    uploaded_keys = {call.kwargs["key"] for call in storage.upload_object.call_args_list}
    deleted_keys = {call.kwargs["key"] for call in storage.delete_object.call_args_list}
    assert uploaded_keys == deleted_keys
    assert len(uploaded_keys) == 2


def test_dedupe_does_not_upload_or_register_cleanup(db_session) -> None:
    """Dedupe không upload mới và không tạo bản ghi cleanup."""
    storage = MagicMock()
    service = PersistenceService(session=db_session, storage=storage)
    service.save_document(**_save_kwargs())
    confirm_pending_document_uploads(db_session)
    storage.reset_mock()

    result = service.save_document(**_save_kwargs(job_id="job-2"))

    assert result.created is False
    storage.upload_object.assert_not_called()
    rollback_pending_document_uploads(db_session)
    storage.delete_object.assert_not_called()


def test_rollback_deletes_each_pending_object_once(db_session) -> None:
    """Rollback xoá từng object đã upload đúng một lần, gọi lại không xoá thêm."""
    storage = MagicMock()
    service = PersistenceService(session=db_session, storage=storage)
    service.save_document(**_save_kwargs())
    keys = [call.kwargs["key"] for call in storage.upload_object.call_args_list]

    rollback_pending_document_uploads(db_session)
    assert [call.kwargs["key"] for call in storage.delete_object.call_args_list] == keys

    storage.delete_object.reset_mock()
    rollback_pending_document_uploads(db_session)
    storage.delete_object.assert_not_called()


def test_confirm_clears_pending_uploads_without_deleting(db_session) -> None:
    """Commit thành công thì bỏ registry, không xoá object."""
    storage = MagicMock()
    service = PersistenceService(session=db_session, storage=storage)
    service.save_document(**_save_kwargs())

    confirm_pending_document_uploads(db_session)
    rollback_pending_document_uploads(db_session)

    storage.delete_object.assert_not_called()
