# Request-driven Workflow Orchestration Documentation Implementation Plan

> **Superseded for curriculum scope:** the learning-removal task is superseded by [`2026-11-09-learning-curriculum.md`](2026-11-09-learning-curriculum.md); retain this file as implementation history.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document request-driven, multi-job workflows while retaining one shared job lifecycle and one delivery lifecycle.

**Architecture:** A `WorkflowOrchestrator` owns `WorkflowRun` and registered step graphs; feature coordinators only translate permitted workflow steps to `JobIntent`; `JobOrchestrationService` owns every `FeatureJob`; and `QueueManagementService` owns delivery. MVP supports explicit search, crawl and bounded search-and-extract; later versions add images, approved browser video, depth 2–3 crawl and scheduled recrawl.

**Tech Stack:** Markdown and Mermaid only.

**Spec:** `docs/superpowers/specs/2026-11-09-job-orchestration-docs-design.md`

## Global Constraints

- Only add or modify Markdown under `docs/`; do not change code, configuration or dependencies.
- Run a workflow only from an explicit request in MVP.
- Queue messages contain delivery metadata only; workflow state and commands are durable records.
- Do not allow direct feature-to-feature calls, automatic unrequested fan-out, arbitrary browser actions or unbounded crawling.
- Preserve Network Policy revalidation, redaction, idempotency, lease, retry and DLQ safety boundaries.

## Review Focus

- A `search` request returns results only; it cannot create crawl jobs without the explicit `search_and_extract` workflow type.
- A duplicate workflow request must reuse one `WorkflowRun`/child-job set through the idempotency scope.
- A child job terminal policy/DRM/validation/cancel outcome must resolve the workflow step without retrying it.
- A depth-2/3 request must remain deferred until the versioned `crawl_collection` guardrails exist.
- A video workflow must never let request content supply browser selectors, JavaScript, cookies or credentials.

---

## File structure

| Path | Responsibility |
|---|---|
| `docs/platform/workflow-orchestration.md` | Workflow request, durable run/step model, registered definitions, flows and roadmap. |
| `docs/platform/job-orchestration.md` | Single `FeatureJob` lifecycle and workflow-to-job hand-off. |
| `docs/platform/queue-management.md` | Delivery mechanics only. |
| `docs/architecture/worker-crawler-rearchitecture.md` | Repository-wide component boundaries and action/data flow. |
| `docs/features/*.md` | Feature command/job/result objects and workflow roles. |
| `docs/INDEX.md` | Navigation to the active contracts. |

### Task 1: Add Workflow and Job Orchestration contracts

**Files:**
- Create: `docs/platform/workflow-orchestration.md`
- Create: `docs/platform/job-orchestration.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: explicit `WorkflowRequest`, registered `WorkflowDefinition`, typed feature command and redacted caller/policy context.
- Produces: `WorkflowRun`, `WorkflowStep`, `JobIntent`, `FeatureJob`, result references and feature queue route.

- [ ] Define object fields, ownership and state transitions for `WorkflowRun`/`WorkflowStep`; include idempotent duplicate request and cancellation behavior.
- [ ] Add the common Mermaid action/data flow from request through workflow, feature job, queue delivery, typed result and aggregate result.
- [ ] Define `search`, `crawl_url` and `search_and_extract`, including the rule that only the explicit third workflow may fan out bounded crawl jobs.
- [ ] Add the version roadmap and constraints for image, video/browser, bounded depth 2–3 and schedules.
- [ ] Define `JobOrchestrationService` as the only owner of `FeatureJob` state; distinguish it from workflow planning and Queue Management delivery.
- [ ] Link both new platform contracts from `docs/INDEX.md`.

### Task 2: Align platform and repository architecture boundaries

**Files:**
- Modify: `docs/platform/queue-management.md`
- Modify: `docs/architecture/worker-crawler-rearchitecture.md`

**Interfaces:**
- Consumes: Workflow/Job Orchestration contracts from Task 1.
- Produces: one canonical component diagram, hand-off model and queue vocabulary.

- [ ] Document outbox hand-offs: Job Orchestration submits a durable job; Queue Management delivers it; typed result updates the durable job and wakes the parent workflow.
- [ ] Add the three-level ownership model—Workflow Orchestrator, feature workflow coordinator and Job Orchestration—without granting any of them feature execution logic.
- [ ] Standardize the maintenance queue as `worker.maintenance.v1` and replace `CrawlJobService`/`UrlPolicyService` with `WebCrawlService`/`NetworkPolicyService`.
- [ ] Correct Queue Management subsection numbering and update diagrams to use canonical object names.
- [ ] Search active docs for retired names; expect no active-contract occurrence.

### Task 3: Make each feature's workflow role and data explicit

**Files:**
- Modify: `docs/features/search.md`
- Modify: `docs/features/web-crawl.md`
- Modify: `docs/features/image-download.md`
- Modify: `docs/features/video-download.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: `WorkflowStep → JobIntent → FeatureJob` lifecycle and Network Policy gate.
- Produces: feature-specific command/job/result/persistent-output descriptions.

- [ ] Document Search objects and distinguish `search` from workflow-level `search_and_extract`; Search service never submits crawl jobs itself.
- [ ] Document Web Crawl command, job, classification/document result and its workflow input/output; link `docs/document-classification.md`.
- [ ] Document Image discovery/download child jobs, per-item terminal outcomes and `ImageManifest` as v1.1 only.
- [ ] Document Video approved-source recipe, `VideoCandidate`, terminal DRM/entitlement outcomes and `VideoAsset` as v1.2 only.
- [ ] Add Document Type Classification to `docs/INDEX.md`.

### Task 4: Remove the superseded learning path and verify documentation

**Files:**
- Delete: `docs/learning/README.md`
- Delete: `docs/learning/01-foundation-api.md`
- Delete: `docs/learning/02-search-and-crawling.md`
- Delete: `docs/learning/03-data-jobs-and-storage.md`
- Delete: `docs/learning/04-llm-agent-and-mcp.md`
- Delete: `docs/learning/05-video-discovery-and-download.md`
- Delete: `docs/learning/06-observability-and-quality.md`
- Review: all changed paths in Tasks 1–3

**Interfaces:**
- Consumes: active-contract navigation and the historical-reference boundary in `docs/sample/`.
- Produces: an active documentation tree without the superseded API/RAG learning path.

- [ ] Remove `docs/learning/`; it documents the superseded API/RAG architecture and is not linked from the active documentation index.
- [ ] Confirm `docs/INDEX.md` keeps `docs/sample/` as the location for reference/historical material.
- [ ] Run the local Markdown-link checker; expect no missing local links.
- [ ] Run a heading/code-fence check across `docs/`; expect no hierarchy or fence errors.
- [ ] Run `git diff --check -- docs` and inspect the diff for documentation-only scope.

## Self-review

- **Spec coverage:** Task 1 covers objects, MVP workflows and version roadmap. Task 2 establishes ownership boundaries. Task 3 defines the four feature roles. Task 4 removes superseded learning material and verifies the corpus.
- **Step scan:** Every step is a focused documentation edit or deterministic validation.
- **Type consistency:** Canonical terms are `WorkflowOrchestrator`, `FeatureWorkflowCoordinator`, `JobOrchestrationService`, `QueueManagementService`, `WorkflowRun`, `WorkflowStep`, `JobIntent`, `FeatureJob` and `worker.maintenance.v1`.
- **Review focus:** Task 1 covers search/fan-out/idempotency; Tasks 1 and 3 make terminal outcomes and deferred depth/browser limits explicit.
- **Proportion:** This plan documents one architecture with four feature views; it does not prescribe source-code implementation.
