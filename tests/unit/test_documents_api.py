"""Document library API contracts (P06 S04)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Document


@dataclass(frozen=True)
class _DocumentPage:
    items: list
    page: int
    page_size: int
    total: int
    total_pages: int


class _FakeDocumentLibrary:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def list_documents(
        self,
        *,
        caller_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
        document_type: str | None = None,
    ) -> _DocumentPage:
        self.calls.append(
            {
                "caller_id": caller_id,
                "page": page,
                "page_size": page_size,
                "document_type": document_type,
            }
        )
        return _DocumentPage(
            items=[Document(id="doc-1", canonical_url="https://example.com/a", content_hash="h")],
            page=page,
            page_size=page_size,
            total=1,
            total_pages=1,
        )


def test_list_documents_paginated_and_filtered() -> None:
    """Danh sách document phân trang, lọc theo loại, và gắn caller_id."""
    lib = _FakeDocumentLibrary()
    app = create_app(document_library=lib)
    with TestClient(app) as client:
        response = client.get(
            "/v1/documents",
            headers={"X-Caller-ID": "user-1"},
            params={"page": 2, "page_size": 5, "document_type": "news_article"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert body["total_pages"] == 1
    assert lib.calls == [
        {"caller_id": "user-1", "page": 2, "page_size": 5, "document_type": "news_article"}
    ]
