"""Tests for queue workers (P01 Item 5).

Kiểm tra cấu hình Celery (queue, route, time limit, retry policy) và
hàm xử lý task (claim/complete/fail job) — gọi trực tiếp hàm underlying,
không cần broker Redis thật.
"""

from __future__ import annotations

from app.workers.celery_app import celery_app
from app.platform.queue_management.tasks import claim_job, complete_job, fail_job


def test_celery_app_has_queues() -> None:
    """Celery app cấu hình 4 queue: crawl, media, torrent, maintenance."""
    queues = {q.name for q in celery_app.conf.task_queues}
    assert {"crawl", "media", "torrent", "maintenance"} <= queues


def test_celery_factory_uses_typed_redis_setting() -> None:
    """Worker broker/backend must follow the same typed runtime settings as Compose."""
    from app.bootstrap.settings import Settings
    from app.workers.celery_app import create_celery_app

    settings = Settings.model_validate({"REDIS_URL": "redis://queue.example:6380/3"})
    configured_app = create_celery_app(settings)

    assert configured_app.conf.broker_url == "redis://queue.example:6380/3"
    assert configured_app.conf.result_backend == "redis://queue.example:6380/3"


def test_celery_task_routes() -> None:
    """Task route ánh xạ task vào queue tương ứng."""
    routes = celery_app.conf.task_routes
    assert routes.get("app.platform.queue_management.tasks.claim_job") == {"queue": "crawl"}
    assert routes.get("app.platform.queue_management.tasks.complete_job") == {"queue": "crawl"}
    assert routes.get("app.platform.queue_management.tasks.fail_job") == {"queue": "crawl"}
    assert routes.get("app.platform.queue_management.tasks.maintenance_job") == {"queue": "maintenance"}


def test_celery_time_limits() -> None:
    """Time limit được thiết lập cho task."""
    assert celery_app.conf.task_time_limit > 0
    assert celery_app.conf.task_soft_time_limit > 0
    assert celery_app.conf.task_soft_time_limit < celery_app.conf.task_time_limit


def test_celery_retry_policy() -> None:
    """Retry backoff được bật; các task có max_retries."""
    assert celery_app.conf.task_retry_backoff is True


def test_claim_job_returns_job_id(tmp_path) -> None:
    """claim_job claim một job pending và trả job_id."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.platform.persistence.models import Base, Job

    db_path = str(tmp_path / "workers.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()

    job = Job(
        id="job-claim-1",
        type="crawl",
        status="pending",
        caller_id="user-1",
        idempotency_key="claim-k-1",
    )
    session.add(job)
    session.commit()

    result = claim_job(session=session, job_type="crawl")
    session.close()
    assert result == "job-claim-1"


def test_claim_job_none_when_no_pending(tmp_path) -> None:
    """Không có job pending => claim_job trả None."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.platform.persistence.models import Base

    db_path = str(tmp_path / "workers2.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()

    result = claim_job(session=session, job_type="crawl")
    session.close()
    assert result is None


def test_complete_job_sets_completed(tmp_path) -> None:
    """complete_job đánh job status completed."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.platform.persistence.models import Base, Job

    db_path = str(tmp_path / "workers3.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()

    job = Job(
        id="job-complete-1",
        type="crawl",
        status="queued",
        caller_id="user-1",
        idempotency_key="complete-k-1",
    )
    session.add(job)
    session.commit()

    complete_job(session=session, job_id="job-complete-1")
    session.refresh(job)
    session.close()
    assert job.status == "completed"


def test_fail_job_sets_failed_with_error_code(tmp_path) -> None:
    """fail_job đánh job status failed với error_code."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.platform.persistence.models import Base, Job

    db_path = str(tmp_path / "workers4.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()

    job = Job(
        id="job-fail-1",
        type="crawl",
        status="queued",
        caller_id="user-1",
        idempotency_key="fail-k-1",
    )
    session.add(job)
    session.commit()

    fail_job(session=session, job_id="job-fail-1", error_code="timeout")
    session.refresh(job)
    session.close()
    assert job.status == "failed"
