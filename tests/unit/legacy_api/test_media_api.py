"""Public media-job API contracts (P03)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.bootstrap.database import initialize_local_schema
from app.bootstrap.settings import Settings
from app.legacy_api.main import create_app
from app.platform.network_policy.policy import PolicyDecision, PolicyGate
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import MediaJob


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


def _local_settings(tmp_path) -> Settings:
    settings = Settings(
        runtime_mode="inline",
        database_url=f"sqlite:///{tmp_path / 'inline-media-api.db'}",
        local_storage_path=tmp_path / "objects",
    )
    initialize_local_schema(settings)
    return settings


def test_inline_media_api_returns_terminal_status_with_200(tmp_path) -> None:
    """Inline mode waits for media execution and returns its persisted status."""
    settings = _local_settings(tmp_path)

    def execute(job_id: str, **_kwargs) -> None:
        from app.bootstrap.database import create_session_factory

        with create_session_factory(settings)() as session:
            session.get(MediaJob, job_id).status = JobStatus.COMPLETED.value
            session.commit()

    with (
        patch("app.legacy_api.main.execute_media_job", side_effect=execute),
        patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)),
    ):
        app = create_app(settings)
        with TestClient(app) as client:
            response = client.post(
                "/v1/media-jobs",
                headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "media-request-2"},
                json={"input_type": "direct", "source_url": "https://example.com/a.png"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.COMPLETED.value
