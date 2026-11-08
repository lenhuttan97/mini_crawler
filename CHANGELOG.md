# Changelog — Mini Crawler

Tất cả các thay đổi đáng chú ý cho dự án này sẽ được ghi trong tệp này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
và dự án tuân theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-08

### Added
- Nền tảng API FastAPI với `/health/live` và `/health/ready` (P00).
- Cài đặt typed bằng `pydantic-settings`, cấu trúc log có correlation ID (P00).
- Docker Compose cho API, PostgreSQL, Redis, MinIO, SearXNG; CI pipeline (P00).
- Policy Gate (SSRF), vòng đời job, idempotency, queue Celery, storage adapter, audit (P01).
- Crawl URL F01: static fetcher, normalizer, classifier, persistence dedupe, worker (P02).
- Trình duyệt dự phòng stub (không có Playwright thật) (P02).
- F02.1 Direct/Batch Image: manifest, quota, MIME/magic-bytes, partial failure (P03).
- Nguồn được phép deny-by-default, cổng DRM, RSS normalizer/dedupe, ngưỡng torrent (P04).
- F03 Search rồi Crawl qua SearXNG, không auto-crawl (P05).
- Phân quyền sở hữu job, hủy công việc, thư viện tài liệu phân trang (P06).
- Backup/restore logic (SQLite drill), ngưỡng SLO, quy tắc cảnh báo + runbook (P07-P08).

### Changed
- Cập nhật `pyproject.toml`: đưa `fastapi`, `uvicorn`, `pytest-asyncio` vào đúng nhóm dependencies.

### Fixed
- Sửa async `CrawlService.crawl` và `SearchService.crawl_selected` để await fetcher.
- Sửa `Dockerfile.local` sao chép build inputs trước khi cài dependency.

## [0.0.1] - 2026-11-01

### Added
- Khởi tạo cấu trúc dự án `mini_crawler` với `pyproject.toml`, `uv.lock`, package `app`.
