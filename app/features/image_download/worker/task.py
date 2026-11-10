"""Media worker (P03 Item 2-3).

process_media_job duyệt từng item của media job, gọi downloader (được inject),
validate MIME/magic bytes, upload storage (được inject), cập nhật status từng
item. Hỗ trợ partial failure: item fail/blocked không làm mất item khác.
"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.platform.asset_storage.storage import StorageAdapter
from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.platform.persistence.enums import JobStatus
from app.platform.persistence.models import MediaAsset, MediaJob, MediaJobItem
from app.features.video_download.application.source_registry import SourceRegistry
from app.entrypoints.celery_worker import celery_app

# Magic bytes header -> mime type được phép.
ALLOWED_MAGIC: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
}
ALLOWED_MIMES = frozenset(ALLOWED_MAGIC.values())


def _detect_mime(data: bytes) -> str | None:
    """Phát hiện MIME từ magic bytes header; None nếu không nhận diện."""
    for header, mime in ALLOWED_MAGIC.items():
        if data.startswith(header):
            return mime
    # RIFF cần kiểm tra sâu hơn cho WEBP.
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def process_media_job(
    session: Any,
    job_id: str,
    downloader: Any,
    storage: Any,
    max_total_bytes: int | None = None,
    source_registry: SourceRegistry | None = None,
    drm_detector=None,
) -> str | None:
    """Xử lý media job: tải từng item, validate, upload, cập nhật status."""
    job = session.get(MediaJob, job_id)
    if job is None:
        return None

    items = (
        session.query(MediaJobItem)
        .filter_by(media_job_id=job_id)
        .order_by(MediaJobItem.sequence)
        .all()
    )
    if not items:
        job.status = JobStatus.COMPLETED.value
        session.flush()
        return job_id

    any_blocked = False
    any_completed = False
    downloaded_bytes = 0
    for item in items:
        if item.status != "pending":
            continue
        domain = urlsplit(item.source_url).hostname
        if source_registry is not None and (
            domain is None or not source_registry.allows_network(domain)
        ):
            item.status = "blocked"
            item.error_code = "blocked_policy"
            any_blocked = True
            continue
        try:
            data, content_type = downloader.download(item.source_url)
        except Exception:  # noqa: BLE001
            item.status = "failed"
            item.error_code = "download_error"
            any_blocked = True
            continue

        if drm_detector is not None and drm_detector(data):
            item.status = "blocked"
            item.error_code = "blocked_drm"
            job.drm_status = "blocked_drm"
            any_blocked = True
            continue

        mime = _detect_mime(data)
        if mime is None or mime not in ALLOWED_MIMES:
            item.status = "blocked"
            item.error_code = "mime_not_allowed"
            any_blocked = True
            continue
        if content_type and content_type not in ALLOWED_MIMES:
            item.status = "blocked"
            item.error_code = "mime_not_allowed"
            any_blocked = True
            continue
        if max_total_bytes is not None and downloaded_bytes + len(data) > max_total_bytes:
            item.status = "blocked"
            item.error_code = "quota_exceeded"
            any_blocked = True
            continue

        try:
            asset = storage.upload_object(
                bucket="media-assets",
                key=f"assets/{job_id}/{item.sequence}",
                data=data,
                content_type=mime,
            )
        except Exception:  # noqa: BLE001
            item.status = "failed"
            item.error_code = "storage_error"
            any_blocked = True
            continue

        uploaded_size = getattr(asset, "size", None)
        if not isinstance(uploaded_size, int):
            uploaded_size = getattr(asset, "byte_size", None)
        if not isinstance(uploaded_size, int):
            uploaded_size = len(data)
        media_asset = MediaAsset(
            job_id=job_id,
            object_key=str(getattr(asset, "key", "")),
            mime_type=mime,
            byte_size=uploaded_size,
            checksum=hashlib.sha256(data).hexdigest(),
            source_metadata=None,
        )
        session.add(media_asset)
        session.flush()
        item.status = "completed"
        item.asset_id = media_asset.id
        downloaded_bytes += len(data)
        any_completed = True

    if any_completed and not any_blocked:
        job.status = JobStatus.COMPLETED.value
    elif any_completed:
        job.status = JobStatus.COMPLETED.value  # partial success vẫn completed job-level
    elif job.drm_status == "blocked_drm":
        job.status = JobStatus.BLOCKED_DRM.value
    else:
        job.status = JobStatus.FAILED.value
    session.flush()
    return job_id


class HttpMediaDownloader:
    """Minimal direct-media downloader; policy is enforced before job creation."""

    def download(self, url: str) -> tuple[bytes, str]:
        response = httpx.get(url, timeout=30.0, follow_redirects=False)
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "").split(";", 1)[0]


def execute_media_job(
    job_id: str,
    *,
    session_factory=None,
    downloader: Any | None = None,
    storage: Any | None = None,
) -> str | None:
    """Celery entrypoint that loads a trusted media job by ID and owns its session."""
    settings = Settings()
    session_factory = session_factory or create_session_factory(settings)
    downloader = downloader or HttpMediaDownloader()
    storage = storage or StorageAdapter(endpoint_url=settings.minio_endpoint)
    session = session_factory()
    try:
        result = process_media_job(session, job_id, downloader, storage)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


celery_app.task(name="app.features.image_download.worker.task.execute_media_job")(execute_media_job)
