"""Tests for Celery-independent execution and inline local submitters."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.network_policy.policy import PolicyDecision, PolicyGate
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import Base, CrawlJob, Job, MediaJob, MediaJobItem


def _imports_without_celery(module: str, callable_name: str) -> None:
    code = (
        f"import sys; from {module} import {callable_name}; "
        f"assert callable({callable_name}); "
        "assert 'app.entrypoints.celery_worker' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_crawl_execution_module_does_not_import_celery() -> None:
    """The shared crawl executor stays usable without a broker."""
    _imports_without_celery("app.features.web_crawl.application.execution", "execute_crawl_job")


def test_image_execution_module_does_not_import_celery() -> None:
    """The shared image executor stays usable without a broker."""
    _imports_without_celery(
        "app.features.image_download.application.execution", "execute_media_job"
    )


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'inline.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    yield factory
    engine.dispose()


def _complete_crawl_job(job_id: str, session_factory) -> None:
    with session_factory() as session:
        job = session.get(Job, job_id)
        job.status = JobStatus.COMPLETED.value
        session.commit()


def _complete_media_job(job_id: str, session_factory) -> None:
    with session_factory() as session:
        job = session.get(MediaJob, job_id)
        job.status = JobStatus.COMPLETED.value
        session.commit()


def test_inline_crawl_submitter_commits_executes_and_returns_terminal_status(
    session_factory,
) -> None:
    """Inline submission executes after commit and returns the persisted status."""
    from app.local_runtime.submitters import InlineCrawlJobSubmitter

    execute = Mock(side_effect=lambda job_id: _complete_crawl_job(job_id, session_factory))
    submitter = InlineCrawlJobSubmitter(session_factory=session_factory, execute=execute)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        result = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )

    assert result.status == JobStatus.COMPLETED.value
    execute.assert_called_once_with(result.job_id)
    with session_factory() as session:
        assert session.get(Job, result.job_id).status == JobStatus.COMPLETED.value


def test_inline_crawl_idempotency_replay_does_not_execute_twice(session_factory) -> None:
    """A duplicate request returns stored state without another crawl."""
    from app.local_runtime.submitters import InlineCrawlJobSubmitter

    execute = Mock(side_effect=lambda job_id: _complete_crawl_job(job_id, session_factory))
    submitter = InlineCrawlJobSubmitter(session_factory=session_factory, execute=execute)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        first = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )
        second = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )

    assert second == first
    execute.assert_called_once()


def test_inline_media_submitter_executes_once_and_returns_terminal_status(session_factory) -> None:
    """Inline media submission runs after durable job/items are committed."""
    from app.local_runtime.submitters import InlineMediaJobSubmitter

    execute = Mock(side_effect=lambda job_id: _complete_media_job(job_id, session_factory))
    submitter = InlineMediaJobSubmitter(session_factory=session_factory, execute=execute)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        result = submitter.submit(
            caller_id="caller-1",
            input_type="direct",
            source_url="https://example.com/a.png",
            idempotency_key="media-request-1",
        )

    assert result.status == JobStatus.COMPLETED.value
    execute.assert_called_once_with(result.job_id)
    with session_factory() as session:
        assert session.get(MediaJob, result.job_id).status == JobStatus.COMPLETED.value
        assert session.query(MediaJobItem).filter_by(media_job_id=result.job_id).count() == 1


def test_inline_media_idempotency_replay_does_not_execute_twice(session_factory) -> None:
    """A repeated media request never downloads the same items a second time."""
    from app.local_runtime.submitters import InlineMediaJobSubmitter

    execute = Mock(side_effect=lambda job_id: _complete_media_job(job_id, session_factory))
    submitter = InlineMediaJobSubmitter(session_factory=session_factory, execute=execute)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        first = submitter.submit(
            caller_id="caller-1",
            input_type="direct",
            source_url="https://example.com/a.png",
            idempotency_key="media-request-1",
        )
        second = submitter.submit(
            caller_id="caller-1",
            input_type="direct",
            source_url="https://example.com/a.png",
            idempotency_key="media-request-1",
        )

    assert second == first
    execute.assert_called_once()


def test_inline_unexpected_executor_error_leaves_safe_failed_status(session_factory) -> None:
    """An executor crash is reported as persisted failure, not a hung job."""
    from app.local_runtime.submitters import InlineCrawlJobSubmitter

    def fail(_job_id: str) -> None:
        raise RuntimeError("provider exploded")

    submitter = InlineCrawlJobSubmitter(session_factory=session_factory, execute=fail)

    with patch.object(PolicyGate, "evaluate", return_value=PolicyDecision(True, None, None)):
        result = submitter.submit(
            url="https://example.com/article",
            caller_id="caller-1",
            idempotency_key="request-1",
        )

    assert result.status == JobStatus.FAILED.value
    with session_factory() as session:
        job = session.get(Job, result.job_id)
        assert job.status == JobStatus.FAILED.value
        assert session.get(CrawlJob, result.job_id) is not None
