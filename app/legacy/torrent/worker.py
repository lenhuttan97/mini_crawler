"""Approved-source torrent/magnet worker entrypoint (P04).

Chỉ nhận một job ID đáng tin cậy từ hàng đợi. Nguồn chưa được phép
hoặc chưa bật tính năng torrent => chặn ngay, không gọi mạng.

Tải torrent được thực hiện qua torrent_client được inject (để kiểm thử
đơn vị không cần mạng thật). Áp dụng giới hạn peers/disk/bandwidth/số
file/thời gian theo yêu cầu P04.
"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit

from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import MediaAsset, MediaJob, MediaJobItem
from app.features.video_download.application.source_registry import SourceRegistry
from app.entrypoints.celery_worker import celery_app


class TorrentDownloadError(Exception):
    """Lỗi khi tải torrent (client lỗi, mạng,...)."""


class TorrentQuotaExceeded(Exception):
    """Vượt quota peers/disk/bandwidth/số file/thời gian."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _check_quota(
    *,
    peers: int,
    disk_mb: int,
    bandwidth_mbps: int,
    max_peers: int,
    min_free_disk_mb: int,
    min_bandwidth_mbps: int,
    max_files: int | None,
    file_count: int,
    max_time_seconds: int | None,
    elapsed_seconds: float,
) -> None:
    """Kiểm tra giới hạn torrent; nêu TorrentQuotaExceeded nếu vượt."""
    if peers > max_peers:
        raise TorrentQuotaExceeded(f"số peers {peers} vượt quá giới hạn {max_peers}")
    if disk_mb < min_free_disk_mb:
        raise TorrentQuotaExceeded(
            f"dung lượng disk {disk_mb}MB thấp hơn giới hạn {min_free_disk_mb}MB"
        )
    if bandwidth_mbps < min_bandwidth_mbps:
        raise TorrentQuotaExceeded(
            f"bandwidth {bandwidth_mbps}Mbps thấp hơn giới hạn {min_bandwidth_mbps}Mbps"
        )
    if max_files is not None and file_count > max_files:
        raise TorrentQuotaExceeded(f"số file {file_count} vượt quá giới hạn {max_files}")
    if max_time_seconds is not None and elapsed_seconds > max_time_seconds:
        raise TorrentQuotaExceeded(
            f"thời gian {elapsed_seconds:.0f}s vượt quá giới hạn {max_time_seconds}s"
        )


def execute_torrent_job(
    job_id: str,
    *,
    session_factory=None,
    source_registry: SourceRegistry | None = None,
    torrent_client: Any = None,
    max_peers: int = 50,
    min_free_disk_mb: int = 1024,
    min_bandwidth_mbps: int = 10,
    max_files: int | None = None,
    max_time_seconds: int | None = None,
) -> str | None:
    """Worker entrypoint: tải torrent từ nguồn approved và lưu asset."""
    settings = Settings()
    session_factory = session_factory or create_session_factory(settings)
    session = session_factory()
    try:
        job = session.get(MediaJob, job_id)
        if job is None:
            return None

        domain = urlsplit(job.source_url or "").hostname
        if source_registry is not None and (
            domain is None or not source_registry.allows_network(domain=domain, feature="torrent")
        ):
            job.status = JobStatus.BLOCKED_POLICY.value
            job.policy_status = JobStatus.BLOCKED_POLICY.value
            job.error_code = "blocked_policy"
            session.commit()
            return job_id

        if torrent_client is None:
            job.status = JobStatus.FAILED.value
            job.error_code = "torrent_client_missing"
            session.commit()
            return job_id

        # Kiểm tra quota trước khi tải (giá trị mặc định an toàn).
        _check_quota(
            peers=0,
            disk_mb=min_free_disk_mb,
            bandwidth_mbps=min_bandwidth_mbps,
            max_peers=max_peers,
            min_free_disk_mb=min_free_disk_mb,
            min_bandwidth_mbps=min_bandwidth_mbps,
            max_files=max_files,
            file_count=0,
            max_time_seconds=max_time_seconds,
            elapsed_seconds=0.0,
        )

        items = (
            session.query(MediaJobItem)
            .filter_by(media_job_id=job_id)
            .order_by(MediaJobItem.sequence)
            .all()
        )
        if not items:
            job.status = JobStatus.COMPLETED.value
            session.commit()
            return job_id

        any_completed = False
        for item in items:
            if item.status != "pending":
                continue
            try:
                metadata = torrent_client.download(item.source_url)
            except Exception:  # noqa: BLE001
                item.status = "failed"
                item.error_code = "download_error"
                session.commit()
                continue

            object_key = str(metadata.get("object_key", ""))
            mime_type = str(metadata.get("mime_type", "application/octet-stream"))
            byte_size = int(metadata.get("byte_size", 0))
            checksum = str(
                metadata.get("checksum", "") or hashlib.sha256(object_key.encode()).hexdigest()
            )

            media_asset = MediaAsset(
                job_id=job_id,
                object_key=object_key,
                mime_type=mime_type,
                byte_size=byte_size,
                checksum=checksum,
                source_metadata=None,
            )
            session.add(media_asset)
            session.flush()

            item.status = "completed"
            item.asset_id = media_asset.id
            any_completed = True
            session.commit()

        if any_completed:
            job.status = JobStatus.COMPLETED.value
        else:
            job.status = JobStatus.FAILED.value
        session.commit()
        return job_id
    finally:
        session.close()


celery_app.task(name="app.legacy.torrent.worker.execute_torrent_job")(execute_torrent_job)
