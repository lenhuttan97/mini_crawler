"""Celery registration for the shared crawl executor."""

from __future__ import annotations

from app.entrypoints.celery_worker import celery_app
from app.features.web_crawl.application.execution import (
    execute_crawl_job,
    process_crawl_job,
)

celery_app.task(name="app.features.web_crawl.worker.task.process_crawl_job")(process_crawl_job)
celery_app.task(name="app.features.web_crawl.worker.task.execute_crawl_job")(execute_crawl_job)
