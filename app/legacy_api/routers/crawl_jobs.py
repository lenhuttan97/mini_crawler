"""Public endpoints for asynchronous crawl-job submission (P02)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["crawl"])


class CreateCrawlJobRequest(BaseModel):
    """Caller request for a crawl job; policy validation happens in the service."""

    url: str = Field(min_length=1, max_length=2048)


class CreateCrawlJobResponse(BaseModel):
    """Immediate submission result; crawling is performed by a worker."""

    crawl_job_id: str
    status: str


@router.post(
    "/crawl-jobs", response_model=CreateCrawlJobResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_crawl_job(
    body: CreateCrawlJobRequest,
    request: Request,
    response: Response,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> dict[str, Any]:
    """Create and enqueue a crawl job without fetching in the API process."""
    submitter = getattr(request.app.state, "crawl_job_submitter", None)
    if submitter is None:
        raise HTTPException(status_code=503, detail="crawl job submission is unavailable")

    submitted = submitter.submit(
        url=body.url,
        caller_id=caller_id,
        idempotency_key=idempotency_key,
    )
    response.status_code = getattr(request.app.state, "job_submission_status_code", 202)
    return {"crawl_job_id": submitted.job_id, "status": submitted.status}
