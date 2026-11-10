# MVP v1 Worker Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a parallel, worker-first MVP v1 for `search`, `crawl_url`, and bounded `search_and_extract`, with PostgreSQL as the durable authority and without enabling browser or media workflows.

**Architecture:** Keep the current FastAPI/API-centric runtime and its `crawl`/`media` queues untouched as a transitional system. Add an isolated MVP v1 worker path: a producer submits a versioned `WorkflowRequest`; Workflow Orchestration creates only `JobIntent`s; Job Orchestration atomically stores a typed durable command, `FeatureJob`, and outbox event; Queue Management delivers an ID-only message to Search or Web Crawl workers. The v1 worker path uses only static HTTP crawling, and its output is a safe durable result reference.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, PostgreSQL, Redis/Celery, HTTPX, Pydantic 2, pytest, respx.

**Spec:** `docs/platform/workflow-orchestration.md`, `docs/platform/job-orchestration.md`, `docs/platform/queue-management.md`, `docs/platform/network-policy.md`, `docs/features/search.md`, and `docs/features/web-crawl.md`.

## Global Constraints

- MVP v1 permits only `search`, `crawl_url`, and bounded `search_and_extract` with static document classification.
- MVP v1 excludes browser actions, media child jobs, recursive links, schedules, torrent work, request-provided selectors/JavaScript/cookies/credentials, and public API contract changes.
- Queue messages contain only `job_id`, `feature_code`, `contract_version`, and `correlation_id`; typed commands and result URLs remain durable records.
- PostgreSQL is the job, command, outbox, lease, retry, and audit source of truth; Redis/Celery is at-least-once transport only.
- Only Workflow Orchestration may create downstream `JobIntent`s; Search and Web Crawl workers never call another feature or queue.
- Network Policy gates every initial URL and redirect; blocked, validation, malformed-command, and cancellation outcomes are terminal and never retry.
- Migrations are additive. Do not drop or repurpose the current `jobs`, `crawl_jobs`, `media_*`, legacy API routes, or current `crawl`/`media` queues in this plan.
- Do not add dependencies. Tests must not call the public network.

## Review Focus

- A duplicate `search_and_extract` request with the same idempotency scope must return its original workflow/run and create no more child jobs — Task 6.
- A queued message with a missing, malformed, cancelled, or terminal command must be durably resolved before acknowledgement and make no network call — Task 3.
- A redirect whose re-resolved address becomes private must produce a terminal policy block before HTTPX follows it — Task 4.
- A crashed worker after document upload but before the outcome commit must leave no orphan object and permit safe lease reclaim — Tasks 3 and 5.
- A result with a URL containing a query string must remain in durable feature storage only and never appear in a queue payload, result event, log, or test assertion output — Tasks 2, 5, and 7.

---

## Current-state findings that constrain this plan

- The package layout exists, but the actual durable model is legacy `Job`/`CrawlJob`; it has no typed command, feature contract version, correlation ID, outbox, lease, retry schedule, or DLQ audit. See `app/platform/persistence/models.py` and `alembic/versions/0001_initial_schema.py`.
- `app/entrypoints/celery_worker.py` routes generic `crawl`, `media`, and `torrent` work. Search has no worker, and `SearchService.crawl_selected()` directly invokes `CrawlService`, violating the target cross-feature boundary.
- `CrawlService` performs submit, network execution, persistence, and completion in one call. `process_crawl_job()` catches every error as generic `failed`; it has no durable outcome/outbox/ack ordering.
- Static fetching has manual redirects and byte/type limits, but the policy API lacks allowlist, robots, and quota ports. Browser fixture code exists and must not be wired into MVP v1.
- `uv run pytest` currently reports **199 passed, 16 skipped, 5 failed**. The failures are caused by the developer `.env` supplying `runtime_mode=inline` and a secret to tests that construct implicit `Settings()` and expect clean broker/default settings. Ruff check and format check pass.

## File Structure

| Area | Files | Responsibility |
|---|---|---|
| Test isolation and docs | Selected settings/API tests, `README.md`, `docs/INDEX.md`, feature/workflow/release docs | Make tests independent of a developer `.env`; make the MVP boundary unambiguous. |
| Contracts | `app/shared/contracts/jobs.py`, `app/shared/contracts/workflows.py` | Frozen Pydantic models for safe queue envelopes, commands, outcomes, and workflow requests/results. |
| Durable platform | `app/platform/persistence/models.py`, `app/platform/job_orchestration/service.py`, `app/platform/queue_management/*`, new Alembic revision | Feature-job lifecycle, command/outbox persistence, lease, retry scheduling, DLQ authorization/audit. |
| Workflow | `app/platform/workflow_orchestration/*` | Registered MVP definitions, bounded selection, parent/step persistence, and downstream intent creation. |
| Features | `app/features/search/*`, `app/features/web_crawl/*`, `app/platform/document_storage/service.py` | One target execution path per MVP feature, safe result references, static crawl and atomic cleanup. |
| Worker runtime | `app/entrypoints/worker_v1.py`, target worker tasks, `docker-compose.yml` | New versioned queues and consumers, isolated from current legacy queue topology. |
| Verification | `tests/unit/platform/...`, `tests/integration/...`, controlled compose tests and docs tests | Contract, durability, safety, and v1-only regression coverage. |

### Task 1: Stabilize the baseline and label the v1 boundary

**Files:**
- Modify: `tests/unit/bootstrap/test_local_bootstrap.py`
- Modify: `tests/unit/bootstrap/test_settings.py`
- Modify: `tests/unit/legacy_api/test_crawl_api.py`
- Modify: `tests/unit/legacy_api/test_media_api.py`
- Modify: `README.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/features/web-crawl.md`
- Modify: `docs/release-signoff.md`

**Interfaces:**
- Consumes: `Settings` as the application’s configuration boundary.
- Produces: a test suite that never reads a developer’s `.env` unless a test explicitly opts in, and a single documented MVP v1 scope.

- [ ] **Step 1: Write failing regression tests for configuration isolation**

Make tests that assert default behavior explicitly construct `Settings(_env_file=None)`. Cover the current five failures: broker-only schema bootstrap, production-without-secret validation, and default asynchronous `202` behavior for injected crawl/media submitters.

- [ ] **Step 2: Run the five currently failing tests and verify they fail because local `.env` changes the implicit `Settings()` values**

Run: `uv run pytest tests/unit/bootstrap/test_local_bootstrap.py::test_initialize_local_schema_rejects_broker_mode tests/unit/bootstrap/test_settings.py::test_settings_production_requires_secret tests/unit/legacy_api/test_crawl_api.py::test_create_crawl_job_returns_pending_job_id_without_fetching tests/unit/legacy_api/test_crawl_api.py::test_app_composes_durable_crawl_submitter_from_settings tests/unit/legacy_api/test_media_api.py::test_create_direct_media_job_returns_pending_job_id -v`

Expected: FAIL before isolation; the effective settings report `runtime_mode=inline` and a configured secret.

- [ ] **Step 3: Isolate test configuration without changing production `Settings` behavior**

Make every default-setting test instantiate `Settings(_env_file=None)` through a shared test helper/fixture, or explicitly pass broker settings to `create_app`. Do not remove `.env` loading from `Settings`; local runtime documentation depends on it.

- [ ] **Step 4: Update docs to name the phase `MVP v1` and remove version leakage**

In `docs/INDEX.md`, add a compact MVP v1/v1.1/v1.2 table. Mark browser fallback, `extract_images`, Image Download, and Video Download as post-MVP. In the Web Crawl and release docs, state that browser fallback is not wired or tested as MVP v1 behavior.

- [ ] **Step 5: Verify baseline tests and documentation assertions**

Run: `uv run pytest tests/unit/bootstrap tests/unit/legacy_api tests/unit/test_release_docs.py -v`

Expected: PASS with no dependency on `.env` contents.

- [ ] **Step 6: Commit the isolated baseline**

```bash
git add tests/unit/bootstrap tests/unit/legacy_api README.md docs/INDEX.md docs/features/web-crawl.md docs/release-signoff.md
git commit -m "docs: define worker MVP v1 boundary"
```

### Task 2: Define the versioned durable contracts and additive schema

**Files:**
- Create: `app/shared/__init__.py`
- Create: `app/shared/contracts/__init__.py`
- Create: `app/shared/contracts/jobs.py`
- Create: `app/shared/contracts/workflows.py`
- Modify: `app/platform/persistence/models.py`
- Create: `alembic/versions/0002_worker_v1_jobs.py`
- Create: `tests/unit/shared/contracts/test_jobs.py`
- Create: `tests/unit/platform/persistence/test_worker_v1_migration.py`

**Interfaces:**
- Produces: `QueueMessageV1(job_id, feature_code, contract_version, correlation_id)`, feature command models, `ExecutionOutcome`, `JobIntent`, `WorkflowRequest`, and safe result-reference models.
- Produces: additive `feature_jobs`, `job_commands`, `outbox_events`, `job_leases`, `workflow_runs`, `workflow_steps`, and `search_result_sets` persistence models; do not use the legacy `Job` table for target v1 jobs.
- Consumes: no raw URL/query/cookie/credential in `QueueMessageV1`, outbox payload, or result event.

- [ ] **Step 1: Write failing serialization and migration tests**

Test that queue serialization rejects unknown fields and serializes only the four envelope fields; test command/outcome validation; upgrade an empty PostgreSQL/SQLite test schema and assert all new tables/indexes exist while legacy tables remain.

- [ ] **Step 2: Run the focused tests and verify missing contracts/migration fail**

Run: `uv run pytest tests/unit/shared/contracts/test_jobs.py tests/unit/platform/persistence/test_worker_v1_migration.py -v`

Expected: FAIL because the v1 models and migration do not exist.

- [ ] **Step 3: Implement frozen Pydantic contracts and SQLAlchemy models**

Use `feature_code` values `search` and `web_crawl` only in executable MVP definitions. Store raw command JSON only in `job_commands`; persist `contract_version`, correlation ID, idempotency scope/key, safe reason code, result reference, `next_run_at`, and cancellation state on `feature_jobs`. Make the outbox store an event type plus the four-field `QueueMessageV1`, never command payload.

- [ ] **Step 4: Add the additive Alembic revision**

Add foreign keys and indexes needed for idempotency lookup, pending-outbox publication, eligible retry scheduling, active lease lookup, workflow-step lookup, and search-result-set ownership. Include a downgrade that removes only this revision’s tables/indexes.

- [ ] **Step 5: Verify contract redaction and migration compatibility**

Run: `uv run pytest tests/unit/shared/contracts/test_jobs.py tests/unit/platform/persistence/test_worker_v1_migration.py tests/unit/platform/document_storage/test_migrations.py -v`

Expected: PASS; no assertion may require a URL/query in a queue event.

- [ ] **Step 6: Commit the durable contract boundary**

```bash
git add app/shared app/platform/persistence/models.py alembic/versions/0002_worker_v1_jobs.py tests/unit/shared tests/unit/platform/persistence
git commit -m "feat: add worker v1 durable contracts"
```

### Task 3: Implement Job and Queue orchestration with outbox, lease, retry, and cancellation

**Files:**
- Modify: `app/platform/job_orchestration/service.py`
- Create: `app/platform/job_orchestration/repository.py`
- Modify: `app/platform/queue_management/tasks.py`
- Modify: `app/platform/queue_management/retry.py`
- Create: `app/platform/queue_management/service.py`
- Create: `app/platform/queue_management/repository.py`
- Create: `tests/unit/platform/job_orchestration/test_worker_v1_jobs.py`
- Create: `tests/unit/platform/queue_management/test_worker_v1_delivery.py`
- Create: `tests/integration/platform/test_worker_v1_durability.py`

**Interfaces:**
- Produces: `JobOrchestrationService.submit(intent)`, `request_cancel(job_id, caller_context)`, and `commit_outcome(job_id, lease_id, outcome)`.
- Produces: `QueueManagementService.publish_pending()`, `acquire_lease(message, worker_id)`, `commit_and_ack(...)`, `schedule_due_retries()`, `reclaim_expired_leases()`, and audited `requeue_dead_letter(...)`.
- Consumes: the v1 contracts from Task 2; feature services return `ExecutionOutcome` only.

- [ ] **Step 1: Write failing lifecycle tests**

Cover atomic job/command/outbox creation; idempotent repeat submit; one winner under two concurrent lease attempts; outbox redelivery without a duplicate job; stale delivery after cancellation; missing/malformed command terminal handling; crash-before-commit and crash-after-commit/before-ack behavior; expired lease reclaim; typed retry scheduling; terminal validation/policy/cancellation; authorized DLQ requeue with audit.

- [ ] **Step 2: Run lifecycle tests to establish the red state**

Run: `uv run pytest tests/unit/platform/job_orchestration/test_worker_v1_jobs.py tests/unit/platform/queue_management/test_worker_v1_delivery.py tests/integration/platform/test_worker_v1_durability.py -v`

Expected: FAIL because current `JobService` has no command/outbox/lease state and retry is string matching.

- [ ] **Step 3: Implement transaction-scoped Job Orchestration**

Create a `FeatureJob`, typed `JobCommand`, and request `OutboxEvent` in one database transaction. Return existing rows for an identical idempotency scope/key. Do not invoke a worker, queue publisher, or network client from this transaction.

- [ ] **Step 4: Implement Queue Management around durable state**

Publish only unconfirmed outbox records; acquire a PostgreSQL lease atomically; load the command after lease acquisition; commit the outcome/result outbox before acknowledging the broker delivery. Replace `RetryService.should_retry(BaseException)` keyword matching with classification on typed error/reason codes. Send only exhausted transient attempts to a non-auto-consumed DLQ.

- [ ] **Step 5: Verify durability failure boundaries**

Run: `uv run pytest tests/unit/platform/job_orchestration/test_worker_v1_jobs.py tests/unit/platform/queue_management/test_worker_v1_delivery.py tests/integration/platform/test_worker_v1_durability.py -v`

Expected: PASS, including lease contention, both commit crash boundaries, terminal non-retry, and authorization-required requeue.

- [ ] **Step 6: Commit the lifecycle platform**

```bash
git add app/platform/job_orchestration app/platform/queue_management tests/unit/platform/job_orchestration tests/unit/platform/queue_management tests/integration/platform
git commit -m "feat: add durable worker job delivery"
```

### Task 4: Make Network Policy the injected gate for static v1 crawling

**Files:**
- Modify: `app/platform/network_policy/policy.py`
- Create: `app/platform/network_policy/ports.py`
- Modify: `app/features/web_crawl/infrastructure/static_fetcher.py`
- Modify: `app/features/web_crawl/application/service.py`
- Create: `tests/unit/platform/network_policy/test_worker_v1_policy.py`
- Modify: `tests/unit/features/web_crawl/test_static_fetcher.py`

**Interfaces:**
- Produces: an injected `NetworkPolicyService.authorize(PolicyCommand) -> ApprovedRequest | PolicyDecision` with DNS, allowlist/source, quota, and robots ports.
- Consumes: an approved initial request and evaluates every redirect target before the next HTTP request.
- Does not produce: any browser adapter, caller-provided browser input, or policy bypass.

- [ ] **Step 1: Write failing policy/fetch tests**

Cover scheme/port/user-info, every A/AAAA record, redirect-to-private and DNS revalidation, allowlist/source denial, Web Crawl robots denial, quota denial, and a fetcher called without an approved initial request.

- [ ] **Step 2: Run the focused policy/fetch tests to verify gaps**

Run: `uv run pytest tests/unit/platform/network_policy/test_worker_v1_policy.py tests/unit/features/web_crawl/test_static_fetcher.py -v`

Expected: FAIL for unavailable policy ports and the current fetcher’s direct URL API.

- [ ] **Step 3: Implement ports and policy decisions without network access in unit tests**

Inject DNS, robots, allowlist, and quota implementations. The production adapter may use real DNS/robots, but all unit tests use controlled fakes. Have `StaticFetcher` accept only the policy-approved request/context and return redirects to the policy service for reauthorization; update the legacy `CrawlService` composition to request that approved object, preserving its public API.

- [ ] **Step 4: Verify policy enforcement and static-only execution**

Run: `uv run pytest tests/unit/platform/network_policy tests/unit/features/web_crawl/test_static_fetcher.py -v`

Expected: PASS; every test is offline and a blocked redirect performs no follow-up request.

- [ ] **Step 5: Commit the policy boundary**

```bash
git add app/platform/network_policy app/features/web_crawl/application/service.py app/features/web_crawl/infrastructure/static_fetcher.py tests/unit/platform/network_policy tests/unit/features/web_crawl/test_static_fetcher.py
git commit -m "feat: gate static crawl requests by policy"
```

### Task 5: Implement the Web Crawl v1 worker path and safe document persistence

**Files:**
- Create: `app/features/web_crawl/application/worker_service.py`
- Modify: `app/features/web_crawl/worker/task.py`
- Modify: `app/platform/document_storage/service.py`
- Modify: `app/platform/asset_storage/storage.py`
- Create: `tests/unit/features/web_crawl/test_worker_v1_service.py`
- Modify: `tests/unit/platform/document_storage/test_persistence.py`
- Modify: `tests/unit/features/web_crawl/test_crawl_worker.py`

**Interfaces:**
- Consumes: a leased durable `WebCrawlCommand` and the `ApprovedRequest` contract from Task 4.
- Produces: `ExecutionOutcome.completed(result_reference=document_id)` or a typed terminal/transient outcome; no direct queue call and no child job.
- Produces: document deduplication by `(canonical_url, content_hash)`, server-generated HTML/Markdown keys, and compensating object cleanup on database failure.

- [ ] **Step 1: Write failing worker-service and persistence failure tests**

Test static fetch → normalize → classify → persist → typed outcome; document dedupe at the documented compound key; cancellation checkpoints before fetch and before persistence; policy/content failures as terminal; transient storage failure classification; object cleanup after a database flush/commit failure; and no browser task route or browser invocation from the v1 worker.

- [ ] **Step 2: Run focused Web Crawl tests and verify they fail on the legacy execution path**

Run: `uv run pytest tests/unit/features/web_crawl/test_worker_v1_service.py tests/unit/features/web_crawl/test_crawl_worker.py tests/unit/platform/document_storage/test_persistence.py -v`

Expected: FAIL because `CrawlService` creates legacy jobs and returns dictionaries instead of typed outcomes.

- [ ] **Step 3: Implement one static target execution path**

Keep the existing legacy `CrawlService` temporarily for the API baseline, but make the v1 worker task call only `WorkerWebCrawlService.execute(command, checkpoint)`. It must load the command after lease acquisition, check cancellation at documented checkpoints, use the injected policy/fetcher, and return an `ExecutionOutcome` to Queue Management.

- [ ] **Step 4: Correct document persistence transaction boundaries**

Store both generated object keys with document metadata. Use a compensating delete for every object written if the surrounding database transaction fails. Do not log document body, requested URL query, or signed storage URL.

- [ ] **Step 5: Verify the complete static crawl boundary**

Run: `uv run pytest tests/unit/features/web_crawl tests/unit/platform/document_storage -v`

Expected: PASS; the v1 worker has no browser route or invocation, and failed persistence leaves no stored object. The existing offline browser fixture remains deferred code, not MVP behavior.

- [ ] **Step 6: Commit Web Crawl v1**

```bash
git add app/features/web_crawl app/platform/document_storage app/platform/asset_storage tests/unit/features/web_crawl tests/unit/platform/document_storage
git commit -m "feat: add static web crawl worker v1"
```

### Task 6: Implement Search v1 and the bounded MVP workflow definitions

**Files:**
- Create: `app/features/search/domain/models.py`
- Create: `app/features/search/domain/ports.py`
- Create: `app/features/search/application/worker_service.py`
- Create: `app/features/search/infrastructure/searxng_provider.py`
- Create: `app/features/search/worker/task.py`
- Create: `app/platform/workflow_orchestration/__init__.py`
- Create: `app/platform/workflow_orchestration/service.py`
- Create: `app/platform/workflow_orchestration/definitions.py`
- Create: `tests/unit/features/search/test_worker_v1_service.py`
- Create: `tests/unit/platform/workflow_orchestration/test_mvp_v1_workflows.py`

**Interfaces:**
- Produces: `SearchWorkerService.execute(SearchCommand) -> ExecutionOutcome` and persists a `SearchResultSet` with a safe reference.
- Produces: `WorkflowOrchestrationService.start(WorkflowRequest) -> WorkflowRun` and `advance_from_outcome(job_id, outcome) -> WorkflowRun`.
- Consumes: `JobOrchestrationService.submit(JobIntent)`; it is the only call that creates feature jobs.

- [ ] **Step 1: Write failing feature and workflow tests**

Cover Search query/page/limit validation, provider timeout/malformed response mapping, normalization/deduplication, result persistence, and the invariant that a Search worker creates no crawl intent. Cover all three registered definitions: `search`, `crawl_url`, and `search_and_extract`; for the latter, use a fixed server-registered top-N selection rule with explicit count/time/byte budgets and verify duplicate requests do not fan out again.

- [ ] **Step 2: Run focused Search/workflow tests and verify they fail**

Run: `uv run pytest tests/unit/features/search/test_worker_v1_service.py tests/unit/platform/workflow_orchestration/test_mvp_v1_workflows.py -v`

Expected: FAIL because `SearchService` returns a list directly and exposes `crawl_selected()` with a direct crawl-service dependency.

- [ ] **Step 3: Implement Search as a standalone worker feature**

Create a provider port/adapter, validate and normalize through the worker service, persist a result set and query hash, and return only a safe result reference. Do not inject a crawl service, queue publisher, or workflow service into Search.

- [ ] **Step 4: Implement registered v1 workflow definitions**

Hard-code only reviewed, versioned definitions in `definitions.py`. `search` ends with `SearchResultSet`; `crawl_url` creates one `WebCrawlJob`; `search_and_extract` waits for Search completion, selects only within its registered budget, and creates bounded crawl `JobIntent`s through Job Orchestration. Reject browser/media/recursive/scheduled request types.

- [ ] **Step 5: Verify workflow boundaries**

Run: `uv run pytest tests/unit/features/search/test_worker_v1_service.py tests/unit/platform/workflow_orchestration/test_mvp_v1_workflows.py tests/unit/features/search/test_search_service.py -v`

Expected: PASS; retain legacy Search tests until the later API cutover, but no target v1 test permits direct Search-to-Crawl calls.

- [ ] **Step 6: Commit Search and Workflow MVP v1**

```bash
git add app/features/search app/platform/workflow_orchestration tests/unit/features/search tests/unit/platform/workflow_orchestration
git commit -m "feat: add bounded search and crawl workflows"
```

### Task 7: Wire isolated v1 queues, workers, observability, and controlled integration coverage

**Files:**
- Create: `app/entrypoints/worker_v1.py`
- Modify: `docker-compose.yml`
- Modify: `app/platform/observability/audit.py`
- Modify: `app/platform/observability/logging.py`
- Modify: `app/platform/observability/slo.py`
- Modify: `docs/platform/queue-management.md`
- Modify: `docs/platform/job-orchestration.md`
- Modify: `docs/platform/workflow-orchestration.md`
- Modify: `docs/features/search.md`
- Modify: `docs/features/web-crawl.md`
- Modify: `docs/release-signoff.md`
- Create: `tests/integration/worker_v1/test_search_and_extract.py`
- Create: `tests/integration/worker_v1/test_worker_v1_redelivery.py`
- Modify: `tests/unit/platform/queue_management/test_workers.py`

**Interfaces:**
- Produces: queues `search.execute.v1`, `web-crawl.execute.v1`, and `worker.maintenance.v1`; reserve explicit image/video queues without attaching MVP consumers if topology is provisioned now.
- Produces: a worker entrypoint that consumes only `QueueMessageV1` and calls Queue Management, not feature services directly.
- Preserves: current `app/entrypoints/celery_worker.py`, legacy API routes, and legacy queues until a separately approved producer/cutover plan.

- [ ] **Step 1: Write failing topology, redaction, and integration tests**

Assert v1 queue names and `acks_late`/prefetch settings; reject generic `media`/`torrent` routes in the v1 worker; assert audit/log/event serialization redacts raw query strings and command URLs; run Search → bounded selected crawls → aggregate result against controlled local HTTP/SearXNG fixtures; cover broker redelivery and expired-lease reclaim.

- [ ] **Step 2: Run v1 integration tests to establish missing worker behavior**

Run: `uv run pytest tests/unit/platform/queue_management/test_workers.py tests/integration/worker_v1 -v`

Expected: FAIL because the repository only has legacy generic queues and no v1 worker entrypoint.

- [ ] **Step 3: Add a separate v1 Celery composition root and Compose worker service**

Configure versioned queues, feature-specific routes, per-feature timeouts, late acknowledgement, and a maintenance consumer. Do not modify the legacy Celery app’s `crawl`, `media`, or `torrent` routes in this task. The Compose worker starts only after migrations and shares PostgreSQL/Redis/MinIO with the controlled test stack.

- [ ] **Step 4: Make operational outputs safe and align docs with the executable boundary**

Emit only job/workflow IDs, feature/version, safe reason codes, attempts, and duration metrics. Update docs so `<Feature>JobRequested v1` is the durable command/outbox event and `QueueMessageV1` is the four-field broker payload. State explicitly that only exhausted transient failures reach the DLQ.

- [ ] **Step 5: Verify controlled end-to-end worker delivery**

Run: `uv run pytest tests/integration/worker_v1 tests/unit/platform/queue_management/test_workers.py -v`

Expected: PASS with PostgreSQL/Redis-controlled fixtures; the test verifies no Search-to-Crawl direct call, no browser execution, redelivery safety, and safe aggregate references.

- [ ] **Step 6: Run the full supported quality gate**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`

Expected: all supported offline/unit/integration tests pass; Docker-dependent benchmark/E2E skips are reported separately and not treated as rollout evidence.

- [ ] **Step 7: Commit worker wiring and docs**

```bash
git add app/entrypoints/worker_v1.py app/platform/observability docker-compose.yml docs tests/integration/worker_v1 tests/unit/platform/queue_management
git commit -m "feat: wire worker platform MVP v1"
```

## Explicitly deferred

- Migrating or deleting `app/legacy_api`, legacy jobs, generic `crawl`/`media` queues, torrent/RSS code, and existing clients. This requires a separate producer contract and cutover/rollback decision.
- Browser recipes/fallback, image extraction/download, video download, recursive crawl, schedules, and any new HTTP endpoint.
- Production rollout, security sign-off, backup/restore drill, and external-site E2E. These require real-environment evidence after the implementation plan completes.

## Self-review

- **Spec coverage:** Tasks 2–7 map every MVP contract to durable models, queue delivery, Network Policy, Search, Web Crawl, bounded workflow fan-out, safe result handling, and documentation. Task 1 resolves the version ambiguity and current test baseline.
- **Step scan:** Every code task starts with a failing test, then focused verification; no task depends on an unspecified public API or external website.
- **Type consistency:** Tasks 2 and 3 define the only message (`QueueMessageV1`), job handoff (`JobIntent`), worker input (typed command), and worker output (`ExecutionOutcome`) used by Tasks 4–7.
- **Review focus coverage:** duplicate fan-out is Task 6; malformed/cancelled delivery and leases are Task 3; redirect safety is Task 4; persistence cleanup is Task 5; URL/query redaction is Tasks 2, 5, and 7.
- **Proportion:** The plan chooses one parallel v1 worker path rather than a simultaneous API cutover or media/browser implementation, so each task remains independently testable and reversible.
