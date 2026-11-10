# Local Runtime Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide inline and DB-only local execution modes for crawl and image APIs without Docker, Redis/Celery, MinIO, or SearXNG, while retaining the broker runtime.

**Architecture:** Add a typed runtime-mode setting and compose each mode at the FastAPI factory boundary. Extract crawl/image execution from Celery registration modules so inline submitters and a DB runner use the same feature logic, then use filesystem object storage for local modes. Preserve the current broker path unchanged.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy 2, SQLite, standard-library filesystem/CLI, HTTPX, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-11-10-local-runtime-modes-design.md`

## Global Constraints

- `broker` remains the default and keeps Redis/Celery, MinIO/S3 and optional SearXNG behavior.
- `inline` and `db-worker` require only a database and local filesystem storage; neither may construct Celery or boto3 S3 clients.
- Local runtime retains existing policy, redirect, MIME, checksum, server-generated-key and request-validation behavior.
- Local modes are developer runtimes, not a replacement for the target PostgreSQL/outbox/lease/DLQ contract.
- `db-worker` supports one runner process only; no retry/DLQ, scheduler or multi-worker guarantee.
- Add no dependency; use installed libraries and the standard library only.
- Never log raw query strings, source URLs, credentials, cookies, tokens, signed URLs or object content.

## Review Focus

- A repeated inline idempotency key returns the stored terminal job and never downloads/crawls twice — Task 3.
- `..`, absolute paths and symlink escapes cannot write outside `APP_LOCAL_STORAGE_PATH` — Task 2.
- Local mode never accidentally contacts the default SearXNG URL — Task 5.
- A restart may leave a queued DB job; normal queued-to-terminal execution is tested, and the single-consumer limitation is documented — Tasks 4 and 6.
- Inline work may exceed a client timeout; it still reloads a safe persisted outcome and the docs point long work to DB worker/broker mode — Tasks 3 and 6.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `app/bootstrap/settings.py` | Runtime mode, local storage and search-capability settings. |
| `app/bootstrap/database.py` | Existing session factory plus explicit local schema bootstrap. |
| `app/platform/asset_storage/local.py` | Filesystem version of existing object-storage operations. |
| `app/features/web_crawl/application/execution.py` | Crawl composition/execution without Celery import. |
| `app/features/image_download/application/execution.py` | Image composition/execution without Celery import. |
| `app/features/*/worker/task.py` | Thin broker-only Celery wrappers. |
| `app/local_runtime/submitters.py` | Post-commit inline submitters that reload terminal status. |
| `app/entrypoints/local_bootstrap.py` | Explicit local schema initialization command. |
| `app/entrypoints/database_worker.py` | Single-process database polling runner. |
| `app/legacy_api/main.py` and routers | Mode-specific composition and status code. |
| Tests and startup docs | Proof and operating instructions. |

### Task 1: Typed settings and explicit local schema bootstrap

**Files:**
- Modify: `app/bootstrap/settings.py`
- Modify: `app/bootstrap/database.py`
- Create: `app/entrypoints/local_bootstrap.py`
- Modify: `tests/unit/bootstrap/test_settings.py`
- Create: `tests/unit/bootstrap/test_local_bootstrap.py`

**Interfaces:**
- Consumes: `Settings`, `Base` from `app.platform.persistence.models`.
- Produces: `Settings.runtime_mode: Literal["broker", "inline", "db-worker"]`, `Settings.local_storage_path: Path`, `Settings.search_enabled: bool`, `initialize_local_schema(settings: Settings) -> None`.

- [ ] **Step 1: Write failing settings tests**

```python
def test_local_runtime_defaults_to_disabled_search_and_local_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_RUNTIME_MODE", "inline")
    monkeypatch.setenv("APP_LOCAL_STORAGE_PATH", str(tmp_path / "objects"))
    settings = Settings()
    assert settings.runtime_mode == "inline"
    assert settings.search_enabled is False
    assert settings.local_storage_path == tmp_path / "objects"

def test_unknown_runtime_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "queue-on-mars")
    with pytest.raises(ValueError, match="runtime_mode"):
        Settings()
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/unit/bootstrap/test_settings.py -v`

Expected: FAIL because local runtime settings do not exist.

- [ ] **Step 3: Implement typed runtime settings**

Use a `Literal` mode, `Path` local root defaulting to `.runtime/objects`, and an optional raw search setting resolved by the existing model validator: search defaults enabled only for `broker`. Preserve current aliases and production secret validation.

- [ ] **Step 4: Write failing bootstrap test**

```python
def test_initialize_local_schema_creates_job_and_document_tables(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'local.db'}", runtime_mode="inline")
    initialize_local_schema(settings)
    engine = create_engine(settings.database_url)
    assert inspect(engine).has_table("jobs")
    assert inspect(engine).has_table("documents")
```

- [ ] **Step 5: Verify the bootstrap test fails**

Run: `uv run pytest tests/unit/bootstrap/test_local_bootstrap.py -v`

Expected: FAIL because `initialize_local_schema` does not exist.

- [ ] **Step 6: Implement `initialize_local_schema(settings: Settings) -> None`**

Place it in `app/bootstrap/database.py`. Reject `broker`, permit only SQLite in local modes, create `Base.metadata`, then dispose the engine. Add `main() -> None` in `app/entrypoints/local_bootstrap.py` for `uv run python -m app.entrypoints.local_bootstrap`.

- [ ] **Step 7: Verify Task 1**

Run: `uv run pytest tests/unit/bootstrap/test_settings.py tests/unit/bootstrap/test_local_bootstrap.py -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add app/bootstrap/settings.py app/bootstrap/database.py app/entrypoints/local_bootstrap.py tests/unit/bootstrap/test_settings.py tests/unit/bootstrap/test_local_bootstrap.py
git commit -m "feat: add local runtime settings"
```

### Task 2: Safe filesystem object storage

**Files:**
- Create: `app/platform/asset_storage/local.py`
- Create: `tests/unit/platform/asset_storage/test_local_storage.py`

**Interfaces:**
- Consumes: `StorageMetadata`, `StorageError` from `app.platform.asset_storage.storage`.
- Produces: `LocalStorageAdapter(root: Path)` with `upload_object`, `download_object`, and `delete_object` signatures matching `StorageAdapter`.

- [ ] **Step 1: Write failing storage tests**

```python
def test_local_storage_round_trips_server_generated_key(tmp_path):
    storage = LocalStorageAdapter(tmp_path)
    result = storage.upload_object(bucket="documents", key="documents/markdown/id", data=b"body", content_type="text/plain")
    assert result.key == "documents/markdown/id"
    assert storage.download_object(bucket="documents", key=result.key) == b"body"

@pytest.mark.parametrize("key", ["../escape", "/tmp/escape", "a/../../escape"])
def test_local_storage_rejects_path_escape(tmp_path, key):
    with pytest.raises(StorageError):
        LocalStorageAdapter(tmp_path).upload_object(bucket="documents", key=key, data=b"x", content_type="text/plain")
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/unit/platform/asset_storage/test_local_storage.py -v`

Expected: FAIL because `LocalStorageAdapter` does not exist.

- [ ] **Step 3: Implement local storage**

Resolve every target under the configured root and reject anything outside it, including symlink escapes. Create parent directories, write to a temporary sibling, atomically replace it, and wrap filesystem errors in `StorageError`. Never return an absolute local path.

- [ ] **Step 4: Add missing/delete/symlink tests and verify Task 2**

Run: `uv run pytest tests/unit/platform/asset_storage/test_local_storage.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add app/platform/asset_storage/local.py tests/unit/platform/asset_storage/test_local_storage.py
git commit -m "feat: add local object storage"
```

### Task 3: Reusable executors and inline submitters

**Files:**
- Create: `app/features/web_crawl/application/execution.py`
- Create: `app/features/image_download/application/execution.py`
- Modify: `app/features/web_crawl/worker/task.py`
- Modify: `app/features/image_download/worker/task.py`
- Create: `app/local_runtime/__init__.py`
- Create: `app/local_runtime/submitters.py`
- Create: `tests/unit/local_runtime/test_inline_submitters.py`
- Modify: `tests/unit/features/web_crawl/test_crawl_worker.py`
- Modify: `tests/unit/features/image_download/test_media_worker.py`

**Interfaces:**
- Consumes: existing `CrawlJobSubmitter`, `MediaJobSubmitter`, `Job`, `MediaJob`, Task 2 storage, and existing feature service/downloader logic.
- Produces: Celery-independent `execute_crawl_job(...) -> str | None`, `execute_media_job(...) -> str | None`, `InlineCrawlJobSubmitter.submit(...) -> CrawlJobSubmission`, and `InlineMediaJobSubmitter.submit(...) -> MediaJobSubmission`.

- [ ] **Step 1: Write failing import-isolation tests**

```python
def test_crawl_execution_module_does_not_import_celery():
    module = import_module("app.features.web_crawl.application.execution")
    assert callable(module.execute_crawl_job)
    assert "app.entrypoints.celery_worker" not in sys.modules
```

Mirror this test for image execution.

- [ ] **Step 2: Verify import-isolation tests fail**

Run: `uv run pytest tests/unit/local_runtime/test_inline_submitters.py::test_crawl_execution_module_does_not_import_celery -v`

Expected: FAIL because the execution module does not exist.

- [ ] **Step 3: Extract shared execution**

Move worker dependency composition and `execute_*_job` to the application execution modules. Select Task 2 storage for local modes and existing `StorageAdapter(endpoint_url=settings.minio_endpoint)` for broker mode. Keep task files as Celery imports plus registrations only, preserving current imports used by existing tests.

- [ ] **Step 4: Write failing inline-submitter tests**

```python
def test_inline_crawl_submitter_commits_executes_and_returns_terminal_status(session_factory):
    submitter = InlineCrawlJobSubmitter(session_factory=session_factory, execute=complete_job)
    result = submitter.submit(url="https://example.test", caller_id="c1", idempotency_key="k1")
    assert result.status == "completed"

def test_inline_idempotency_replay_does_not_execute_twice(session_factory):
    execute = Mock(side_effect=complete_job)
    submitter = InlineCrawlJobSubmitter(session_factory=session_factory, execute=execute)
    submitter.submit(url="https://example.test", caller_id="c1", idempotency_key="k1")
    submitter.submit(url="https://example.test", caller_id="c1", idempotency_key="k1")
    execute.assert_called_once()
```

Add equivalent media and executor-failure tests.

- [ ] **Step 5: Verify inline tests fail**

Run: `uv run pytest tests/unit/local_runtime/test_inline_submitters.py -v`

Expected: FAIL because inline submitters do not exist.

- [ ] **Step 6: Implement inline submitters**

Compose the current durable submitters with a post-commit inline callback. Execute only a newly created job, then reload `Job` or `MediaJob` and return its persisted terminal/safe status. An idempotency replay must not enqueue, execute or retry.

- [ ] **Step 7: Verify Task 3 and existing worker behavior**

Run: `uv run pytest tests/unit/local_runtime/test_inline_submitters.py tests/unit/features/web_crawl/test_crawl_worker.py tests/unit/features/image_download/test_media_worker.py -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add app/features/web_crawl/application/execution.py app/features/image_download/application/execution.py app/features/web_crawl/worker/task.py app/features/image_download/worker/task.py app/local_runtime tests/unit/local_runtime/test_inline_submitters.py tests/unit/features/web_crawl/test_crawl_worker.py tests/unit/features/image_download/test_media_worker.py
git commit -m "feat: add inline local job execution"
```

### Task 4: Single-process DB-only worker

**Files:**
- Create: `app/entrypoints/database_worker.py`
- Create: `tests/unit/entrypoints/test_database_worker.py`
- Modify: `app/features/web_crawl/application/execution.py`
- Modify: `app/features/image_download/application/execution.py`

**Interfaces:**
- Consumes: Task 3 executors and Task 1 settings/session factory.
- Produces: `run_once(*, session_factory, crawl_executor, media_executor) -> bool` and `main() -> None` in `app.entrypoints.database_worker`.

- [ ] **Step 1: Write failing DB-runner tests**

```python
def test_run_once_claims_pending_crawl_and_completes_it(session_factory):
    create_pending_crawl(session_factory)
    assert run_once(session_factory=session_factory, crawl_executor=complete_crawl, media_executor=complete_media) is True
    assert load_job(session_factory).status == "completed"

def test_run_once_claims_pending_media_and_completes_it(session_factory):
    create_pending_media(session_factory)
    assert run_once(session_factory=session_factory, crawl_executor=complete_crawl, media_executor=complete_media) is True
    assert load_media_job(session_factory).status == "completed"
```

Also test no pending work returns `False` and executor receives an already claimed ID.

- [ ] **Step 2: Verify DB-runner tests fail**

Run: `uv run pytest tests/unit/entrypoints/test_database_worker.py -v`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement database runner**

Atomically claim one pending crawl or media record, commit the claim, execute it through Task 3, and commit a terminal state. `main()` polls at a bounded configurable interval and has no concurrency flag. It rejects `broker`, imports no Celery, creates no S3 client, and initializes no `SearchService`.

- [ ] **Step 4: Adjust executors for claimed jobs**

Allow a claimed `queued` job to move to `running` then terminal while retaining existing Celery behavior for `pending`. Terminal/cancelled records remain no-ops and cannot execute twice.

- [ ] **Step 5: Verify Task 4**

Run: `uv run pytest tests/unit/entrypoints/test_database_worker.py tests/unit/local_runtime/test_inline_submitters.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add app/entrypoints/database_worker.py app/features/web_crawl/application/execution.py app/features/image_download/application/execution.py tests/unit/entrypoints/test_database_worker.py
git commit -m "feat: add database local worker"
```

### Task 5: API composition and response contracts

**Files:**
- Modify: `app/legacy_api/main.py`
- Modify: `app/legacy_api/routers/crawl_jobs.py`
- Modify: `app/legacy_api/routers/media_jobs.py`
- Modify: `app/legacy_api/routers/search.py`
- Modify: `tests/unit/legacy_api/test_crawl_api.py`
- Modify: `tests/unit/legacy_api/test_media_api.py`
- Modify: `tests/unit/legacy_api/test_search_api.py`

**Interfaces:**
- Consumes: Task 1 settings and Task 3 submitters.
- Produces: `create_app(Settings(runtime_mode=...))` with mode-specific submitters and `app.state.job_submission_status_code: int`.

- [ ] **Step 1: Write failing API mode tests**

```python
def test_inline_crawl_api_returns_terminal_status_with_200(tmp_path):
    app = create_app(Settings(runtime_mode="inline", database_url=f"sqlite:///{tmp_path / 'api.db'}"))
    with TestClient(app) as client:
        response = client.post("/v1/crawl-jobs", headers=headers, json={"url": "https://example.test"})
    assert response.status_code == 200
    assert response.json()["status"] in {"completed", "failed", "blocked_policy"}

def test_db_worker_api_returns_pending_202_without_constructing_celery(tmp_path, monkeypatch):
    monkeypatch.setattr("app.legacy_api.main.create_celery_app", fail_if_called)
    app = create_app(Settings(runtime_mode="db-worker", database_url=f"sqlite:///{tmp_path / 'api.db'}"))
    assert app.state.job_submission_status_code == 202

def test_local_search_disabled_returns_503_without_provider_call(tmp_path):
    app = create_app(Settings(runtime_mode="inline", database_url=f"sqlite:///{tmp_path / 'api.db'}"))
    assert TestClient(app).get("/v1/search?q=x").status_code == 503
```

Use controlled executors/services only; no test calls the network.

- [ ] **Step 2: Verify API tests fail**

Run: `uv run pytest tests/unit/legacy_api/test_crawl_api.py tests/unit/legacy_api/test_media_api.py tests/unit/legacy_api/test_search_api.py -v`

Expected: FAIL because API composition always creates Celery submitters and routers always return `202`.

- [ ] **Step 3: Implement mode selection in `create_app`**

Retain current `broker` composition exactly. For `inline`, install Task 3 submitters. For `db-worker`, install durable submitters whose post-commit dispatch is a no-op. Populate one app-state status value (`200` inline, `202` otherwise). Do not construct `SearchService` when search is disabled.

- [ ] **Step 4: Implement router status selection**

Set response status from app state while retaining current response fields and default `202` OpenAPI declaration. Do not expose runtime config or any URL.

- [ ] **Step 5: Verify Task 5**

Run: `uv run pytest tests/unit/legacy_api/test_crawl_api.py tests/unit/legacy_api/test_media_api.py tests/unit/legacy_api/test_search_api.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add app/legacy_api/main.py app/legacy_api/routers/crawl_jobs.py app/legacy_api/routers/media_jobs.py app/legacy_api/routers/search.py tests/unit/legacy_api/test_crawl_api.py tests/unit/legacy_api/test_media_api.py tests/unit/legacy_api/test_search_api.py
git commit -m "feat: compose local API runtime modes"
```

### Task 6: Operator documentation and final verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `STARTUP.md`
- Modify: `.gitignore` only if `.runtime/` is not already ignored

**Interfaces:**
- Consumes: commands from Tasks 1 and 4 and runtime modes from Task 1.
- Produces: documented SQLite bootstrap, inline API, DB-worker API/worker commands, and limitations.

- [ ] **Step 1: Add no-Docker instructions**

Document SQLite/local storage variables and these commands:

```bash
APP_RUNTIME_MODE=inline uv run python -m app.entrypoints.local_bootstrap
APP_RUNTIME_MODE=inline uv run uvicorn app.legacy_api.main:create_app --factory --reload
```

Add separate API and `database_worker` commands for `db-worker`. Keep Docker instructions intact. State that Search is disabled without a provider, inline waits for remote work, and DB worker is single-process with no retry/DLQ guarantee.

- [ ] **Step 2: Run focused local-runtime tests**

Run: `uv run pytest tests/unit/bootstrap/test_settings.py tests/unit/bootstrap/test_local_bootstrap.py tests/unit/platform/asset_storage/test_local_storage.py tests/unit/local_runtime/test_inline_submitters.py tests/unit/entrypoints/test_database_worker.py tests/unit/legacy_api/test_crawl_api.py tests/unit/legacy_api/test_media_api.py tests/unit/legacy_api/test_search_api.py -v`

Expected: PASS.

- [ ] **Step 3: Run repository verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pytest`

Expected: all checks PASS; only explicitly Docker-dependent tests may be skipped.

- [ ] **Step 4: Review diff and commit Task 6**

Run: `git diff --check && git status --short`

Review only planned paths, then:

```bash
git add .env.example README.md STARTUP.md .gitignore docs/superpowers/specs/2026-11-10-local-runtime-modes-design.md docs/superpowers/plans/2026-11-10-local-runtime-modes.md
git commit -m "docs: document local runtime modes"
```

## Self-review

- **Spec coverage:** Tasks 1–5 cover modes, SQLite bootstrap, filesystem storage, shared execution, inline API behavior, DB worker behavior, disabled search, and broker compatibility. Task 6 documents commands and limitations.
- **Step scan:** Every task starts with a failing test, has a precise implementation boundary, runs focused tests, and commits reviewed paths.
- **Type consistency:** Task 1 configuration is used by Tasks 3–5; Task 2 storage is selected by Task 3; Task 3 executors are consumed by Tasks 4–5; Task 4 commands are documented by Task 6.
- **Review Focus:** All five risks have a named owning task and test/documentation check.
- **Proportion:** The plan specifies interfaces and tests without transcribing implementation bodies.
