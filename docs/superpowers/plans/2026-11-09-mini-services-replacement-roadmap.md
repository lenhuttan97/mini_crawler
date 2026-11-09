# Mini Services Replacement Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document how Mini Search and Mini Nextcloud evolve from temporary services without changing the current simple repository layout, and record deferred module extraction for Search, Crawl Data, Image and Video.

**Architecture:** Keep the present `services/`, `adapters/` and `workers/` layout. Update the two reference examples with a truthful temporary-provider/target-provider path, then add one reference roadmap for the whole repository. Physical feature modules remain a future, per-feature migration; no adapter interface, source code, runtime configuration or dependency is created now.

**Tech Stack:** Markdown documentation only; current runtime references Python, FastAPI, HTTPX, SearXNG, MinIO/S3-compatible storage and Celery.

**Spec:** `docs/superpowers/specs/2026-11-09-mini-services-replacement-roadmap-design.md`

## Global Constraints

- Modify Markdown under `docs/` only; do not change source code, tests, dependencies, Docker Compose or runtime configuration.
- Keep `docs/sample/` labelled as reference/roadmap material, never as an active worker implementation contract.
- The current repository remains physically organized as `app/services/`, `app/adapters/`, `app/workers/` and the transitional `app/api/`.
- Do not add `app/features/`, `app/platform/`, a provider port, a wrapper or a future configuration flag in this work.
- Current Mini Crawler storage remains MinIO/S3-compatible; Nextcloud must not be represented as a current runtime replacement.
- Search remains discovery-only in target workflow documentation; it must not be described as auto-crawling results.

## Review Focus

- **Runtime truth:** Each example must distinguish current Mini Crawler services from standalone learning/product targets; validate in Task 3 by checking required status language.
- **Nextcloud scope:** Nextcloud is a temporary baseline only for the future Mini Nextcloud project, never an instruction to replace crawler MinIO; validate in Task 2.
- **No premature abstraction:** The roadmap must forbid physical feature-module extraction and provider seams until a real second implementation exists; validate in Task 3.
- **All feature coverage:** Search, Crawl Data, Image and Video must appear in the deferred extraction table; validate in Task 3.
- **Workflow boundary:** Search replacement documentation must preserve “no auto-crawl”; validate in Task 1.

---

### Task 1: Reframe the Mini Search reference

**Files:**
- Modify: `docs/sample/MINI_SEARXNG_PYTHON.md`

**Interfaces:**
- Consumes: Current Search behavior in `app/services/search_service.py` and active Search contract in `docs/features/search.md`.
- Produces: A reference path from self-hosted SearXNG to a standalone Mini Search without claiming either a new crawler module or a current Mini Search implementation.

- [ ] Add a status section before the scope that identifies SearXNG as the current search provider and Mini Search as a future standalone target.
- [ ] Add a two-stage table: use SearXNG now through the current `SearchService`; only replace it after Mini Search preserves normalized results, timeout/error mapping and the discovery-only boundary.
- [ ] State that any provider seam is deferred until Mini Search exists, remains at the existing call site, and does not create `app/features/search/` now.
- [ ] Add explicit switch gates: controlled contract/integration tests, rollback to SearXNG and no raw provider payload/credential in result or job data.
- [ ] Check the rewritten page keeps the AGPL warning and does not state that Search automatically crawls result URLs.

### Task 2: Reframe the Mini Nextcloud reference

**Files:**
- Modify: `docs/sample/mini_nextcloud_architecture.md`

**Interfaces:**
- Consumes: Current `StorageAdapter`/`PersistenceService` use of MinIO/S3-compatible storage and `docs/platform/storage.md` boundaries.
- Produces: A reference path from self-hosted Nextcloud to a standalone Mini Nextcloud without replacing current crawler storage.

- [ ] Add a status section that separates the current Mini Crawler MinIO/S3 runtime from the separate Mini Nextcloud learning/product path.
- [ ] Add a two-stage table: use reviewed self-hosted Nextcloud through WebDAV/API before Mini Nextcloud exists; switch the standalone project only after equivalent safe file/object operations and tests.
- [ ] State that this is not a current crawler-storage migration, does not change server-generated object-key/result-reference rules, and creates no `app/features/nextcloud/` module.
- [ ] Add switch gates: controlled integration target, credential redaction, rollback to Nextcloud, and a separately approved data migration before any binary-object move.
- [ ] Check existing auth/ACL, upload and media safety guidance remains intact.

### Task 3: Add the repository-wide deferred-module roadmap and navigation

**Files:**
- Create: `docs/sample/mini-services-replacement-roadmap.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: The two revised examples, `docs/architecture/worker-crawler-rearchitecture.md`, `docs/features/search.md` and `docs/platform/storage.md`.
- Produces: One reference-only map from the simple current layout to future, independently migrated feature modules.

- [ ] Create the roadmap with a status notice: reference only; current repository keeps `app/services/`, `app/adapters/`, `app/workers/` and `app/api/`.
- [ ] Add a table covering Search, Crawl Data, Image and Video: current simple area, later `app/features/<feature>/` destination, and the rule that each moves only in an approved, reversible migration.
- [ ] Add a separate provider table that limits temporary/target substitution to SearXNG → Mini Search and self-hosted Nextcloud → Mini Nextcloud; state Crawl, Image and Video continue with their current direct implementation.
- [ ] Add module-extraction triggers: independent deployment/queue ownership, versioned contract need or repeated cross-directory change; forbid directory-only refactors.
- [ ] Add no-go rules: no module folders, no provider abstraction, no dual write, no automatic storage migration and no behavior change in this documentation phase.
- [ ] Link the roadmap and both examples from the `Reference material` section in `docs/INDEX.md`, retaining the existing disclaimer that they are not active implementation contracts.
- [ ] Verify required phrases/tables include all four features, MinIO remains current crawler storage, and no Markdown link points to a missing local file.

### Task 4: Validate documentation-only scope

**Files:**
- Review: `docs/sample/MINI_SEARXNG_PYTHON.md`
- Review: `docs/sample/mini_nextcloud_architecture.md`
- Review: `docs/sample/mini-services-replacement-roadmap.md`
- Review: `docs/INDEX.md`

- [ ] Run a local Markdown-link, heading hierarchy and code-fence checker for `README.md`, `STARTUP.md` and all `docs/**/*.md`.
- [ ] Run `git diff --check -- README.md STARTUP.md docs` plus an explicit whitespace check for newly created, untracked Markdown files.
- [ ] Inspect `git diff --name-only` and `git status --short` to confirm no source/config/test paths were changed for this roadmap work.

## Self-review

- **Spec coverage:** Tasks 1–2 establish the two provider replacement paths; Task 3 records the current simple layout and deferred per-feature extraction for all four capabilities; Task 4 validates navigation and scope.
- **Step scan:** Every change names its exact document and required truth boundary; no step asks for code or unspecified provider behavior.
- **Type consistency:** Current references use `SearchService`, `StorageAdapter`, `PersistenceService`, MinIO/S3-compatible storage and the deferred `app/features/search`, `web_crawl`, `image_download`, `video_download` paths consistently.
- **Review focus:** Task 1 covers Search’s discovery boundary, Task 2 covers Nextcloud/MinIO separation, Task 3 covers all-feature/module-deferral coverage and Task 4 validates documentation integrity.
- **Proportion:** The plan uses one new roadmap and focused status additions rather than duplicating active worker contracts or introducing a new architecture.
