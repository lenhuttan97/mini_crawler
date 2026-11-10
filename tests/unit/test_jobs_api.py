"""Job API authorization contracts (P06 S01)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.legacy_api.main import create_app
from app.platform.persistence.enums import JobStatus


@dataclass(frozen=True)
class _JobView:
    id: str
    type: str
    status: str
    caller_id: str


class _FakeJobService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_job(self, job_id, caller_id: str):
        self.calls.append({"job_id": job_id, "caller_id": caller_id})
        if job_id == "job-owner" and caller_id == "user-A":
            return _JobView(
                id="job-owner", type="crawl", status=JobStatus.COMPLETED.value, caller_id="user-A"
            )
        return None


def test_get_crawl_job_enforces_ownership() -> None:
    """Chủ sở hữu đọc được job; caller khác nhận 404, không lộ dữ liệu của người khác."""
    service = _FakeJobService()
    app = create_app(job_service=service)

    with TestClient(app) as client:
        owner_resp = client.get("/v1/crawl-jobs/job-owner", headers={"X-Caller-ID": "user-A"})
        other_resp = client.get("/v1/crawl-jobs/job-owner", headers={"X-Caller-ID": "user-B"})

    assert owner_resp.status_code == 200
    assert owner_resp.json()["id"] == "job-owner"
    assert other_resp.status_code == 404
    assert service.calls == [
        {"job_id": "job-owner", "caller_id": "user-A"},
        {"job_id": "job-owner", "caller_id": "user-B"},
    ]
