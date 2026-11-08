"""Public media-job API contracts (P03)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.main import create_app


@dataclass(frozen=True)
class _SubmittedMediaJob:
    job_id: str
    status: str


class _FakeMediaSubmitter:
    def submit(self, **kwargs):
        self.kwargs = kwargs
        return _SubmittedMediaJob(job_id="media-job-1", status="pending")


def test_create_direct_media_job_returns_pending_job_id() -> None:
    """API submits direct media work without downloading in the request process."""
    submitter = _FakeMediaSubmitter()
    app = create_app(media_job_submitter=submitter)
    with TestClient(app) as client:
        response = client.post(
            "/v1/media-jobs",
            headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "media-request-1"},
            json={"input_type": "direct", "source_url": "https://example.com/a.png"},
        )

    assert response.status_code == 202
    assert response.json() == {"media_job_id": "media-job-1", "status": "pending"}
    assert submitter.kwargs["caller_id"] == "caller-1"
