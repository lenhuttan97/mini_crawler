"""Public endpoints for F03 Search rồi Crawl (P05)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["search"])


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str = ""


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int


class CrawlSelectedRequest(BaseModel):
    result_url: str = Field(min_length=1, max_length=2048)


class CrawlSelectedResponse(BaseModel):
    crawl_job_id: str
    status: str


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """Tìm kiếm qua provider đã cấu hình và trả kết quả đã chuẩn hóa (không auto-crawl)."""
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="search service is unavailable")
    # Gọi trực tiếp (không await) vì SearchService.search là hàm đồng bộ.
    results = service.search(query=q, page=page, limit=limit)
    return {"results": results, "total": len(results)}


@router.post(
    "/search/crawl-selected",
    response_model=CrawlSelectedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def crawl_selected(
    body: CrawlSelectedRequest,
    request: Request,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> dict[str, str]:
    """Chọn một kết quả search => tạo F01 CrawlJob (không có crawler thứ hai)."""
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="search service is unavailable")
    result = await service.crawl_selected(
        result_url=body.result_url,
        caller_id=caller_id,
        idempotency_key=idempotency_key,
    )
    return {"crawl_job_id": result["crawl_job_id"], "status": result["status"]}
