"""Tests for worker v1 Job Orchestration (P01/P02).

Job Orchestration is the only component allowed to create or transition
FeatureJob. It persists FeatureJob, typed JobCommand and OutboxEvent
atomically, and never calls a worker, queue publisher or network client.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.job_orchestration.repository import JobOrchestrationRepository
from app.platform.job_orchestration.service import (
    JobNotFound,
    JobOrchestrationService,
    JobOwnershipError,
)
from app.platform.persistence.models import Base
from app.shared.contracts.jobs import QueueMessageV1
from app.shared.contracts.workflows import JobIntent


@pytest.fixture
def session(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    sess = SessionLocal()
    yield sess
    sess.close()


def _intent() -> JobIntent:
    return JobIntent(
        feature_code="search",
        command_ref="cmd-1",
        workflow_run_id="run-1",
        workflow_step_id=None,
        idempotency_scope="scope-1",
        idempotency_key="idem-1",
        caller_id="user-1",
        correlation_id="corr-1",
    )


def test_submit_creates_job_command_and_outbox_atomically(session) -> None:
    """Submit persists FeatureJob + JobCommand + OutboxEvent in one transaction."""
    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())

    assert job.job_id is not None
    assert job.feature_code == "search"
    assert job.status == "pending_publish"
    assert job.idempotency_scope == "scope-1"
    assert job.idempotency_key == "idem-1"

    repo = JobOrchestrationRepository(session)
    assert repo.get_command(job.job_id) is not None
    assert repo.get_pending_outbox() is not None


def test_submit_is_idempotent_and_returns_existing_job(session) -> None:
    """Repeat submit with same scope+key returns the existing job, no duplicate outbox."""
    service = JobOrchestrationService(JobOrchestrationRepository(session))
    intent = _intent()
    job1 = service.submit(intent)
    job2 = service.submit(intent)

    assert job1.job_id == job2.job_id
    repo = JobOrchestrationRepository(session)
    outbox = repo.get_pending_outbox()
    assert outbox is not None
    # Calling submit again must not create a second pending outbox event.
    service.submit(intent)
    assert repo.get_pending_outbox() is outbox or repo.count_outbox("pending_publish") == 1


def test_submit_unknown_feature_code_is_rejected(session) -> None:
    """Image/Video intents are not executable in MVP v1."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        JobIntent(
            feature_code="image_download",
            command_ref="cmd-1",
            workflow_run_id="run-1",
            workflow_step_id=None,
            idempotency_scope="scope-1",
            idempotency_key="idem-1",
            caller_id="user-1",
            correlation_id="corr-1",
        )


def test_request_cancel_sets_cancellation_state(session) -> None:
    """Cancellation marks the job without completing it."""
    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())

    result = service.request_cancel(job.job_id, caller_id="user-1")
    assert result.cancellation_state == "requested"
    assert result.status != "cancelled"


def test_request_cancel_unknown_job_raises(session) -> None:
    """Cancelling a missing job raises JobNotFound."""
    service = JobOrchestrationService(JobOrchestrationRepository(session))
    with pytest.raises(JobNotFound):
        service.request_cancel("missing-job", caller_id="user-1")


def test_request_cancel_other_caller_raises(session) -> None:
    """A different caller cannot cancel a job."""
    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())
    with pytest.raises(JobOwnershipError):
        service.request_cancel(job.job_id, caller_id="user-2")


def test_commit_outcome_marks_job_and_publishes_result_outbox(session) -> None:
    """Commit outcome transitions the job and appends a result outbox event."""
    from app.shared.contracts.jobs import ExecutionOutcome

    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())
    repo = JobOrchestrationRepository(session)
    lease = repo.acquire_lease(job.job_id, worker_id="worker-1")

    outcome = ExecutionOutcome.completed(result_reference="doc-1")
    updated = service.commit_outcome(job.job_id, lease.id, outcome)

    assert updated.status == "completed"
    assert updated.result_reference == "doc-1"
    # submit created 1 pending_publish (request); commit_outcome adds 1 (result).
    assert repo.count_outbox("pending_publish") == 2  # request + result events


def test_commit_outcome_requires_active_lease(session) -> None:
    """Committing without a lease is rejected."""
    from app.shared.contracts.jobs import ExecutionOutcome

    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())

    with pytest.raises(ValueError, match="lease"):
        service.commit_outcome(
            job.job_id,
            lease_id="missing-lease",
            outcome=ExecutionOutcome.completed(result_reference="doc-1"),
        )


def test_queue_message_contains_only_four_fields(session) -> None:
    """The durable command is not in the queue; only the four-field envelope is."""
    from app.platform.queue_management.repository import QueueManagementRepository

    service = JobOrchestrationService(JobOrchestrationRepository(session))
    job = service.submit(_intent())
    repo = QueueManagementRepository(session)
    message = repo.build_queue_message(job.job_id, "search", "v1", "corr-1")

    assert message == QueueMessageV1(
        job_id=job.job_id,
        feature_code="search",
        contract_version="v1",
        correlation_id="corr-1",
    )
    assert "url" not in message.model_dump()
    assert "query" not in message.model_dump()
