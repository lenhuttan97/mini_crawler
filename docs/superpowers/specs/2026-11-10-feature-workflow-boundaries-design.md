# Feature Workflow Boundaries Design

## Intent

Xác định rõ bốn feature dữ liệu/media của Mini Crawler theo workflow mà người
dùng nhìn thấy, thay vì nhầm chúng với thư mục code hoặc implementation provider:

1. Search Discovery;
2. Crawl Data;
3. Image Download;
4. Video Download.

Một URL trang có thể được crawl để tạo document và media candidate. Chỉ một
workflow được caller yêu cầu rõ ràng mới được chọn một tập candidate có giới
hạn để tạo image/video download job. Direct URL download vẫn được hỗ trợ. Torrent
Download là capability thứ năm, tách riêng và deferred.

## Current reality

Current source is intentionally simple, not physically feature-modular:

| Capability | Current behavior | Limit |
|---|---|---|
| Search | `SearchService` calls SearXNG and normalizes results; an API bridge may explicitly call crawl for a selected result. | Target workflow must remove this direct feature-to-feature coupling. |
| Crawl Data | Policy gate → static fetch → normalize → classify → persist a document. | No durable media-candidate workflow yet. |
| Image Download | `MediaJob` accepts direct/batch image URLs, validates policy/MIME/magic bytes and persists assets. | Generic `MediaJob` naming; it is not a generic media feature. |
| Video | `VideoDiscoveryService` validates approved source and normalizes supplied raw items. | It does not fetch or download video. |

No source, dependency, configuration or Docker change is in scope. Current
`app/services/`, `app/adapters/`, `app/workers/` and transitional `app/api/`
remain in place. Physical feature-module extraction is a separate future project.

## Feature definitions and workflows

### 1. Search Discovery

**Input:** query, page/limit, redacted caller/quota context.

**Output:** normalized, deduplicated `SearchResultSet` of safe title/URL/snippet
metadata.

**Rule:** Search never crawls, discovers media or creates another feature job.
For `search_and_extract`, Workflow Orchestration applies a registered bounded
selection rule and creates separate Crawl Data job intents.

### 2. Crawl Data

**Input:** one approved page URL and redacted caller/policy context.

**Output:** `Document` with canonical URL, clean HTML/Markdown, content hash,
one `document_type`, confidence, reason and `needs_review`; an explicit media
discovery workflow may also retain a `MediaCandidateManifest` as evidence.

**MVP classification:** `news_article`, `learning_material`, `course_page`,
`technical_documentation`, `api_reference`, `academic_article`, `blog_article`,
`book_chapter`, `listing_page`, `navigation_page`, `media_page`, `generic_page`
or `unknown`. Classification uses trustworthy structured metadata, then DOM/content
signals, URL patterns and finally caller hint. It never invents missing metadata.

**Rule:** classification and candidate discovery never auto-follow links or create
download jobs. Every initial URL and redirect passes Network Policy; static fetch is
the MVP. Browser processing is permitted only by a reviewed server-side recipe.

### 3. Image Download

**Direct workflow:** `download_image` accepts one allowed image URL or a bounded
explicit image manifest.

**Page workflow:** `extract_images` accepts a page URL. Crawl Data extracts only
static image evidence allowed by its parser (for example `img`, responsive image
sources and approved metadata). Workflow Orchestration deduplicates/selects within
the registered count, byte and time budget, then creates one bounded
`ImageDownloadJob`.

**Output:** `ImageManifest` with per-item `completed`, `failed` or `blocked`
outcome and safe asset references. Each candidate URL is policy-checked before
network access, streamed under per-item/total-byte limits, validated by declared
MIME and magic bytes, then persisted with checksum/size/MIME/object metadata.

**Ownership:** Crawl Data owns `ImageCandidateManifest` and static image parsing.
Image Download never parses page HTML or discovers candidates itself.

### 4. Video Download

**Direct workflow:** `download_video` accepts one approved-source video URL or
approved source reference.

**Page workflow:** `extract_video` accepts an approved page/source URL. A fixed,
reviewed source recipe may extract static video evidence (for example `video`,
`source`, allowed Open Graph media or approved `.mp4`/`.m3u8` references). Browser
wait/click/capture is v1.2 only and cannot receive selectors, JavaScript, cookies or
credentials from the request.

**Output:** one `VideoAsset` or bounded video manifest with terminal reason codes.
The worker rechecks source registry, Network Policy, entitlement and DRM before
download. `.mp4` is handled as a bounded stream. `.m3u8` is a playlist: it is parsed
only for an approved source, its segment/variant URLs are policy-checked and bounded,
and encrypted/DRM/unsupported playlists are terminally blocked. Signed URLs, cookies,
authorization headers and raw capture are never persisted.

**Ownership:** Video Download owns `VideoCandidateManifest`, the approved-source
registry, recipe version and DRM/entitlement decision. Crawl Data may supply a
normalized page/document reference, but it does not select video candidates and does
not decide whether a video may be downloaded.

### 5. Torrent Download — deferred and separate

A discovered `.torrent` or magnet link may be recorded as a safe candidate reference,
but Video Download never downloads it. `torrent_download` is a separate future feature
because peer, disk, bandwidth, file-count, legal/source and retention controls differ
from HTTP/HLS video. It requires a separate product/legal decision, approved sources,
and its own workflow, quota and audit design.

## Cross-feature workflow boundary

```text
WorkflowRequest
  ├─ crawl_url(page) ─────────────→ Crawl Data ─→ Document
  ├─ extract_images(page) ────────→ Crawl Data ─→ ImageCandidateManifest
  │                                      └─ registered selection + budget
  │                                          → Image Download ─→ ImageManifest
  └─ extract_video(page/source) ──→ Crawl/approved recipe ─→ VideoCandidateManifest
                                         └─ registered selection + budget
                                             → Video Download ─→ VideoAsset/Manifest
```

Only Workflow Orchestration may fan out from a candidate manifest. Crawl Data, Image
Download and Video Download never call one another or publish downstream work directly.
Direct and page workflows have distinct registered definitions; page content cannot
choose workflow steps, selectors, JavaScript, credentials or arbitrary executable input.

## Durable references and result shape

Page workflows are two-stage: Crawl Data persists its `Document` first, then the owning
media feature persists the candidate manifest. The workflow result carries both
`document_reference` and media-manifest reference when Crawl Data ran. `extract_video`
may use the approved recipe to enrich candidates, but the page/document reference stays
available for audit and provenance.

A candidate manifest is durable evidence, not a transient list:

- It holds the source page reference, candidate ID, ordered safe metadata and a candidate
  URL only where the owning feature needs that URL to execute.
- Result events and UI-facing manifests expose candidate IDs, outcome/reason codes and
  asset references; they never expose cookies, authorization headers, signed URLs or raw
  browser capture.
- Candidate URLs are stored only in the durable feature record, never in logs or result
  payloads. Credential-bearing/user-info URLs are rejected; expiring signed URLs are
  re-resolved by the owning feature at execution rather than persisted.
- Retention/delete follows the source policy and the existing storage contract; a deleted
  manifest does not leave downloadable orphan assets.

Downstream download jobs reference the durable manifest ID plus selected candidate IDs,
never a caller-supplied replacement URL or provider-specific payload.

## Version roadmap

| Version | Allowed workflows | Exclusions |
|---|---|---|
| MVP v1 | `search`, `crawl_url`, `search_and_extract`; static document classification. | Media child jobs, browser action, recursive links, scheduling. |
| v1.1 | `download_image`, `extract_images` from static page evidence with bounded item/byte budget. | Browser lazy-load, automatic page expansion. |
| v1.2 | `download_video`, `extract_video` from approved sources; bounded `.mp4` and approved `.m3u8` handling. | Login, paywall/CAPTCHA/geo bypass, request-provided browser/program input. |
| Later | `torrent_download` only after a separate decision; bounded collection crawl may be considered separately. | Treating magnet/`.torrent` as ordinary video URLs. |

## Security and operational constraints

- Network Policy gates every candidate URL and redirect; image validates every manifest
  item; video additionally requires approved source, entitlement and DRM checks.
- Quotas cover candidate count, requests, bytes, time and concurrency; HLS adds segment
  and playlist limits; torrent has separate peer/disk/bandwidth controls if approved.
- Blocked policy, invalid MIME, quota, DRM, entitlement and unsupported playlist outcomes
  are terminal and non-retryable. Only typed transient network/storage failures retry.
- Tests use controlled fixtures/approved targets. No unit test calls external web search,
  pages, image hosts or video hosts.

## Documentation changes

Create one canonical media-candidate/workflow contract and align active feature,
workflow, classification, architecture-roadmap and learning documents to it. The
documentation must distinguish **current runtime behavior**, **versioned target
workflow** and **deferred capability** at every feature boundary.

## Acceptance criteria

- Reader can tell direct URL download from explicit page-driven discovery for image/video.
- Crawl Data has one document classification taxonomy and does not auto-download candidates.
- Image and Video flows state candidate selection, policy, validation, budget, persistence
  and terminal outcomes.
- `.mp4`, `.m3u8` and torrent/magnet have distinct handling rules.
- Current runtime limitations and deferred module extraction remain truthful.
