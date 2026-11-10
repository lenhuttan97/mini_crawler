"""Cấu hình Celery cho Mini Crawler (P01 Item 5).

4 queue tách biệt: crawl, media, torrent, maintenance. Mỗi queue có
concurrency/time limit riêng. Broker là Redis (cấu hình qua env tại runtime).
"""

from __future__ import annotations

from celery import Celery
from kombu import Queue

from app.bootstrap.settings import Settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the worker app from typed runtime configuration without connecting."""
    settings = settings or Settings()
    app = Celery("mini_crawler")

    # Broker / result backend: shared with API settings and Compose.
    app.conf.broker_url = settings.redis_url
    app.conf.result_backend = settings.redis_url

    # 4 queue tách theo loại tác vụ (P01 §5.4).
    app.conf.task_queues = (
        Queue("crawl"),
        Queue("media"),
        Queue("torrent"),
        Queue("maintenance"),
    )

    # Ánh xạ task vào queue (P01 §5.4: tách queue để giới hạn tài nguyên riêng).
    app.conf.task_routes = {
        "app.platform.queue_management.tasks.claim_job": {"queue": "crawl"},
        "app.platform.queue_management.tasks.complete_job": {"queue": "crawl"},
        "app.platform.queue_management.tasks.fail_job": {"queue": "crawl"},
        "app.features.web_crawl.worker.task.process_crawl_job": {"queue": "crawl"},
        "app.features.web_crawl.worker.task.execute_crawl_job": {"queue": "crawl"},
        "app.workers.media_tasks.execute_media_job": {"queue": "media"},
        "app.workers.torrent_worker.execute_torrent_job": {"queue": "torrent"},
        "app.platform.queue_management.tasks.maintenance_job": {"queue": "maintenance"},
    }

    # Giới hạn thời gian và hành vi worker.
    app.conf.task_time_limit = 3600  # hard limit: 1 giờ
    app.conf.task_soft_time_limit = 3300  # soft limit: 55 phút
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1

    # Retry chỉ cho lỗi tạm thời (timeout, upstream, storage); không retry blocked_*.
    app.conf.task_retry_backoff = True
    app.conf.task_retry_backoff_max = 600
    app.conf.task_retry_jitter = True
    app.conf.task_default_retry_delay = 60
    app.conf.task_max_retries = 3
    return app


celery_app = create_celery_app()
