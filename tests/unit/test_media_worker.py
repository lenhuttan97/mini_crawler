"""Tests cho media worker (P03 Item 2).

process_media_job duyệt từng item, gọi downloader (mock), validate MIME/magic
bytes, upload storage (mock), cập nhật status từng item. Không gọi mạng thật.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base, MediaAsset, MediaJob, MediaJobItem
from app.services.source_registry import SourceRecord, SourceRegistry
from app.workers.media_tasks import process_media_job


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "mediaworker.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _make_media_job(session, items):
    job = MediaJob(
        id="media-job-1",
        caller_id="user-1",
        input_type="image_batch",
        source_url="https://example.com/manifest",
        policy_status="allowed",
    )
    session.add(job)
    session.flush()
    for idx, src in enumerate(items, start=1):
        session.add(
            MediaJobItem(
                id=f"item-{idx}",
                media_job_id=job.id,
                sequence=idx,
                source_url=src,
                status="pending",
            )
        )
    session.commit()
    return job


def test_process_media_job_success_all(db_session) -> None:
    """Tất cả item tải thành công => completed, asset được tạo."""
    _job = _make_media_job(db_session, ["https://example.com/a.png", "https://example.com/b.png"])

    downloader = MagicMock()
    downloader.download.side_effect = [
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
    ]
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(key="assets/k1", byte_size=8, checksum="sha1")

    result = process_media_job(
        session=db_session, job_id="media-job-1", downloader=downloader, storage=storage
    )

    assert result == "media-job-1"
    assert downloader.download.call_count == 2
    assert storage.upload_object.call_count == 2
    db_session.expire_all()
    items = (
        db_session.query(MediaJobItem)
        .filter_by(media_job_id="media-job-1")
        .order_by(MediaJobItem.sequence)
        .all()
    )
    assert all(it.status == "completed" for it in items)
    assets = db_session.query(MediaAsset).order_by(MediaAsset.object_key).all()
    assert len(assets) == 2
    assert all(asset.mime_type == "image/png" for asset in assets)
    assert all(asset.byte_size == 8 for asset in assets)
    assert {item.asset_id for item in items} == {asset.id for asset in assets}


def test_process_media_job_partial_failure_keeps_success(db_session) -> None:
    """Một item fail/blocked vẫn giữ item thành công, không làm mất kết quả khác."""
    _job = _make_media_job(db_session, ["https://example.com/a.png", "https://example.com/b.png"])

    downloader = MagicMock()
    downloader.download.side_effect = [
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        Exception("bad mime"),
    ]
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(key="assets/k1", byte_size=8, checksum="sha1")

    result = process_media_job(
        session=db_session, job_id="media-job-1", downloader=downloader, storage=storage
    )

    assert result == "media-job-1"
    db_session.expire_all()
    items = (
        db_session.query(MediaJobItem)
        .filter_by(media_job_id="media-job-1")
        .order_by(MediaJobItem.sequence)
        .all()
    )
    assert items[0].status == "completed"
    assert items[1].status in ("failed", "blocked")
    assert items[1].error_code is not None


def test_process_media_job_mime_rejected(db_session) -> None:
    """MIME/magic bytes không cho phép => item blocked, không upload."""
    _job = _make_media_job(db_session, ["https://example.com/x.exe"])

    downloader = MagicMock()
    downloader.download.return_value = (b"MZ\x90\x00", "application/x-dosexec")
    storage = MagicMock()

    process_media_job(
        session=db_session, job_id="media-job-1", downloader=downloader, storage=storage
    )

    storage.upload_object.assert_not_called()
    db_session.expire_all()
    item = db_session.get(MediaJobItem, "item-1")
    assert item.status == "blocked"
    assert item.error_code is not None


def test_process_media_job_blocks_item_exceeding_total_byte_quota(db_session) -> None:
    """A later item may not upload when it would exceed the job byte quota."""
    _make_media_job(db_session, ["https://example.com/a.png", "https://example.com/b.png"])
    downloader = MagicMock()
    downloader.download.side_effect = [
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
    ]
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(key="assets/k1", size=8)

    process_media_job(
        session=db_session,
        job_id="media-job-1",
        downloader=downloader,
        storage=storage,
        max_total_bytes=8,
    )

    db_session.expire_all()
    items = (
        db_session.query(MediaJobItem)
        .filter_by(media_job_id="media-job-1")
        .order_by(MediaJobItem.sequence)
        .all()
    )
    assert items[0].status == "completed"
    assert items[1].status == "blocked"
    assert items[1].error_code == "quota_exceeded"
    assert storage.upload_object.call_count == 1


def test_execute_media_job_loads_session_from_job_id(db_session) -> None:
    """Queue task payload is only job ID; dependencies are composed at worker boundary."""
    from app.workers.media_tasks import execute_media_job

    _make_media_job(db_session, ["https://example.com/a.png"])
    downloader = MagicMock()
    downloader.download.return_value = (b"\x89PNG\r\n\x1a\n", "image/png")
    storage = MagicMock()
    storage.upload_object.return_value = MagicMock(key="assets/k1", size=8)

    result = execute_media_job(
        "media-job-1",
        session_factory=lambda: db_session,
        downloader=downloader,
        storage=storage,
    )

    assert result == "media-job-1"
    db_session.expire_all()
    assert db_session.get(MediaJob, "media-job-1").status == "completed"


def test_process_media_job_blocks_unapproved_source_before_download(db_session) -> None:
    """Pending/unknown sources are deny-by-default and never reach downloader."""
    _make_media_job(db_session, ["https://pending.example/a.png"])
    registry = SourceRegistry()
    registry.add(SourceRecord(domain="pending.example", state=SourceStatus.PENDING_REVIEW))
    downloader = MagicMock()
    storage = MagicMock()

    process_media_job(
        session=db_session,
        job_id="media-job-1",
        downloader=downloader,
        storage=storage,
        source_registry=registry,
    )

    downloader.download.assert_not_called()
    item = db_session.get(MediaJobItem, "item-1")
    assert item.status == "blocked"
    assert item.error_code == "blocked_policy"


def test_process_media_job_blocks_drm_before_storage_upload(db_session) -> None:
    """A DRM detector stops an approved item before any object is persisted."""
    _make_media_job(db_session, ["https://approved.example/a.png"])
    registry = SourceRegistry()
    registry.add(SourceRecord(domain="approved.example", state=SourceStatus.APPROVED))
    downloader = MagicMock()
    downloader.download.return_value = (b"\x89PNG\r\n\x1a\n", "image/png")
    storage = MagicMock()

    process_media_job(
        session=db_session,
        job_id="media-job-1",
        downloader=downloader,
        storage=storage,
        source_registry=registry,
        drm_detector=lambda _data: True,
    )

    storage.upload_object.assert_not_called()
    item = db_session.get(MediaJobItem, "item-1")
    assert item.status == "blocked"
    assert item.error_code == "blocked_drm"
    assert db_session.get(MediaJob, "media-job-1").drm_status == "blocked_drm"
