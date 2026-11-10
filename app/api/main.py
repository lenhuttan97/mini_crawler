"""FastAPI application factory (P00 Item 3)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from app.api.exceptions import http_exception_handler, unhandled_exception_handler
from app.api.middleware.correlation_id import CorrelationIdMiddleware
from app.api.routers import crawl_jobs, documents, health, jobs, media_jobs, search
from app.bootstrap.database import create_session_factory
from app.bootstrap.settings import Settings
from app.platform.observability.logging import configure_logging, get_logger
from app.features.web_crawl.application.submission import CrawlJobSubmitter
from app.services.media_submission import MediaJobSubmitter
from app.features.search.application.service import SearchService
from app.workers.celery_app import create_celery_app

_logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    crawl_job_submitter: Any | None = None,
    media_job_submitter: Any | None = None,
    search_service: Any | None = None,
    job_service: Any | None = None,
    document_library: Any | None = None,
) -> FastAPI:
    """Build the FastAPI application with settings, logging, middleware and routers."""
    settings = settings or Settings()
    configure_logging()
    if crawl_job_submitter is None:
        task_app = create_celery_app(settings)

        def enqueue_crawl_job(job_id: str) -> None:
            task_app.send_task(
                "app.features.web_crawl.worker.task.execute_crawl_job",
                args=[job_id],
                queue="crawl",
            )

        crawl_job_submitter = CrawlJobSubmitter(
            session_factory=create_session_factory(settings),
            enqueue=enqueue_crawl_job,
        )
    if media_job_submitter is None:
        media_task_app = create_celery_app(settings)

        def enqueue_media_job(job_id: str) -> None:
            media_task_app.send_task(
                "app.workers.media_tasks.execute_media_job",
                args=[job_id],
                queue="media",
            )

        media_job_submitter = MediaJobSubmitter(
            session_factory=create_session_factory(settings),
            enqueue=enqueue_media_job,
        )
    if search_service is None:
        search_service = SearchService(searxng_url=settings.searxng_url)

    app = FastAPI(
        title="Mini Crawler",
        version="0.1.0",
        description="Policy-first asynchronous crawler and approved-media downloader.",
    )
    app.state.settings = settings
    app.state.crawl_job_submitter = crawl_job_submitter
    app.state.media_job_submitter = media_job_submitter
    app.state.search_service = search_service
    app.state.job_service = job_service
    app.state.document_library = document_library

    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.include_router(health.router)
    app.include_router(crawl_jobs.router)
    app.include_router(media_jobs.router)
    app.include_router(search.router)
    app.include_router(jobs.router)
    app.include_router(documents.router)

    @app.get("/{path:path}", include_in_schema=False)
    async def catch_all_not_found(path: str) -> None:
        """Convert any unmatched route into a 404 handled by the error envelope."""
        raise HTTPException(status_code=404, detail=f"not found: {path}")

    _logger.info("application_created", profile=settings.profile)
    return app
