"""Public endpoints for asynchronous media-job submission (P03)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["media"])


class CreateMediaJobRequest(BaseModel):
    input_type: str = Field(pattern="^(direct|image_batch)$")
    source_url: str | None = Field(default=None, max_length=2048)
    items: list[dict[str, Any]] | None = Field(default=None, max_length=50)


class CreateMediaJobResponse(BaseModel):
    media_job_id: str
    status: str


@router.post(
    "/media-jobs", response_model=CreateMediaJobResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_media_job(
    body: CreateMediaJobRequest,
    request: Request,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> dict[str, str]:
    """Submit direct/batch media work without downloading in the API process."""
    submitter = getattr(request.app.state, "media_job_submitter", None)
    if submitter is None:
        raise HTTPException(status_code=503, detail="media job submission is unavailable")
    submitted = submitter.submit(
        caller_id=caller_id,
        input_type=body.input_type,
        source_url=body.source_url,
        idempotency_key=idempotency_key,
        items=body.items,
    )
    return {"media_job_id": submitted.job_id, "status": submitted.status}
