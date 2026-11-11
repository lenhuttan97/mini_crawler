# Article Content Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a clean article body and verified article metadata while excluding page chrome and preserving the Web Crawl/image-workflow boundary.

**Architecture:** Extend the existing `selectolax` normalizer with structured-metadata extraction and deterministic content-root selection, then pass its typed output through classification and document storage. Add only nullable document columns through an additive Alembic revision; object uploads are tracked on the current database session so failed persistence or transaction rollback can delete new objects.

**Tech Stack:** Python 3.12, selectolax, markdownify, SQLAlchemy 2, Alembic, pytest, SQLite test database.

**Spec:** `docs/superpowers/specs/2026-11-11-article-content-extraction-design.md`

## Global Constraints

- Use the installed `selectolax` and standard library only; do not add Readability, Trafilatura, or another dependency.
- Web Crawl remains static and bounded: no browser fallback, recursive links, request-provided selectors/JavaScript/cookies, or downstream jobs.
- Only the explicit `extract_images` workflow may create an `ImageCandidateManifest`; `crawl_url` must not expose raw image/candidate URLs.
- Missing, malformed, or conflicting author/date/section data stays unset; never infer it.
- Never log or return raw query strings, cookies, tokens, signed URLs, raw page captures, storage keys, or candidate URLs.
- The schema migration is additive and nullable, with no backfill and no expected downtime. Downgrade removes only the new columns, which irreversibly discards metadata written while the revision was active.
- Keep legacy HTTP document-list output unchanged; it is not the target worker result contract.

## Review Focus

1. **Pages with several `<article>` cards:** select the substantial article body rather than a teaser/card; covered by Task 1’s multi-article fixture.
2. **Malformed or graph-shaped JSON-LD:** ignore invalid/unusable data without failing a crawl or fabricating metadata; covered by Task 1’s malformed/multiple-script fixtures.
3. **Short or navigation-like pages:** do not classify them as news from the URL alone; mark the fallback output `needs_review`; covered by Task 4’s insufficient-content classification test.
4. **Real article semantics:** removing boilerplate must retain figures, captions, tables, code, blockquotes and article links; covered by Task 1’s preservation fixture.
5. **Storage/flush/commit failure:** delete every object uploaded in the failed transaction, while leaving a successful/deduplicated document untouched; covered by Tasks 3 and 4.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `app/features/web_crawl/application/normalizer.py` | Select one content root, remove boilerplate, extract validated article metadata and structured data. |
| `app/features/web_crawl/application/classifier.py` | Preserve existing taxonomy while rejecting insufficient extraction quality as a news/article signal. |
| `app/features/web_crawl/application/service.py` | Explicitly map normalized fields to classifier and persistence boundaries. |
| `app/features/web_crawl/application/execution.py` | Confirm or compensate pending object uploads around the owning session transaction. |
| `app/platform/persistence/models.py` | ORM mapping for new nullable document metadata and article HTML key. |
| `app/platform/document_storage/service.py` | Persist article metadata/HTML, dedupe, and session-scoped object cleanup helpers. |
| `alembic/versions/0003_document_article_metadata.py` | Add/drop the document columns without backfill. |
| `tests/unit/features/web_crawl/*.py` | Extraction, classification, service mapping, and rollback behavior. |
| `tests/unit/platform/document_storage/*.py` | Schema and storage persistence/compensation behavior. |
| `docs/features/web-crawl.md`, `docs/document-classification.md` | Active contract documentation for article extraction and metadata. |

### Task 1: Normalize one article root and structured metadata

**Files:**
- Modify: `app/features/web_crawl/application/normalizer.py:17-94`
- Modify: `tests/unit/features/web_crawl/test_normalizer.py:12-84`

**Interfaces:**
- Produces `NormalizedDocument` with `title`, `summary`, `authors: tuple[str, ...]`, `published_at`, `updated_at`, `section`, `language`, `canonical_url`, `json_ld`, `content_is_sufficient`, `content_hash`, `markdown`, and `clean_html`.
- Retains `normalize_html(html: str, base_url: str) -> NormalizedDocument` as the only normalizer entrypoint.
- Removes the unused `links` field; repository search showed no production caller consumes it.

- [ ] **Step 1: Write failing normalizer tests with controlled HTML fixtures**

  Add tests that assert:
  - a JSON-LD `NewsArticle` wins over OpenGraph, `h1`, and `<title>` for title; extracts two named authors, ISO-aware published/updated datetimes, summary, `articleSection`, language, and canonical URL;
  - two distinct usable JSON-LD Article values for the same factual field leave that field unset, while a lower-priority OpenGraph value does not override a valid selected JSON-LD value;
  - the largest valid `<article>` is selected when the page also has header, aside, teaser `<article>`, related, social, newsletter, comment, tag and pagination blocks;
  - selected output retains `figure`/`figcaption`, table, code, blockquote and an in-article link, but excludes every boilerplate block and its links;
  - malformed JSON-LD is ignored, and an article with fewer than 200 non-whitespace characters or fewer than two paragraph/text blocks sets `content_is_sufficient is False` rather than failing;
  - a body-text change changes `content_hash`, while a change restricted to removed boilerplate does not.

- [ ] **Step 2: Run the normalizer tests to verify they fail**

  Run: `uv run pytest tests/unit/features/web_crawl/test_normalizer.py -v`

  Expected: FAIL because `NormalizedDocument` lacks the metadata/quality fields and whole-page normalization retains the fixture boilerplate.

- [ ] **Step 3: Implement typed extraction in `normalizer.py`**

  Keep the public function signature. Parse JSON-LD scripts safely with `json.loads`; collect usable Article-family items from an object, `@graph`, or list and expose the selected item as `json_ld` for classification. Resolve metadata using the precedence in the spec; when values at the selected source priority disagree, leave that factual field unset. Parse only valid ISO datetimes (normalizing a trailing `Z` to UTC); normalise authors to a de-duplicated tuple of non-empty strings.

  Select candidates in this order: all `<article>` candidates, then `<main>`, then `[role="main"]`, then `<body>`; choose the candidate with the highest text length within the first non-empty group. Mark it sufficient only at 200 non-whitespace characters and two text blocks. Prune structural tags and exact class/id/aria-label tokens from the selected root, then derive both HTML and Markdown from that root. Keep `content_hash = sha256(markdown.encode("utf-8"))`.

- [ ] **Step 4: Run the normalizer tests to verify they pass**

  Run: `uv run pytest tests/unit/features/web_crawl/test_normalizer.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit the extraction change**

  ```bash
  git add app/features/web_crawl/application/normalizer.py tests/unit/features/web_crawl/test_normalizer.py
  git commit -m "feat: extract clean article content and metadata"
  ```

### Task 2: Add the additive document metadata migration

**Files:**
- Create: `alembic/versions/0003_document_article_metadata.py`
- Modify: `app/platform/persistence/models.py:9-21,82-99`
- Modify: `tests/unit/platform/document_storage/test_migrations.py:73-90`

**Interfaces:**
- Produces nullable ORM fields on `Document`: `summary`, `authors`, `published_at`, `updated_at`, `section`, `language`, and `article_html_key`.
- The Alembic revision has `down_revision = "0002_worker_v1_jobs"`; `upgrade()` adds exactly those columns and `downgrade()` drops exactly those columns.

- [ ] **Step 1: Write failing migration/ORM parity tests**

  Add a test that upgrades a fresh SQLite database to `head` and asserts the `documents` table contains all seven new columns. Downgrade only to `0002_worker_v1_jobs` and assert the columns are absent while `documents` remains. Extend the existing ORM/migration parity assertion to include the new `Document` fields.

- [ ] **Step 2: Run the migration tests to verify they fail**

  Run: `uv run pytest tests/unit/platform/document_storage/test_migrations.py -v`

  Expected: FAIL because revision `0003` and matching ORM fields do not exist.

- [ ] **Step 3: Add the model and handwritten migration**

  Map `summary` as nullable `Text`, `authors` as nullable `JSON`, `published_at`/`updated_at` as nullable timezone-aware `DateTime`, `section` as nullable `String(256)`, `language` as nullable `String(35)`, and `article_html_key` as nullable `String(512)`. Use `op.add_column`/`op.drop_column` only; do not backfill or rewrite existing objects.

- [ ] **Step 4: Run the migration tests to verify they pass**

  Run: `uv run pytest tests/unit/platform/document_storage/test_migrations.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit the schema change**

  ```bash
  git add app/platform/persistence/models.py alembic/versions/0003_document_article_metadata.py tests/unit/platform/document_storage/test_migrations.py
  git commit -m "feat: store article document metadata"
  ```

### Task 3: Persist article HTML and compensate failed storage writes

**Files:**
- Modify: `app/platform/document_storage/service.py:17-104`
- Modify: `tests/unit/platform/document_storage/test_persistence.py:31-102`

**Interfaces:**
- Extends `PersistenceService.save_document(...) -> PersistenceResult` with `summary: str | None`, `authors: tuple[str, ...]`, `published_at: datetime | None`, `updated_at: datetime | None`, `section: str | None`, and `language: str | None`; its existing `clean_html` argument is the selected article HTML.
- Produces `confirm_pending_document_uploads(session) -> None` and `rollback_pending_document_uploads(session) -> None` for the transaction owner.
- Stores pending `(storage, bucket, key)` records in `session.info`; cleanup is idempotent and does not mask the original upload/database exception.

- [ ] **Step 1: Write failing persistence tests**

  Extend the create test to assert every metadata field and `article_html_key` are persisted, and that Markdown plus article HTML use server-generated keys. Add tests that:
  - a second upload failure deletes the already uploaded Markdown object;
  - a `session.flush()` failure deletes both uploaded objects and re-raises;
  - dedupe performs no new upload and creates no pending cleanup records;
  - `rollback_pending_document_uploads` deletes each registered object once, while `confirm_pending_document_uploads` clears the registry without deletion.

- [ ] **Step 2: Run the persistence tests to verify they fail**

  Run: `uv run pytest tests/unit/platform/document_storage/test_persistence.py -v`

  Expected: FAIL because metadata/article HTML keys and pending-upload compensation are absent.

- [ ] **Step 3: Implement explicit persistence mapping and compensation**

  Generate `documents/markdown/<uuid>` and `documents/html/<uuid>` keys; upload the Markdown and selected article HTML, register successful uploads on the session, then flush the `Document` with all new fields and `article_html_key`. On any exception in this method, call the rollback helper before re-raising. Keep content-hash dedupe before key generation/upload.

- [ ] **Step 4: Run the persistence tests to verify they pass**

  Run: `uv run pytest tests/unit/platform/document_storage/test_persistence.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit the persistence change**

  ```bash
  git add app/platform/document_storage/service.py tests/unit/platform/document_storage/test_persistence.py
  git commit -m "feat: persist article metadata and html references"
  ```

### Task 4: Wire extraction quality, classification, persistence, and transaction finalization

**Files:**
- Modify: `app/features/web_crawl/application/classifier.py:77-126`
- Modify: `app/features/web_crawl/application/service.py:58-83`
- Modify: `app/features/web_crawl/application/execution.py:24-102`
- Modify: `tests/unit/features/web_crawl/test_classifier.py:13-98`
- Modify: `tests/unit/features/web_crawl/test_crawl_service.py:18-90`
- Modify: `tests/unit/features/web_crawl/test_crawl_worker.py:53-119`

**Interfaces:**
- Extends `DocumentClassifier.classify(..., content_is_sufficient: bool = True) -> ClassificationResult`.
- `CrawlService.crawl(...) -> dict` remains API-compatible but maps all `NormalizedDocument` metadata explicitly into `PersistenceService.save_document`.
- `process_crawl_job(...)` rolls back pending document uploads when crawl processing raises; `execute_crawl_job(...)` confirms them only after `session.commit()` and rolls them back after commit failure.

- [ ] **Step 1: Write failing classifier/service/worker tests**

  Add assertions that:
  - `content_is_sufficient=False` yields `generic_page` when cleaned text exists, otherwise `unknown`; both are low-confidence and `needs_review=True`, regardless of a `/news/` URL;
  - `CrawlService` passes `normalized.json_ld` and `content_is_sufficient` to the classifier, and maps every metadata field to persistence;
  - a worker crawl exception invokes `rollback_pending_document_uploads(session)` before setting the job to failed;
  - a successful `execute_crawl_job` commits then invokes `confirm_pending_document_uploads(session)`; a commit exception rolls back and invokes `rollback_pending_document_uploads(session)`.

- [ ] **Step 2: Run the focused orchestration tests to verify they fail**

  Run: `uv run pytest tests/unit/features/web_crawl/test_classifier.py tests/unit/features/web_crawl/test_crawl_service.py tests/unit/features/web_crawl/test_crawl_worker.py -v`

  Expected: FAIL because the quality flag, structured-data mapping, and transaction finalization calls are absent.

- [ ] **Step 3: Implement boundary mapping and lifecycle handling**

  Make the classifier return the safe low-confidence fallback before structured metadata/DOM/URL rules when `content_is_sufficient` is false. In `CrawlService`, pass the selected JSON-LD and quality flag, then map each normalized metadata field by name to persistence. In the execution boundary, call the Task 3 helpers around the session-owned commit/rollback path; preserve current job terminal-state behavior and do not expose object keys in the returned dict.

- [ ] **Step 4: Run the focused orchestration tests to verify they pass**

  Run: `uv run pytest tests/unit/features/web_crawl/test_classifier.py tests/unit/features/web_crawl/test_crawl_service.py tests/unit/features/web_crawl/test_crawl_worker.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit the integration change**

  ```bash
  git add app/features/web_crawl/application/classifier.py app/features/web_crawl/application/service.py app/features/web_crawl/application/execution.py tests/unit/features/web_crawl/test_classifier.py tests/unit/features/web_crawl/test_crawl_service.py tests/unit/features/web_crawl/test_crawl_worker.py
  git commit -m "feat: classify and persist extracted article data"
  ```

### Task 5: Synchronize active contracts and run the final focused quality gate

**Files:**
- Modify: `docs/features/web-crawl.md:5-9,70-80`
- Modify: `docs/document-classification.md:36-63`

**Interfaces:**
- Documents the persisted article metadata, selected article-body quality gate, and `extract_images`-only image candidate boundary implemented by Tasks 1–4.

- [ ] **Step 1: Update active Web Crawl and classification documentation**

  State that Web Crawl persists selected article HTML/Markdown and nullable factual metadata; list the source-precedence/fallback rule; state that missing fields are not inferred. Preserve the existing `extract_images` ownership and raw-URL redaction boundary. Do not document the legacy API as the target result contract.

- [ ] **Step 2: Run the complete affected test set**

  Run: `uv run pytest tests/unit/features/web_crawl/test_normalizer.py tests/unit/features/web_crawl/test_classifier.py tests/unit/features/web_crawl/test_crawl_service.py tests/unit/features/web_crawl/test_crawl_worker.py tests/unit/platform/document_storage/test_persistence.py tests/unit/platform/document_storage/test_migrations.py -v`

  Expected: PASS.

- [ ] **Step 3: Run static verification**

  Run: `uv run ruff check . && uv run ruff format --check .`

  Expected: both commands exit 0.

- [ ] **Step 4: Review the migration and final diff**

  Run: `git diff --check && git diff -- app/features/web_crawl app/platform/document_storage app/platform/persistence/models.py alembic/versions/0003_document_article_metadata.py tests/unit/features/web_crawl tests/unit/platform/document_storage docs/features/web-crawl.md docs/document-classification.md`

  Expected: no whitespace errors; no changed queue/workflow contract, legacy response schema, raw image URL output, or unrelated files.

- [ ] **Step 5: Commit documentation and final verification changes**

  ```bash
  git add docs/features/web-crawl.md docs/document-classification.md
  git commit -m "docs: define clean article extraction contract"
  ```
