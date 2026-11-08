"""Document library API endpoints (P06 S04)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/v1", tags=["documents"])


def _serialize_document(item: Any) -> dict[str, Any]:
    """Chuyển document ORM sang dict an toàn để trả về API."""
    crawled_at = getattr(item, "crawled_at", None)
    if crawled_at is not None:
        crawled_at = crawled_at.isoformat()
    return {
        "id": getattr(item, "id", None),
        "canonical_url": getattr(item, "canonical_url", None),
        "title": getattr(item, "title", None),
        "document_type": getattr(item, "document_type", None),
        "content_hash": getattr(item, "content_hash", None),
        "crawled_at": crawled_at,
    }


@router.get("/documents")
def list_documents(
    request: Request,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
    page: int = 1,
    page_size: int = 20,
    document_type: str | None = None,
) -> dict[str, Any]:
    """Lấy trang document đã chuẩn hóa, phân trang và lọc theo loại."""
    service = getattr(request.app.state, "document_library", None)
    if service is None:
        raise HTTPException(status_code=503, detail="document library is unavailable")
    page_result = service.list_documents(
        caller_id=caller_id,
        page=page,
        page_size=page_size,
        document_type=document_type,
    )
    return {
        "items": [_serialize_document(item) for item in page_result.items],
        "page": page_result.page,
        "page_size": page_result.page_size,
        "total": page_result.total,
        "total_pages": page_result.total_pages,
    }
