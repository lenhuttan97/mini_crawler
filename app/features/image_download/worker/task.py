"""Celery registration for the shared image executor."""

from __future__ import annotations

from app.entrypoints.celery_worker import celery_app
from app.features.image_download.application.execution import (
    execute_media_job,
    process_media_job,
)

__all__ = ["execute_media_job", "process_media_job"]

celery_app.task(name="app.features.image_download.worker.task.execute_media_job")(execute_media_job)
