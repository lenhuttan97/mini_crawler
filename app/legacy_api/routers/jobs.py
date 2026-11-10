"""Job API endpoints with ownership enforcement (P06 S01)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.platform.persistence.enums import JobStatus
from app.platform.job_orchestration.service import JobNotFound, JobOwnershipError

router = APIRouter(prefix="/v1", tags=["jobs"])


@router.get("/crawl-jobs/{job_id}")
async def get_crawl_job(
    job_id: str,
    request: Request,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
) -> dict[str, Any]:
    """Đọc job chỉ khi caller là chủ sở hữu; không lộ dữ liệu của người khác."""
    service = getattr(request.app.state, "job_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="job service is unavailable")
    job = service.get_job(job_id, caller_id=caller_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "caller_id": job.caller_id,
    }


@router.post("/crawl-jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_crawl_job(
    job_id: str,
    request: Request,
    caller_id: str = Header(alias="X-Caller-ID", min_length=1),
) -> dict[str, str]:
    """Hủy job chỉ khi caller là chủ sở hữu và job chưa ở trạng thái cuối cùng."""
    service = getattr(request.app.state, "job_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="job service is unavailable")
    try:
        cancelled = service.cancel_job(job_id, caller_id=caller_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")
    except JobOwnershipError:
        raise HTTPException(status_code=403, detail="not owner")
    if not cancelled:
        raise HTTPException(status_code=409, detail="job already in terminal state")
    return {"job_id": job_id, "status": JobStatus.CANCELLED.value}
