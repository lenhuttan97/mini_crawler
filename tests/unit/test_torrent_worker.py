"""Approved-source torrent/magnet worker tests (P04)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base, MediaJob
from app.services.source_registry_service import SourceRegistryService


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "torrents.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _make_media_job(session, status="pending"):
    job = MediaJob(
        id="torrent-job-1",
        caller_id="user-1",
        input_type="torrent",
        status=status,
        source_url="https://torrents.example/magnet",
        policy_status="allowed",
    )
    session.add(job)
    session.flush()
    return job


def test_execute_torrent_job_requires_persisted_approved_torrent_source(db_session) -> None:
    """Queue task chỉ nhận job ID; nguồn chưa approved => blocked_policy, không gọi mạng."""
    from app.workers.torrent_worker import execute_torrent_job

    _make_media_job(db_session)
    registry = SourceRegistryService(db_session)
    registry.upsert(
        domain="torrents.example",
        state=SourceStatus.PENDING_REVIEW,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"torrent": False},
    )
    db_session.commit()

    result = execute_torrent_job(
        "torrent-job-1",
        session_factory=lambda: db_session,
        source_registry=registry,
    )

    db_session.expire_all()
    job = db_session.get(MediaJob, "torrent-job-1")
    assert result == "torrent-job-1"
    assert job.status == "blocked_policy"
    assert job.policy_status == "blocked_policy"
    assert job.error_code == "blocked_policy"
