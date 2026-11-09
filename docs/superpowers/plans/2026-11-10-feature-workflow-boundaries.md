# Feature Workflow Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the four Mini Crawler feature workflows — Search Discovery, Crawl Data, Image Download, Video Download — plus deferred Torrent Download, so direct-URL and page-driven discovery are distinct and every document labels current runtime, target architecture and deferred capability.

**Architecture:** Documentation-only alignment around one canonical media-candidate contract. Crawl Data owns documents and static image candidates; Video Download owns video candidates through an approved-source recipe; Workflow Orchestration alone fans out from a durable candidate manifest. Torrent stays a separate, deferred fifth capability.

**Tech Stack:** Markdown, Mermaid, Python 3 stdlib check scripts (no new dependency).

**Spec:** `docs/superpowers/specs/2026-11-10-feature-workflow-boundaries-design.md`

## Global Constraints

- Change Markdown only. Do not touch `app/**`, `tests/**`, `pyproject.toml`, `docker-compose*`, `.env*` or migrations.
- Keep the current layout: `app/services/`, `app/adapters/`, `app/workers/`, transitional `app/api/`. Do not create `app/features/` now.
- Every feature doc must separate **Current repository**, **Target architecture** and **After MVP**.
- Search is discovery-only. Search never crawls, discovers media or creates another feature job.
- Crawl Data owns `Document`, `document_type` and `ImageCandidateManifest`. Image Download never parses page HTML.
- Video Download owns `VideoCandidateManifest`, approved-source registry, recipe version and DRM/entitlement decision. Crawl Data never selects video candidates.
- Page workflows are two-stage: Crawl Data persists `Document` first, then the owning media feature persists its candidate manifest; the workflow result carries both `document_reference` and manifest reference.
- Candidate manifests are durable evidence. Result events/UI expose candidate IDs, outcome/reason codes and asset references; never raw candidate URLs, cookies, authorization headers, signed URLs or browser capture.
- `.mp4`, `.m3u8` and `.torrent`/magnet have distinct rules. Torrent Download is a separate deferred capability, never part of Video Download.
- Mini Nextcloud must not be described as replacing current crawler MinIO/S3-compatible storage.
- Do not commit, stage or push. The working tree holds unrelated user work.

## Review Focus

- **Current vs target confusion:** a reader must not mistake `VideoDiscoveryService` (normalizes supplied `raw_items`, no network) for a working Video Download pipeline, or `MediaJob` (image-only) for a generic media feature.
- **Classification triggers download:** a reader must not conclude `media_page`/`document_type` automatically creates download jobs.
- **Page workflow skipping persistence:** a reader must not think `extract_images`/`extract_video` returns media without first persisting the page `Document`.
- **Media format equivalence:** a reader must not treat `.m3u8`, `.mp4` and magnet links as the same download path.
- **Redaction leak:** a reader must not persist candidate URLs, cookies or capture in results, logs or queue payloads.

---

### Task 1: Add the canonical media-candidate workflow contract

**Files:**
- Create: `docs/platform/media-candidate-workflows.md`
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_1.py`

**Interfaces:**
- Consumes: the design's feature definitions, ownership, durable-reference and version-roadmap sections.
- Produces: the single canonical reference that Tasks 2–5 link to and cannot contradict. Section headings: `## Workflow types`, `## Ownership`, `## Two-stage page workflow`, `## Candidate manifest`, `## Image workflow`, `## Video workflow`, `## Torrent boundary`, `## Budgets and terminal outcomes`, `## Version roadmap`.

- [ ] **Step 1: Write the failing check**

Create the script with these exact assertions against `docs/platform/media-candidate-workflows.md` (normalize whitespace and casefold before matching):

```python
required = (
    "## workflow types",
    "direct url workflow",
    "page-driven workflow",
    "crawl data owns `imagecandidatemanifest`",
    "video download owns `videocandidatemanifest`",
    "image download never parses page html",
    "crawl data never selects video candidates",
    "two-stage",
    "`document_reference`",
    "durable evidence",
    "result events expose candidate ids",
    "never raw candidate urls, cookies, authorization headers, signed urls or browser capture",
    "download_image",
    "extract_images",
    "download_video",
    "extract_video",
    ".mp4",
    ".m3u8",
    ".torrent",
    "torrent download is a separate deferred capability",
    "only workflow orchestration may fan out",
)
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_1.py`
Expected: FAIL with `Missing canonical contract statements: [...]` (file absent or incomplete).

- [ ] **Step 3: Write `docs/platform/media-candidate-workflows.md`**

Content must include:

- A status note: this is a **target workflow contract**; the current repository still uses the simple layout.
- **Workflow types** table with four rows: `download_image` (direct image), `extract_images` (page), `download_video` (direct/approved source), `extract_video` (approved page/source).
- **Ownership** table: Crawl Data owns `Document`, `document_type`, static parsing and `ImageCandidateManifest`; Image Download owns download execution, per-item validation and `ImageManifest`; Video Download owns `VideoCandidateManifest`, approved source, recipe and DRM decision; Workflow Orchestration owns step graph, selection rule and budget.
- **Two-stage page workflow** diagram: `extract_images(page)` → `Document` + `ImageCandidateManifest` → selection/budget → `ImageDownloadJob` → `ImageManifest`; `extract_video(page/source)` → `Document` reference + `VideoCandidateManifest` → selection/budget → `VideoDownloadJob` → `VideoAsset`/manifest.
- **Candidate manifest** rules: durable record, source page reference, candidate ID, ordered safe metadata, candidate URL only where needed to execute; result events and logs expose IDs/outcomes/asset refs only; user-info URLs rejected; expiring signed URLs re-resolved, never persisted.
- **Image workflow:** every item policy-checked before network, streamed under per-item/total-byte limit, declared MIME + magic-byte validation, checksum/size/MIME/object metadata.
- **Video workflow:** approved source rechecked before download; `.mp4` bounded stream; `.m3u8` parsed only for approved source with policy-checked bounded segments; encrypted/DRM/unsupported playlist terminal; no login/CAPTCHA/paywall/geo bypass.
- **Torrent boundary:** `.torrent`/magnet may be recorded as a safe candidate reference; Video Download never downloads it; `torrent_download` is a separate deferred capability with its own product/legal, quota and audit design.
- **Budgets and terminal outcomes:** candidate count, requests, bytes, time, concurrency; HLS segment/playlist limits; blocked policy/MIME/quota/DRM/entitlement/unsupported playlist are terminal; only typed transient network/storage failures retry.
- **Version roadmap** table matching the design: v1 `search`/`crawl_url`/`search_and_extract`; v1.1 `download_image`/`extract_images`; v1.2 `download_video`/`extract_video`; later `torrent_download` only after separate decision.
- A `## Related docs` list linking `../features/search.md`, `../features/web-crawl.md`, `../features/image-download.md`, `../features/video-download.md`, `workflow-orchestration.md`, `../document-classification.md`, `network-policy.md`, `storage.md`.

- [ ] **Step 4: Run the check to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_1.py`
Expected: PASS with `Canonical media-candidate contract present.`

- [ ] **Step 5: Check whitespace for the new file**

Run: `git diff --check -- docs/platform/media-candidate-workflows.md`
Expected: no output (untracked files are checked by the Task 6 script).

---

### Task 2: Align Search and Crawl Data feature docs

**Files:**
- Modify: `docs/features/search.md`
- Modify: `docs/features/web-crawl.md`
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_2.py`

**Interfaces:**
- Consumes: Task 1's canonical contract.
- Produces: feature docs whose status blocks and outputs later tasks can cite consistently.

- [ ] **Step 1: Write the failing check**

Assert normalized, casefolded text in each file:

```python
search_required = (
    "## current repository",
    "`searchservice` calls searxng",
    "## target architecture",
    "search never crawls",
    "## after mvp",
    "mini search is a future standalone target",
    "media-candidate-workflows.md",
)
crawl_required = (
    "## current repository",
    "policy gate",
    "static fetch",
    "normalize",
    "classify",
    "persist",
    "## target architecture",
    "`document_type`",
    "`imagecandidatemanifest`",
    "classification never creates download jobs",
    "media_page",
    "## after mvp",
    "crawl_collection",
    "media-candidate-workflows.md",
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_2.py`
Expected: FAIL listing missing statements.

- [ ] **Step 3: Update `docs/features/search.md`**

Keep the existing contract; add `## Current repository` stating `SearchService` calls SearXNG, normalizes/deduplicates, and the transitional API may explicitly call crawl for a selected result. Add `## Target architecture` stating Search never crawls, discovers media or creates another feature job; `search_and_extract` selection belongs to Workflow Orchestration. Add `## After MVP` stating Mini Search is a future standalone target, not a current module, with rollback to SearXNG. Add a Related contract link to `media-candidate-workflows.md`. Do not change the existing queue/contract/execution sections beyond wording needed for consistency.

- [ ] **Step 4: Update `docs/features/web-crawl.md`**

Add `## Current repository` describing the shipped path: Policy Gate → job → static fetch → normalize → classify → persist. Add to `## Workflow role and data` that `crawl_url`/`search_and_extract` return a `Document`, and the explicit `extract_images` workflow may additionally retain an `ImageCandidateManifest`. Add `## Target architecture` stating one `document_type`, confidence/reason/needs_review, no auto-follow and no auto-download; `media_page` is a classification label only. Keep `## After MVP` (`crawl_collection`, browser recipe, depth 2–3). Add a Related contract link to `media-candidate-workflows.md`.

- [ ] **Step 5: Run to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_2.py`
Expected: PASS with `Search and Crawl Data docs aligned.`

---

### Task 3: Align Image and Video feature docs

**Files:**
- Modify: `docs/features/image-download.md`
- Modify: `docs/features/video-download.md`
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_3.py`

**Interfaces:**
- Consumes: Task 1's ownership and durable-reference rules.
- Produces: direct-vs-page workflow descriptions that Task 4's orchestration table references.

- [ ] **Step 1: Write the failing check**

```python
image_required = (
    "## current repository",
    "direct and batch image urls",
    "`mediajob`",
    "## target architecture",
    "`download_image`",
    "`extract_images`",
    "crawl data owns `imagecandidatemanifest`",
    "image download never parses page html",
    "per-item",
    "magic bytes",
    "## after mvp",
    "browser lazy-load",
    "media-candidate-workflows.md",
)
video_required = (
    "## current repository",
    "`videodiscoveryservice`",
    "does not fetch or download video",
    "## target architecture",
    "`download_video`",
    "`extract_video`",
    "video download owns `videocandidatemanifest`",
    ".mp4",
    ".m3u8",
    "encrypted",
    "## after mvp",
    "torrent download is a separate deferred capability",
    "media-candidate-workflows.md",
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_3.py`
Expected: FAIL listing missing statements.

- [ ] **Step 3: Update `docs/features/image-download.md`**

Add `## Current repository`: `MediaJob` accepts direct and batch image URLs, applies policy/quota, downloads with injected downloader, validates declared MIME + magic bytes, persists assets; the name is generic but the capability is image-only. Add `## Target architecture`: direct `download_image` vs page `extract_images`; Crawl Data owns `ImageCandidateManifest` and static parsing; Image Download never parses page HTML; per-item outcomes and `ImageManifest`. Add `## After MVP`: browser lazy-load and automatic page expansion excluded. Keep package structure clearly labelled as target. Add Related contract link.

- [ ] **Step 4: Update `docs/features/video-download.md`**

Add `## Current repository`: `VideoDiscoveryService` only checks approved source and normalizes supplied `raw_items`; it does not fetch or download video; `torrent_worker.py` is separate. Add `## Target architecture`: direct `download_video` vs page `extract_video`; Video Download owns `VideoCandidateManifest`, approved source, recipe version and DRM/entitlement; `.mp4` bounded stream; `.m3u8` playlist parsed only for approved source with policy-checked bounded segments; encrypted/DRM/unsupported playlist terminal. Add `## After MVP` stating torrent download is a separate deferred capability, never part of this feature. Add Related contract link.

- [ ] **Step 5: Run to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_3.py`
Expected: PASS with `Image and Video docs aligned.`

---

### Task 4: Align workflow orchestration, classification, and navigation

**Files:**
- Modify: `docs/platform/workflow-orchestration.md`
- Modify: `docs/document-classification.md`
- Modify: `docs/INDEX.md`
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_4.py`

**Interfaces:**
- Consumes: Tasks 1–3's workflow names and ownership.
- Produces: navigation and platform rules that must not contradict the feature docs.

- [ ] **Step 1: Write the failing check**

```python
workflow_required = (
    "`download_image`",
    "`extract_images`",
    "`download_video`",
    "`extract_video`",
    "`torrent_download`",
    "two-stage",
    "`document_reference`",
    "only workflow orchestration may fan out",
    "media-candidate-workflows.md",
)
classification_required = (
    "classification does not trigger downloads",
    "`media_page`",
    "`never`",
    "media-candidate-workflows.md",
)
index_required = (
    "platform/media-candidate-workflows.md",
    "features/search.md",
    "features/web-crawl.md",
    "features/image-download.md",
    "features/video-download.md",
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_4.py`
Expected: FAIL listing missing statements.

- [ ] **Step 3: Update `docs/platform/workflow-orchestration.md`**

Add the four media workflow rows to `## MVP workflow definitions` or a new `## Media workflow definitions` table: `download_image`, `extract_images`, `download_video`, `extract_video`, each with steps/output/boundary. State page workflows are two-stage, the aggregate result carries `document_reference` plus manifest reference, and only Workflow Orchestration may fan out from a durable candidate manifest. Add `torrent_download` to the version roadmap as deferred. Link `media-candidate-workflows.md`.

- [ ] **Step 4: Update `docs/document-classification.md`**

Add an explicit rule after `## 5. Ranh giới và quality gate`: classification does not trigger downloads; `media_page` is only a label; candidate discovery requires an explicit media workflow and is owned per `media-candidate-workflows.md`. Keep the existing taxonomy unchanged.

- [ ] **Step 5: Update `docs/INDEX.md`**

Add `- [Media candidate workflows](platform/media-candidate-workflows.md) — direct vs page workflows, manifest ownership, budgets, durable references and terminal outcomes.` under `## Shared platform`. Update the Image and Video feature descriptions so they mention direct plus page-driven discovery. Keep the existing navigation intact.

- [ ] **Step 6: Run to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_4.py`
Expected: PASS with `Orchestration, classification and index aligned.`

---

### Task 5: Align the architecture roadmap, sample roadmap and learning modules

**Files:**
- Modify: `docs/architecture/worker-crawler-rearchitecture.md`
- Modify: `docs/sample/mini-services-replacement-roadmap.md`
- Modify: `docs/learning/04-media-workflows.md`
- Modify: `docs/learning/06-search-and-crawling.md`
- Modify: `docs/learning/README.md`
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_5.py`

**Interfaces:**
- Consumes: Tasks 1–4's canonical names and boundaries.
- Produces: reference/learning material that repeats the same truth without inventing new behavior.

- [ ] **Step 1: Write the failing check**

```python
architecture_required = (
    "direct url",
    "page-driven",
    "imagecandidatemanifest",
    "videocandidatemanifest",
    "torrent",
)
sample_required = (
    "video discovery",
    "does not fetch or download video",
    "deferred",
)
learning_04_required = (
    "direct url",
    "page url",
    "extract_images",
    "extract_video",
    "m3u8",
    "torrent",
    "media-candidate-workflows.md",
)
learning_06_required = (
    "classification does not trigger downloads",
    "media-candidate-workflows.md",
)
learning_index_required = (
    "04-media-workflows.md",
    "direct",
    "page",
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_5.py`
Expected: FAIL listing missing statements.

- [ ] **Step 3: Update the architecture roadmap**

In the feature-boundary and queue sections, state that Image and Video each support direct-URL and page-driven workflows, that Crawl Data owns `ImageCandidateManifest` and Video Download owns `VideoCandidateManifest`, that page workflows persist a `Document` first, and that torrent is separate and deferred. Do not change the roadmap's "future" labelling or the current-runtime description.

- [ ] **Step 4: Update the sample replacement roadmap**

Change the Video row from "video discovery/download" to "video discovery only", state it does not fetch or download video, and keep module extraction deferred. Do not claim a working Video Download feature.

- [ ] **Step 5: Update the learning modules and learning index**

In `04-media-workflows.md`, add a short "direct URL vs page URL" section near the top: direct `download_image`/`download_video` versus page `extract_images`/`extract_video`; page workflows go through Crawl Data and a durable candidate manifest; `.m3u8` is not `.mp4`; torrent is separate. In `06-search-and-crawling.md`, add that classification does not trigger downloads and link the canonical contract. In `README.md`, make the 04 module description mention direct and page-driven media workflows.

- [ ] **Step 6: Run to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_5.py`
Expected: PASS with `Roadmap and learning docs aligned.`

---

### Task 6: Validate documentation-only scope

**Files:**
- Review: every file changed in Tasks 1–5
- Test: `.superpowers/sdd/feature-workflow-boundaries/check_task_6.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: evidence that links, headings, fences, whitespace and scope are correct.

- [ ] **Step 1: Write the failing check**

The script must:

1. Parse `README.md`, `STARTUP.md` and `docs/**/*.md`; verify every relative Markdown link target exists (ignore anchors, `http(s)`, `mailto`).
2. Verify heading levels never jump by more than one and every code fence is closed.
3. Verify no trailing whitespace in the files created/modified by this plan:
   `docs/platform/media-candidate-workflows.md`, `docs/features/search.md`, `docs/features/web-crawl.md`, `docs/features/image-download.md`, `docs/features/video-download.md`, `docs/platform/workflow-orchestration.md`, `docs/document-classification.md`, `docs/INDEX.md`, `docs/architecture/worker-crawler-rearchitecture.md`, `docs/sample/mini-services-replacement-roadmap.md`, `docs/learning/04-media-workflows.md`, `docs/learning/06-search-and-crawling.md`, `docs/learning/README.md`.
4. Run `git status --short` and fail if any changed path is outside `README.md`, `STARTUP.md`, `docs/` and `.superpowers/`.
5. Assert the current-layout sentence exists in `docs/INDEX.md` or `docs/architecture/worker-crawler-rearchitecture.md`, and that no doc contains `app/features/` as a *current* directory claim (occurrences inside a "future/target migration" sentence are allowed).

- [ ] **Step 2: Run to verify it fails**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_6.py`
Expected: FAIL on at least one missing link, whitespace issue, scope violation or current-layout assertion.

- [ ] **Step 3: Fix only the plan-scoped documentation issues**

Correct broken links, heading jumps, unclosed fences, trailing whitespace or contradictory current-layout claims introduced by Tasks 1–5. Do not fix unrelated pre-existing whitespace in other documents.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 .superpowers/sdd/feature-workflow-boundaries/check_task_6.py`
Expected: PASS with `Documentation links, headings, fences, whitespace and scope valid.`

- [ ] **Step 5: Confirm the pre-existing debt stays out of scope**

Run: `git diff --check -- README.md STARTUP.md docs`
Expected: only the known pre-existing trailing-whitespace lines in `docs/architecture/worker-crawler-rearchitecture.md:3`, `docs/sample/mini_crawler_implementation_plan.md:3-4` and `docs/sample/yt-dlp-REPO_DESCRIPTION_VI.md:11-13` may remain; report them, do not edit them.

---

## Self-review

- **Spec coverage:** Task 1 covers feature definitions, ownership, two-stage workflow, durable references, budgets, version roadmap and torrent boundary. Tasks 2–3 cover all four feature docs. Task 4 covers orchestration/classification/index. Task 5 covers roadmap/learning. Task 6 covers acceptance-criteria verification.
- **Step scan:** Each step names one file and one checkable result. No step says "update as needed" without naming the required statement.
- **Type consistency:** Workflow names (`download_image`, `extract_images`, `download_video`, `extract_video`, `torrent_download`) and object names (`Document`, `ImageCandidateManifest`, `ImageManifest`, `VideoCandidateManifest`, `VideoAsset`) match the design.
- **Review Focus:** Five failure modes each appear in Task 2–5 checks (status blocks, classification-no-download, two-stage persistence, format distinctions, redaction) or Task 6 scope/current-layout assertion.
- **Proportion:** Six tasks, all documentation; no task recreates feature implementation detail already in the design.
