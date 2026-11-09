# Learning Curriculum Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore and align the Beginner-to-Master learning path with the current repository and worker-first roadmap.

**Architecture:** Restore the existing detailed modules from Git, then add a consistent status boundary to each. Preserve current-tech practical learning, make workflow orchestration the advanced core, defer non-installed media/browser/AI/observability technologies explicitly, and place Search & Crawl as the final capstone.

**Tech Stack:** Markdown only; curriculum covers Python 3.12, uv, Pydantic, FastAPI, HTTPX, selectolax, markdownify, PostgreSQL, SQLAlchemy, Alembic, Redis, Celery, MinIO, structlog, pytest, respx and Ruff.

**Spec:** `docs/superpowers/specs/2026-11-09-learning-curriculum-design.md`

## Global Constraints

- Only modify Markdown under `docs/`; do not change code, configuration or dependencies.
- Restore the deleted learning files from Git before revising their content.
- Mark any absent dependency or deferred capability honestly; never imply it runs today.
- Use controlled fixtures/authorized targets only; retain all SSRF, policy, DRM and access-control boundaries.

## Review Focus

- A beginner must not interpret FastAPI exercises as the target worker entrypoint.
- A learner must not install/run browser or media tooling from an example presented as already supported.
- `search_and_extract` must be explicit and bounded; standalone Search must not auto-crawl.
- Workflow Orchestration must not be described as a second retry/lease/job lifecycle.
- Links from the learning index and module transitions must resolve after module 03 is repurposed and Search moves to module 06.

---

### Task 1: Restore and reframe the curriculum index and foundation

**Files:**
- Restore/Modify: `docs/learning/README.md`
- Restore/Modify: `docs/learning/01-foundation-api.md`

- [ ] Restore the three files from `HEAD`.
- [ ] Reframe the learning index around current repository, target architecture and post-MVP labels.
- [ ] Update module 01 with a module status table and links to `docs/INDEX.md`, Network Policy and Document Classification.
- [ ] Mark FastAPI as current transitional runtime and link to data/job/storage as the next module.
- [ ] Verify learning links and transitions for module 01.

### Task 2: Restore and align the data/job/storage module

**Files:**
- Restore/Modify: `docs/learning/02-data-jobs-and-storage.md`

- [ ] Restore the file from `HEAD`.
- [ ] Add current status for PostgreSQL, SQLAlchemy, Alembic, Redis, Celery and MinIO; defer pgvector.
- [ ] Add concise `FeatureJob`/outbox/lease/retry/DLQ boundary and link to Job/Queue Orchestration contracts.
- [ ] Verify it does not present job execution as an API-local background task only.

### Task 3: Replace the AI-first advanced module with workflow orchestration

**Files:**
- Restore/Modify: `docs/learning/03-workflow-orchestration-and-ai.md`

- [ ] Restore the file from `HEAD`.
- [ ] Replace its primary curriculum with Workflow Request/Run/Step, Feature Workflow Coordinator, Job Intent/FeatureJob, explicit `search_and_extract`, bounded fan-out and cancellation.
- [ ] Add diagrams and exercise/checklist that distinguish workflow planning, job lifecycle and delivery.
- [ ] Retain LLM/MCP as a brief post-MVP learning appendix with absent-dependency labels.
- [ ] Verify all terminology matches `docs/platform/workflow-orchestration.md` and `docs/platform/job-orchestration.md`.

### Task 4: Restore and version-gate media and quality learning

**Files:**
- Restore/Modify: `docs/learning/04-media-workflows.md`
- Restore/Modify: `docs/learning/05-observability-and-quality.md`

- [ ] Restore both files from `HEAD`.
- [ ] Gate static image workflow to v1.1 and approved browser/video workflow to v1.2; label absent media dependencies.
- [ ] Keep policy/DRM and controlled-fixture exercises; prohibit arbitrary browser inputs and bypass techniques.
- [ ] Mark structlog/pytest/respx/Ruff current; mark OpenTelemetry/Prometheus deferred until dependencies/wiring exist.
- [ ] Transition from module 05 to the Search & Crawl capstone rather than a deleted implementation plan.

### Task 5: Make Search & Crawl the final capstone

**Files:**
- Restore/Modify: `docs/learning/06-search-and-crawling.md`

- [ ] Move Search & Crawl after workflow, media and quality foundations.
- [ ] Mark SearXNG, HTTPX, selectolax and markdownify as current; mark Crawl4AI/Playwright as deferred, approved browser work.
- [ ] Teach standalone Search as non-crawling and `search_and_extract` as explicit, bounded workflow fan-out.
- [ ] Transition from the capstone to active contracts in `docs/INDEX.md`.

### Task 6: Integrate and verify the restored curriculum

**Files:**
- Modify: `docs/INDEX.md`
- Review: `README.md`, `STARTUP.md`, `docs/learning/*.md`

- [ ] Add the learning landing page to the documentation index and label it as a curriculum, not an implementation contract.
- [ ] Add a superseded note to the previous learning-removal spec/plan so it does not conflict with the restored curriculum.
- [ ] Run a local Markdown-link, heading and code-fence checker for root docs and `docs/`.
- [ ] Run `git diff --check -- README.md STARTUP.md docs` and inspect changed paths for docs-only scope.

## Self-review

- **Spec coverage:** Tasks 1–5 restore every module and apply the status/roadmap rules; Task 6 restores navigation and validates the corpus.
- **Type consistency:** Modules use `WorkflowRequest`, `WorkflowRun`, `WorkflowStep`, `JobIntent`, `FeatureJob`, `JobOrchestrationService` and `QueueManagementService` exactly as the active platform contracts do.
- **Review focus:** Task 1 prevents architecture confusion, Tasks 2–3 cover job/workflow ownership, Task 4 covers deferred technology safety, Task 5 covers explicit Search fan-out, and Task 6 covers navigation.
- **Proportion:** The plan preserves detailed learning material rather than duplicating active architecture contracts.
