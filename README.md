# Mini Crawler

Mini Crawler is a policy-first data-collection platform for web search, document crawling and approved-media ingestion.

> **Architecture status:** the repository is transitioning from the current API-centric local stack to a worker-first architecture. The target architecture is documented; it is not a claim that every worker component is implemented today.

## Target architecture

An explicit request creates a bounded workflow. The workflow may search, crawl and later discover approved images or video, but it never follows links, downloads media or runs browser actions unless its registered workflow definition permits that step.

```text
WorkflowRequest
  → Workflow Orchestration
  → Job Orchestration
  → Queue Management
  → Search / Web Crawl / Image / Video worker
  → durable result reference
```

- **MVP v1:** `search`, `crawl_url` and bounded `search_and_extract` workflows for static content.
- **v1.1 / v1.2:** approved static-image and video/browser-recipe workflows.
- **v2+:** bounded depth 2–3 crawl and registered scheduled recrawl.

Read the active contracts and runbooks in [docs/INDEX.md](docs/INDEX.md). Historical/reference material is isolated under `docs/sample/`.

## Scope and safety boundaries

- Search alone never crawls results; only an explicit, bounded `search_and_extract` workflow may create crawl jobs.
- All network calls pass Network Policy; redirects are revalidated.
- Browser recipes, media sources and workflow definitions are registered server-side. Request content cannot supply selectors, JavaScript, credentials or shell arguments.
- DRM, entitlement, policy, validation and cancellation outcomes are terminal; no bypass path is supported.

## Local development

The current Docker Compose stack still starts the existing `api`, PostgreSQL, Redis, MinIO and SearXNG services. It is a local baseline during the transition; it does not by itself prove that the target worker-first workflow architecture is running.

See [STARTUP.md](STARTUP.md) for commands and health checks.
