"""Tests cho persistence layer (P02 Item 7).

Lưu document vào PostgreSQL (documents, crawl_jobs) và Markdown/raw HTML vào
MinIO (StorageAdapter bị mock). Dedupe theo content hash: cùng nội dung không
tạo document trùng.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.document_storage.service import PersistenceResult, PersistenceService
from app.platform.persistence.models import Base, Document


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
    )

    assert isinstance(result, PersistenceResult)
    assert result.document_id is not None
    assert result.created is True
    # Upload Markdown và raw HTML
    assert storage.upload_object.call_count == 2
    # Truy vấn lại document
    doc = db_session.get(Document, result.document_id)
    assert doc is not None
    assert doc.title == "Tiêu đề"
    assert doc.content_hash == "hash-123"


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
