# Worker Documentation Index

> Đây là tài liệu cho **target worker-platform architecture** xử lý các job Search, Web Crawl, Image Download và Video Download; worker đích không cung cấp HTTP API cho client. Repository hiện tại vẫn có **current transitional FastAPI API runtime** trong `app/api/` trong quá trình chuyển đổi.

## Architecture

- [Worker platform architecture](architecture/worker-crawler-rearchitecture.md) — bounded contexts, queue management, contracts, migration principles và feature boundaries.

## Shared platform

- [Media candidate workflows](platform/media-candidate-workflows.md) — direct vs page workflows, manifest ownership, budgets, durable references and terminal outcomes.
- [Workflow orchestration](platform/workflow-orchestration.md) — explicit workflow requests, bounded fan-out/fan-in, versioned definitions and MVP-to-schedule roadmap.
- [Job orchestration](platform/job-orchestration.md) — durable feature job lifecycle, idempotency, cancellation, status and route ownership.
- [Queue management](platform/queue-management.md) — outbox, lease, retry, DLQ, cancellation và observability.
- [Network policy](platform/network-policy.md) — SSRF, redirect, robots, source policy và quota gates.
- [Storage](platform/storage.md) — document/asset persistence, deduplication, retention và result references.

## Worker features

- [Search](features/search.md) — provider discovery và normalized result sets; không auto-crawl.
- [Web Crawl](features/web-crawl.md) — fetch, browser fallback, extraction, classification, document persistence và static image candidates.
- [Image Download](features/image-download.md) — direct image URL hoặc page-driven static image discovery, validation, quotas và manifests.
- [Video Download](features/video-download.md) — direct approved source hoặc page-driven approved recipe, DRM gate và controlled `.mp4`/`.m3u8` download.
- [Document Type Classification](document-classification.md) — taxonomy, signals, metadata và quality gates cho Web Crawl.

## Operations

- [Queue lag runbook](runbooks/queue_lag.md)
- [Browser memory runbook](runbooks/browser_memory.md)
- [Error ratio runbook](runbooks/error_ratio.md)

## Learning

- [Beginner-to-Master learning path](learning/README.md) — curriculum for repository technologies and the worker-first roadmap; it is not an implementation contract.

## Reference material

`docs/sample/` chứa tài liệu tham khảo bên ngoài/lịch sử. Chúng không phải architecture hoặc implementation contract hiện hành của worker repository.

- [Mini Search học từ SearXNG](sample/MINI_SEARXNG_PYTHON.md)
- [Mini Nextcloud architecture](sample/mini_nextcloud_architecture.md)
- [Mini services replacement roadmap](sample/mini-services-replacement-roadmap.md)
