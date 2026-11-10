# Mini Crawler — Target Worker Platform

## Source of truth

- Build toward the worker-first contracts indexed by `docs/INDEX.md`. `docs/sample/` is historical/reference material; do not derive target behavior from it or from transitional API-era code.
- The target has four isolated features: Search, Web Crawl, Image Download, and Video Download. Organize new target code feature-first (`domain/`, `application/`, `infrastructure/`, `worker/`), with shared workflow, job, queue, network-policy, and storage platforms.

## Workflow and job boundaries

- Only `WorkflowOrchestration` may fan out, join, or create downstream `JobIntent`s. Feature workers never call another feature service or queue directly.
- `JobOrchestration` alone creates/transitions `FeatureJob`; persist the typed durable command and outbox event atomically. Queue messages carry only `job_id`, `feature_code`, `contract_version`, and `correlation_id`.
- PostgreSQL is the source of truth; Redis/Celery provides at-least-once delivery. A worker acquires a lease, loads its command from durable storage, and delivery is acknowledged only after the outcome is durably committed.
- Use target feature queues: `search.execute.v1`, `web-crawl.execute.v1`, `image.execute.v1`, `video.execute.v1`, and `worker.maintenance.v1`. Do not introduce a generic media or torrent queue; DLQs are not auto-consumed.
- Retry only typed transient failures. Policy, DRM, entitlement, validation, malformed-command, and cancellation outcomes are terminal; DLQ requeue requires authorization and audit.

## Safety and data handling

- `network_policy` is the mandatory gate before every network call: validate scheme/port/host and all DNS records, revalidate redirects, then apply source/allowlist, quota, and robots rules. Check every image URL separately.
- Job/request content must never supply selectors, JavaScript, cookies, credentials, or shell arguments. Browser recipes and video sources are reviewed, versioned, and registered server-side.
- Never log or return raw query strings, credentials, cookies, tokens, signed URLs, browser captures, or queue payloads. Results expose safe references and reason codes.
- Web Crawl alone persists documents; Image Download and Video Download alone persist assets. Use server-generated object keys, validate before persistence, retain partial image successes, and clean up orphaned objects on transaction failure.

## Feature limits and roadmap

- Search is discovery-only: it never crawls, discovers media, or creates feature jobs. Only explicit bounded `search_and_extract` may schedule crawl work.
- MVP supports bounded static `search`, `crawl_url`, and `search_and_extract`; no browser action, media download, recursive links, or schedules. `crawl_collection` remains deferred and must be bounded through workflows.
- Image page extraction is v1.1: Crawl Data owns static `ImageCandidateManifest`; Image Download never parses page HTML. Video is v1.2: only approved sources and reviewed recipes; DRM/entitlement blocks have no bypass. Torrent download is deferred pending a separate product/legal decision.
- New workflow definitions, selection rules, browser recipes, and source registrations require policy/security review. Keep registered budgets for count, bytes, time, depth, and approved sources.

## Target verification

- Queue changes need coverage for lease contention, outbox redelivery, commit crashes, expired-lease reclaim, retry classification, DLQ authorization, and cancellation checkpoints.
- Add feature tests for their documented failure boundaries: redirect/private-IP policy, document dedupe, per-item image validation/partial manifests, and video source/DRM/entitlement/redaction/sandbox behavior.
