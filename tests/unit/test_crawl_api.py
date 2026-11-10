"""Public API contracts for asynchronous crawl-job submission (P02)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.legacy_api.main import create_app
from app.bootstrap.settings import Settings
from app.features.web_crawl.application.submission import CrawlJobSubmitter


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
    app = create_app(crawl_job_submitter=submitter)

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
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}"))

    assert isinstance(app.state.crawl_job_submitter, CrawlJobSubmitter)
