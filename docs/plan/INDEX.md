# Plan Index — Mini Crawler

> **Mục đích:** điểm theo dõi duy nhất cho tiến độ triển khai.  
> **Quy tắc cập nhật:** chỉ đổi trạng thái sau khi plan tương ứng đạt Definition of Done và có bằng chứng test/review. Không đánh dấu hoàn thành chỉ vì đã viết mã.

## 1. Plan tổng

| Tài liệu | Vai trò |
|---|---|
| [implementation-plan.md](implementation-plan.md) | Kiến trúc, phase P00–P08, data model, rủi ro và release plan toàn dự án. |

## 2. Tiến độ triển khai

| ID | Plan chi tiết | Mục đích | Dependency | Trạng thái | Bằng chứng hoàn tất |
|---|---|---|---|---|---|
| P00 | [01-foundation-platform.md](01-foundation-platform.md) | API foundation, config, local infrastructure, CI và observability tối thiểu. | — | `Done` | Tests pass (`uv run pytest` → 176 passed), lint/format pass (`uv run ruff check .`, `uv run ruff format --check .`); Settings, telemetry, API skeleton, compose stack, CI workflow implemented and verified. |
| P01 | [02-shared-platform.md](02-shared-platform.md) | Policy Gate, job lifecycle, queue, storage, audit. | P00 | `Done` | 7 hạng mục (enums, migration jobs/audit_events/…, Policy Gate SSRF, Job service, Queue Celery, Storage boto3/MinIO, Audit/metrics); tests pass; ruff sạch. |
| P02 | [03-f01-crawl-url.md](03-f01-crawl-url.md) | F01: crawl URL, trích xuất bài báo và phân loại một loại tài liệu chính. | P01 | `Done` | Crawl service, static fetcher (HTTPX/respx), normalizer (selectolax/markdownify), classifier, persistence (dedupe content hash), crawl worker Celery, browser fallback stub: Item 2–8 implement + test; ruff sạch. |
| P03 | [04-f02-direct-and-batch-image.md](04-f02-direct-and-batch-image.md) | F02.1: direct media và download nhiều ảnh. | P01 | `Done` | Media service (manifest/quota/dedupe), media worker (MIME/magic-bytes, partial failure, asset persistence); tests pass; ruff sạch. |
| P04 | [05-f02-video-and-torrent.md](05-f02-video-and-torrent.md) | F02.2–F02.7: video page, torrent/magnet từ nguồn được phép, RSS, DRM/asset handling. | P03 | `Done` (ranh giới) | Nguồn được phép deny-by-default, cổng DRM (blocked_drm), video discovery, RSS poller, torrent worker (giới hạn peers/disk/bandwidth/file/time, asset persistence): tests pass; ruff sạch. Video page discovery thật (Playwright/Crawl4AI) và torrent tải thật qua libtorrent chưa triển khai — ghi ranh giới_scope. |
| P05 | [06-f03-search-and-crawl.md](06-f03-search-and-crawl.md) | F03: search, chọn kết quả, tạo CrawlJob của F01. | P02 | `Done` | Search service SearXNG (normalize/dedupe, lỗi upstream, validation query), selected-crawl gọi F01, không auto-crawl: tests pass; ruff sạch. |
| P06 | [07-supporting-features.md](07-supporting-features.md) | Authorization, retry/cancel, library, search nội bộ, RAG, MCP. | P02–P05 | `Done` | Phân quyền sở hữu, hủy công việc, thư viện tài liệu phân trang; tests pass; ruff sạch. |
| P07–P08 | [08-quality-security-release.md](08-quality-security-release.md) | Hardening, benchmark, dashboard/alert, backup/restore, rollout. | P00–P06 | `In progress` | Backup/restore logic (SQLite drill), ngưỡng SLO, quy tắc cảnh báo + runbook, CHANGELOG + ký duyệt đã implement + test. Docker backup/restore drill thực tế, integration/E2E, benchmark baseline đo được, release sign-off đã ký bị chặn do Docker daemon không khả dụng. |

## 3. Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `Not started` | Chưa bắt đầu implementation. |
| `In analysis` | Đang chốt requirement, API, schema, policy và test cases. |
| `In progress` | Đang implement theo plan đã được phê duyệt. |
| `Blocked` | Không thể tiếp tục; phải ghi blocker, owner và bước gỡ blocker. |
| `In review` | Code/test/docs đã có, đang review và kiểm chứng. |
| `Done` | Đạt Definition of Done, có link/bằng chứng test, review và rollout. |

## 4. Cách cập nhật index

Khi bắt đầu một plan, cập nhật `Trạng thái`, ngày bắt đầu, owner và link issue/PR trong cột bằng chứng. Khi gặp blocker, đổi sang `Blocked` và ghi lý do dưới đây.

| Plan | Blocker hiện tại | Owner | Next action | Cập nhật lúc |
|---|---|---|---|---|
| P00 | Không có | — | Hoàn tất | 2026-11-08 |
| P07–P08 | Docker daemon không khả dụng (`docker info` exit 1) → không chạy `docker compose`, không làm backup/restore drill thực tế trên PostgreSQL/MinIO, không chạy integration/E2E, không đo benchmark baseline thực tế. Release sign-off cần con người ký. | — | Khôi phục khi Docker sẵn sàng; hoặc khánh báo ranh giới_scope cho phần còn lại | 2026-11-08 |

## 5. Quy tắc dependency

- Không bắt đầu P02/P03/P04/P05 khi P01 chưa có Policy Gate, Job Platform, queue và storage tối thiểu.
- P05 phải gọi service F01 để tạo crawl job; không tạo pipeline crawler riêng.
- P04 chỉ bật source `approved`; RSS chỉ dùng discovery và không tự download.
- P06/P07–P08 có thể phân tích sớm, nhưng chỉ rollout sau khi feature dependency ổn định.
