"""Job cancel API contracts (P06 S02)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.platform.persistence.enums import JobStatus
from app.platform.job_orchestration.service import JobOwnershipError


@dataclass(frozen=True)
class _JobView:
    id: str
    status: str


class _FakeJobService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def cancel_job(self, job_id, caller_id: str) -> bool:
        self.calls.append({"job_id": job_id, "caller_id": caller_id})
        if job_id == "job-owner" and caller_id == "user-A":
            return True
        if job_id == "job-owner":
            raise JobOwnershipError(f"caller {caller_id} không sở hữu job {job_id}")
        return False


def test_cancel_job_enforces_ownership_and_returns_status() -> None:
    """Chủ sở hữu hủy được job và nhận trạng thái; caller khác bị từ chối (403)."""
    service = _FakeJobService()
    app = create_app(job_service=service)

    with TestClient(app) as client:
        owner_resp = client.post(
            "/v1/crawl-jobs/job-owner/cancel", headers={"X-Caller-ID": "user-A"}
        )
        other_resp = client.post(
            "/v1/crawl-jobs/job-owner/cancel", headers={"X-Caller-ID": "user-B"}
        )

    assert owner_resp.status_code == 200
    assert owner_resp.json() == {"job_id": "job-owner", "status": JobStatus.CANCELLED.value}
    assert other_resp.status_code == 403
    assert service.calls == [
        {"job_id": "job-owner", "caller_id": "user-A"},
        {"job_id": "job-owner", "caller_id": "user-B"},
    ]
