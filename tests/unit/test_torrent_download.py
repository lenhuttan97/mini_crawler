"""Torrent download worker tests (P04 F02.4).

Chỉ download torrent từ nguồn approved và đã bật feature torrent.
Áp dụng giới hạn peers/disk/bandwidth/số file/thời gian.
Không gọi mạng thật — downloader bị inject.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import JobStatus, SourceStatus
from app.platform.persistence.models import Base, MediaAsset, MediaJob, MediaJobItem
from app.services.source_registry_service import SourceRegistryService
from app.workers.torrent_worker import (
    execute_torrent_job,
)


def _make_torrent_job(session, status="pending"):
    job = MediaJob(
        id="torrent-job-1",
        caller_id="user-1",
        input_type="torrent",
        status=status,
        source_url="https://torrents.example/example.torrent",
        policy_status="allowed",
    )
    session.add(job)
    session.flush()
    session.add(
        MediaJobItem(
            id="item-1",
            media_job_id=job.id,
            sequence=1,
            source_url="https://torrents.example/example.torrent",
            status="pending",
        )
    )
    session.commit()
    return job


def test_torrent_download_approved_source(tmp_path) -> None:
    """Nguồn approved + feature torrent => download, tạo asset, đánh completed."""
    engine = _ce(f"sqlite:///{tmp_path / 'torrent.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    registry = SourceRegistryService(session)
    registry.upsert(
        domain="torrents.example",
        state=SourceStatus.APPROVED,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"torrent": True},
    )
    session.commit()

    _make_torrent_job(session)

    client = MagicMock()
    client.download.return_value = {
        "object_key": "torrents/torrent-job-1/example.torrent",
        "mime_type": "application/x-bittorrent",
        "byte_size": 1024,
        "checksum": "abc123",
    }

    result = execute_torrent_job(
        "torrent-job-1",
        session_factory=lambda: session,
        source_registry=registry,
        torrent_client=client,
        max_peers=10,
        min_free_disk_mb=2048,
        min_bandwidth_mbps=10,
        max_files=5,
        max_time_seconds=3600,
    )

    assert result == "torrent-job-1"
    session.expire_all()
    job = session.get(MediaJob, "torrent-job-1")
    assert job.status == JobStatus.COMPLETED.value
    assert job.drm_status is None

    items = session.query(MediaJobItem).filter_by(media_job_id="torrent-job-1").all()
    assert all(it.status == "completed" for it in items)
    assert all(it.asset_id is not None for it in items)

    assets = session.query(MediaAsset).all()
    assert len(assets) == 1
    assert assets[0].mime_type == "application/x-bittorrent"
    assert assets[0].byte_size == 1024


def test_torrent_download_blocks_unapproved_source(tmp_path) -> None:
    """Nguồn chưa approved => blocked_policy, không gọi client."""
    engine = _ce(f"sqlite:///{tmp_path / 'torrent2.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    registry = SourceRegistryService(session)
    registry.upsert(
        domain="torrents.example",
        state=SourceStatus.PENDING_REVIEW,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"torrent": False},
    )
    session.commit()

    _make_torrent_job(session)

    client = MagicMock()
    result = execute_torrent_job(
        "torrent-job-1",
        session_factory=lambda: session,
        source_registry=registry,
        torrent_client=client,
    )

    assert result == "torrent-job-1"
    client.download.assert_not_called()
    session.expire_all()
    job = session.get(MediaJob, "torrent-job-1")
    assert job.status == JobStatus.BLOCKED_POLICY.value
    assert job.error_code == "blocked_policy"
