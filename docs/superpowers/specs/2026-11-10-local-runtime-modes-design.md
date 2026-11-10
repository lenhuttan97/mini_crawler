# Local Runtime Modes — Design

## Intent

Cho phép chạy FastAPI trực tiếp trên máy phát triển mà không khởi động Docker
Compose và không cần Redis, Celery broker, MinIO hay SearXNG. Vẫn giữ nguyên
mode broker hiện có cho Docker/worker-first runtime.

Người dùng đã chọn cả hai mode local:

1. `inline`: API thực thi crawl và image-download ngay trong request.
2. `db-worker`: API chỉ ghi job vào database; một tiến trình worker polling
   database thực thi sau đó, không dùng Redis/Celery.

## Goals

- Chạy `uvicorn` với SQLite file và filesystem local, không cần Docker hay
  service ngoài.
- `inline` trả kết quả sau khi xử lý xong; job metadata/idempotency vẫn được
  ghi database để giữ traceability và các endpoint trạng thái.
- `db-worker` giữ semantics asynchronous: API trả `202`, worker riêng xử lý
  durable job từ database.
- Crawl và image-download dùng local filesystem storage với object key do
  server sinh, giữ nguyên validation, policy gate, redirect check, MIME check
  và partial-success behavior hiện có.
- Giữ Redis/Celery + MinIO + SearXNG runtime hiện tại hoạt động không đổi khi
  không bật local mode.

## Non-goals / anti-goals

- Không thay SearXNG bằng một search provider mới. Khi không cấu hình search
  provider, `/v1/search` trả `503` với capability/reason code an toàn; crawl
  URL trực tiếp vẫn hoạt động.
- Không biến local DB worker thành implementation thay thế contract target
  PostgreSQL outbox/lease/DLQ/at-least-once. Nó là runtime local một consumer.
- Không hỗ trợ video, torrent, browser recipe, recursive crawl, scheduler,
  retry/DLQ hay multi-worker concurrency mới trong local modes.
- Không lưu content/binary vào database và không nới lỏng network policy hay
  request validation.

## Constraints

- `docs/INDEX.md` vẫn là source of truth: target worker-first uses PostgreSQL
  and Redis/Celery delivery. Local modes must be explicitly documented as
  transitional developer runtimes, not as target queue contracts.
- Feature worker code must retain its existing policy/storage boundaries. API
  does not call HTTPX/downloader/parser directly; it delegates to the existing
  feature execution entrypoints/composition.
- Local object paths must be based on server-generated object keys and remain
  below a configured storage root; no caller-supplied filename/path is used.
- The DB worker is single-instance only. Starting more than one is unsupported
  until the target lease/outbox design is implemented; the runner must state
  this restriction in its help/docs.

## Approaches considered

| Approach | Trade-off | Decision |
| --- | --- | --- |
| Inline only | Smallest diff, but cannot exercise durable asynchronous job behavior. | Rejected: user needs DB-backed job execution too. |
| Reconfigure Celery with an in-process/filesystem broker | Retains Celery commands but adds transport-specific behavior and is not a DB-only worker. | Rejected: unnecessary moving parts for local development. |
| Two explicit local runtime modes plus existing broker mode | One simple synchronous path and one DB-only asynchronous path; preserves existing Docker behavior. | Selected. |

## Runtime configuration and behavior

Add one typed `APP_RUNTIME_MODE` setting with explicit values:

| Mode | Dependencies | Submission behavior | HTTP response |
| --- | --- | --- | --- |
| `broker` (default) | Current DB + Redis/Celery + configured S3/MinIO; SearXNG for search | Existing enqueue path | Existing `202` pending job |
| `inline` | SQLite or explicitly configured DB; local filesystem storage | Persist, execute through feature worker entrypoint, then reload terminal status | `200` with the existing job-id/status response shape |
| `db-worker` | SQLite or explicitly configured DB; local filesystem storage; separate runner process | Persist only | Existing `202` pending job |

`APP_LOCAL_STORAGE_PATH` is required for local modes and defaults to an ignored
runtime directory. A local mode also uses an explicit SQLite `DATABASE_URL` in
the documented no-Docker example. Schema creation is a local-mode bootstrap
step only; broker/production modes continue to use migrations/deployment
operations, never implicit schema creation.

Search provider configuration is capability-based rather than an attempted
network call to `localhost:8080`: local modes without an explicitly enabled
provider install no `SearchService`; `/v1/search` reports it unavailable. The
selected-search-to-crawl endpoint is also unavailable in that case.

## Components and changes

1. **Settings and bootstrap**
   - Validate the runtime mode and local storage path.
   - Create local SQLite schema only through an explicit local bootstrap
     command, not during arbitrary API startup.
   - Keep the present external-service settings for `broker` mode; local modes
     must not construct a Celery app or S3 client.

2. **Filesystem object storage**
   - Add a minimal local storage adapter with the existing
     `upload_object`/`download_object`/`delete_object` behavior needed by
     document and image feature code.
   - Write atomically within the configured root and return the existing safe
     metadata shape. Preserve server-generated keys and cleanup on a database
     rollback where the current persistence flow supports it.

3. **Feature execution composition**
   - Move common worker dependency composition out of Celery-only code so the
     inline submitters and DB runner invoke the same crawl/image executors.
   - Leave task registration as a thin broker-only wrapper. No API router gains
     HTTPX, parser, downloader or storage implementation knowledge.

4. **Inline submitters**
   - Add submitters with the same API-facing `submit(...)` contract as the
     current durable submitters: commit the job first, execute it once, reload
     the persisted result, and return its final status.
   - An idempotency replay returns the previously persisted result and does not
     execute the job twice.
   - The existing request/response model stays unchanged; only local inline
     mode returns `200` because completion is known before the response.

5. **DB-only worker runner**
   - Add a command-line entrypoint that polls the configured database and
     dispatches pending crawl/image jobs to the common executors.
   - It records `queued` then `running` and commits a terminal result; errors
     leave a safe failed/blocked status. It does not use Redis, Celery result
     backend, MinIO or SearXNG.
   - Enforce/document one runner process. The target queue/lease/outbox worker
     remains the only supported multi-consumer runtime.

6. **API composition and documentation**
   - `create_app` selects broker, inline or DB-worker submitters from settings.
   - Update `.env.example`, `STARTUP.md`, and README with copy-paste commands
     for SQLite bootstrap, inline API, and API + DB worker. Docker Compose is
     not removed.

## Scope map

| Area | Expected paths |
| --- | --- |
| Config/bootstrap | `app/bootstrap/settings.py`, database bootstrap/entrypoint, `.env.example` |
| Local object storage | `app/platform/asset_storage/` |
| Crawl/image execution | existing worker task modules plus small shared composition/submitter code |
| API selection/status | `app/legacy_api/main.py`, crawl/media routers as needed |
| DB runner | new `app/entrypoints/` module |
| Tests | settings, API crawl/media, local storage, inline execution, DB runner |
| Operator docs | `README.md`, `STARTUP.md` |

## Verification

- Unit-test mode validation and ensure local modes never instantiate/send a
  Celery task or create an S3 client.
- Test inline crawl and media API calls with controlled HTTP/storage doubles:
  response is terminal, work executes once, and idempotency replay does not
  repeat network/storage work.
- Test DB-worker API submission plus worker execution using a file-backed
  SQLite database; verify `202 → terminal` state without Redis/Celery.
- Test filesystem storage server-generated keys, traversal rejection, read,
  delete, and storage failure behavior.
- Test search-disabled response does not attempt a request to SearXNG.
- Run the focused tests, then `uv run ruff check .` and
  `uv run ruff format --check .`; review the diff before completion.

## Risks and decisions left to implementation

- Inline requests legitimately take as long as the remote crawl/download and
  can hit an HTTP timeout. It is intentionally developer-only; use DB worker
  or broker mode for long work.
- SQLite is suitable for no-Docker/single-runner development, not concurrent
  worker production. A real external PostgreSQL instance may also be used in
  `db-worker` mode.
- Existing code does not yet implement the target durable command/outbox/lease
  model. This change must not claim that it does.
