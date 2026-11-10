"""Tests cho supporting features (P06 S01/S02/S04).

Authorization ownership, retry classification transient/blocked, document
library list phân trang. Không gọi mạng thật.
"""

from __future__ import annotations

import pytest

from app.legacy.support.authorization import AuthorizationService, OwnershipDenied
from app.legacy.support.document_library import DocumentLibrary
from app.platform.queue_management.retry import RetryService


def test_authorization_owner_allowed() -> None:
    """Caller sở hữu tài nguyên => được phép."""
    auth = AuthorizationService()
    assert auth.check_ownership(resource_owner="user-A", caller_id="user-A") is True


def test_authorization_denied_other_caller() -> None:
    """Caller khác => OwnershipDenied."""
    auth = AuthorizationService()
    with pytest.raises(OwnershipDenied):
        auth.check_ownership(resource_owner="user-A", caller_id="user-B")


def test_authorization_denied_no_owner() -> None:
    """Tài nguyên không có owner => từ chối."""
    auth = AuthorizationService()
    with pytest.raises(OwnershipDenied):
        auth.check_ownership(resource_owner=None, caller_id="user-A")


def test_retry_transient_error() -> None:
    """Lỗi tạm thời (timeout, upstream) => retry."""
    service = RetryService()
    assert service.should_retry(Exception("timeout")) is True
    assert service.should_retry(Exception("upstream error")) is True


def test_retry_blocked_error_not_retry() -> None:
    """Lỗi blocked_* => không retry."""
    service = RetryService()
    assert service.should_retry(Exception("blocked_policy")) is False
    assert service.should_retry(Exception("blocked_drm")) is False
    assert service.should_retry(Exception("blocked_permission")) is False


def test_retry_permanent_error_not_retry() -> None:
    """Lỗi vĩnh viễn (validation) => không retry."""
    service = RetryService()
    assert service.should_retry(ValueError("validation error")) is False


def test_retry_backoff_delay() -> None:
    """Backoff delay tăng theo attempts."""
    service = RetryService(base_delay=1.0)
    assert service.backoff_delay(attempt=1) == 1.0
    assert service.backoff_delay(attempt=2) == 2.0
    assert service.backoff_delay(attempt=3) == 4.0


def test_document_library_list_pagination(tmp_path) -> None:
    """Document library list có phân trang và filter theo caller."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.platform.persistence.models import Base, Document

    db_path = str(tmp_path / "library.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    for i in range(5):
        session.add(
            Document(
                id=f"doc-{i}",
                canonical_url=f"https://example.com/{i}",
                content_hash=f"hash-{i}",
                title=f"T{i}",
                document_type="news_article",
            )
        )
    session.commit()

    lib = DocumentLibrary(session=session)
    page1 = lib.list_documents(caller_id="user-1", page=1, page_size=2)
    assert len(page1.items) == 2
    assert page1.page == 1
    assert page1.total == 5
    assert page1.total_pages == 3
