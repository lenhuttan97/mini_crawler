"""Public API contracts for asynchronous crawl-job submission (P02)."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.bootstrap.database import initialize_local_schema
from app.bootstrap.settings import Settings
from app.features.web_crawl.application.submission import CrawlJobSubmitter
from app.legacy_api.main import create_app
from app.platform.network_policy.policy import PolicyDecision, PolicyGate
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Job


@dataclass(frozen=True)
class _SubmittedJob:
    job_id: str
    status: str


class _FakeCrawlJobSubmitter:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def submit(self, *, url: str, caller_id: str, idempotency_key: str) -> _SubmittedJob:
        self.calls.append({"url": url, "caller_id": caller_id, "idempotency_key": idempotency_key})
        return _SubmittedJob(job_id="crawl-job-1", status="pending")


def test_create_crawl_job_returns_pending_job_id_without_fetching() -> None:
    """The request creates/enqueues a job and never performs a crawl inline."""
    submitter = _FakeCrawlJobSubmitter()
    app = create_app(
        crawl_job_submitter=submitter,
        settings=Settings(_env_file=None),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/crawl-jobs",
            headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "crawl-request-1"},
            json={"url": "https://example.com/article"},
        )

    assert response.status_code == 202
    assert response.json() == {"crawl_job_id": "crawl-job-1", "status": "pending"}
    assert submitter.calls == [
        {
            "url": "https://example.com/article",
            "caller_id": "caller-1",
            "idempotency_key": "crawl-request-1",
        }
    ]


def test_app_composes_durable_crawl_submitter_from_settings(tmp_path) -> None:
    """Production factory supplies the durable submitter without a test fake."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", _env_file=None))

    assert isinstance(app.state.crawl_job_submitter, CrawlJobSubmitter)


def _local_settings(tmp_path) -> Settings:
    settings = Settings(
        runtime_mode="inline",
        database_url=f"sqlite:///{tmp_path / 'inline-api.db'}",
        local_storage_path=tmp_path / "objects",
    )
    initialize_local_schema(settings)
    return settings


def test_inline_crawl_api_returns_terminal_status_with_200(tmp_path) -> None:
    """Inline mode waits for crawl execution and returns its persisted status."""
    settings = _local_settings(tmp_path)

    def execute(job_id: str, **_kwargs) -> None:
        from app.bootstrap.database import create_session_factory

        with create_session_factory(settings)() as session:
            session.get(Job, job_id).status = JobStatus.COMPLETED.value
            session.commit()

    with (
        patch("app.legacy_api.main.execute_crawl_job", side_effect=execute),
        patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)),
    ):
        app = create_app(settings)
        with TestClient(app) as client:
            response = client.post(
                "/v1/crawl-jobs",
                headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "crawl-request-1"},
                json={"url": "https://example.com/article"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.COMPLETED.value


def test_db_worker_crawl_api_returns_pending_202(tmp_path) -> None:
    """DB-worker mode persists a pending job without enqueueing Celery work."""
    settings = Settings(
        runtime_mode="db-worker",
        database_url=f"sqlite:///{tmp_path / 'db-worker-api.db'}",
        local_storage_path=tmp_path / "objects",
    )
    initialize_local_schema(settings)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        app = create_app(settings)
        with TestClient(app) as client:
            response = client.post(
                "/v1/crawl-jobs",
                headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "crawl-request-2"},
                json={"url": "https://example.com/article"},
            )

    assert app.state.job_submission_status_code == 202
    assert response.status_code == 202
    assert response.json()["status"] == JobStatus.PENDING.value


def test_local_app_composition_does_not_import_celery() -> None:
    """Local modes must start without a broker module or a global Celery app."""
    code = (
        "import sys\n"
        "from app.bootstrap.settings import Settings\n"
        "from app.legacy_api.main import create_app\n"
        "create_app(Settings(runtime_mode='db-worker', database_url='sqlite://'))\n"
        "assert 'app.entrypoints.celery_worker' not in sys.modules\n"
    )

    subprocess.run([sys.executable, "-c", code], check=True)
