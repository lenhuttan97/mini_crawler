# Mini Services Replacement Roadmap Design

## Intent

Tài liệu hoá hai mini project như đích học tập/roadmap độc lập, không phải capability đã chạy trong Mini Crawler:

- **Mini Search** sẽ thay thế provider SearXNG khi đạt contract và quality gate.
- **Mini Nextcloud** sẽ thay thế provider Nextcloud self-hosted khi đạt contract và quality gate.

Trước khi mỗi mini project sẵn sàng, worker dùng provider thay thế đã được cấu hình. Thay provider không được làm thay đổi workflow, job lifecycle, result object hay policy boundaries của Mini Crawler.

## Scope

- Chỉ cập nhật Markdown trong `docs/sample/` và documentation index/reference roadmap.
- Không thêm container, dependency, endpoint, adapter source code hoặc cấu hình runtime.
- Giữ `docs/sample/` là reference/roadmap, không đưa hai mini project vào active worker contract.

## Stable boundaries

| Capability | Temporary provider | Target provider | Stable boundary |
|---|---|---|---|
| Web discovery | Self-hosted SearXNG | Mini Search | `SearchProvider` → normalized `SearchResultSet` |
| Standalone Mini Nextcloud storage | Self-hosted Nextcloud | Mini Nextcloud | Metadata/binary separation and server-generated object key; not a Mini Crawler storage provider. |

`SearchProvider` remains discovery-only: it never creates crawl work. For explicit `search_and_extract`, only Workflow Orchestration applies the registered selection rule and creates bounded crawl job intents.

For the current crawler, `ObjectStorage` remains storage-only: it does not decide caller authorization, workflow flow, MIME validity or retention. Mini Crawler persists document/asset metadata in MinIO/S3-compatible storage and keeps server-generated object keys; provider credentials, signed URLs and storage-specific paths never enter job messages or result objects. The Nextcloud-to-Mini-Nextcloud path belongs only to the standalone Mini Nextcloud project.

## Keep the current repository simple

The current repository does **not** split physical modules by feature. It keeps the existing simple structure:

```text
app/
  services/                 # SearchService, PersistenceService, crawl/media services
  adapters/                 # StorageAdapter, static/browser fetchers
  workers/                  # Celery wiring and tasks
  api/                      # current transitional API runtime
```

The feature-first structure in `docs/architecture/worker-crawler-rearchitecture.md` is a later worker-platform direction, not a refactor required by this roadmap. This roadmap must not create `app/features/`, `app/platform/`, new ports, or wrapper modules simply to prepare for a hypothetical provider.

Current integration points are deliberately direct:

| Capability | Current implementation | Current provider | Later replacement decision |
|---|---|---|---|
| Search | `app/services/search_service.py` | `Settings.searxng_url` → SearXNG | Only when Mini Search is runnable, extract the smallest provider seam needed to select it instead of SearXNG. |
| Object storage | `app/adapters/storage.py` used by `PersistenceService` | MinIO/S3-compatible storage | Current Mini Crawler remains on MinIO. A future Mini Nextcloud project can use self-hosted Nextcloud before its own implementation exists; it does not silently replace this runtime's storage. |

Mini Search and Mini Nextcloud are standalone learning/product targets, not new crawler features. While they are only examples, their replacement decision belongs in documentation. When either becomes a real second provider, introduce only the interface needed at its existing call site and retain the current simple layout.

This simple structure applies to every current capability: Search, Crawl Data, Image and Video. Crawl, image and video continue to be built through the current service/adapter/worker layout; this roadmap does not define an external replacement provider for them.

Feature-first extraction is deferred until there is evidence that a feature needs independent deployment/queue ownership, independently versioned contracts, or a change is repeatedly crossing the existing service/worker/adapter directories. The later direction covers all four worker capabilities, but each feature migrates in its own approved, reversible increment:

| Current capability | Current area | Later feature module |
|---|---|---|
| Search | `app/services/search_service.py` | `app/features/search/` |
| Crawl Data | crawl, normalize, classify and persistence services | `app/features/web_crawl/` |
| Image | media submission/processing services and media tasks | `app/features/image_download/` |
| Video | video discovery/download services and worker tasks | `app/features/video_download/` |

The later refactor moves each capability's domain behavior, application service, adapter and worker task as one unit. It does not alter feature behavior merely to fit a directory structure. Queue/version migration, integration tests and rollback are part of that separate approval.

## Documentation changes

1. Update `docs/sample/MINI_SEARXNG_PYTHON.md` with a status box, a provider substitution table and exit criteria. Its primary target remains a small standalone meta-search app; SearXNG is the temporary self-hosted provider, not source code to fork or copy.
2. Update `docs/sample/mini_nextcloud_architecture.md` with the equivalent status box, a Nextcloud-to-Mini-Nextcloud provider path and exit criteria. Its primary target remains a standalone cloud server; its temporary provider communicates through a reviewed storage integration, preferably WebDAV for file operations.
3. Add one reference roadmap that states the current simple integration points, future provider switch gates, lifecycle boundaries, migration order and no-go conditions; link it from the reference-material section of `docs/INDEX.md`.

## Provider switch gates

The target provider may receive controlled traffic only after it:

1. passes the same adapter contract tests as the temporary provider;
2. maps timeout, unavailable and malformed upstream data to the existing typed error/outcome model;
3. preserves no-network-in-unit-test rules and uses controlled integration targets;
4. has an explicit rollback switch to the temporary provider; and
5. does not require raw credentials, signed URLs, user-supplied object keys, arbitrary URLs or provider-specific payloads in worker messages.

No dual-write of search results or binary objects is introduced in this documentation-only phase. The later implementation must use a controlled canary/read path before a full provider switch; storage data migration is a separate, explicitly approved project.

## Non-goals

- Claiming that a Nextcloud container or Mini Search/Mini Nextcloud implementation exists in the current Compose runtime.
- Replacing MinIO/object-storage contracts in the active worker documentation.
- Adding WebDAV, SearXNG compatibility, authentication, media processing or migration code.
- Moving reference architecture into `docs/platform/` without a separate product/implementation decision.

## Acceptance criteria

- A reader can tell which service runs before and after each mini app exists.
- A reader can identify the current call site and the minimum future seam that prevents workflow changes during replacement.
- A reader sees that neither mini project is a new crawler feature and that no physical module split is planned now.
- A reader sees that Search, Crawl Data, Image and Video all remain in the current simple layout until one later, explicitly approved feature-extraction migration.
- The documents name concrete switch gates and the rollback/no-dual-write boundary.
- The active documentation index continues to label the material as reference/roadmap only.
