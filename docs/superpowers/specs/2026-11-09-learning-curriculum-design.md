# Learning Curriculum Restoration and Alignment Design

## Intent

Khôi phục bộ tài liệu `docs/learning/` thành lộ trình Beginner → Master cho Mini Crawler, nhưng không để người học nhầm lẫn giữa dependency/runtime đang có, kiến trúc worker-first đích và công nghệ học sau MVP.

## Goals

- Khôi phục sáu học phần và landing page từ phiên bản đã được theo dõi trong Git.
- Giữ hướng dẫn thực hành chi tiết hiện có khi vẫn phù hợp.
- Thêm trạng thái rõ ràng cho từng công nghệ: **Current repository**, **Target architecture**, hoặc **After MVP / dependency not installed**.
- Dạy workflow/job orchestration—`WorkflowRun`, `FeatureJob`, idempotency, outbox, lease, retry/DLQ và bounded fan-out—as the advanced core of this repository.
- Giữ media/browser, LLM/MCP, vector search, tracing/metrics là nội dung học có điều kiện và không trình bày như capability đã chạy.
- Liên kết learning index với `docs/INDEX.md` và contracts/platform hiện hành.

## Constraints

- Chỉ chỉnh Markdown; không thêm dependency, source code, configuration hoặc container.
- Nội dung thực hành không gọi target Internet không được phép; không bypass CAPTCHA, DRM, paywall hoặc access control.
- Không trình bày browser recipe, recursive crawl, media download, scheduler, LLM/MCP, pgvector, Crawl4AI, Playwright, yt-dlp, FFmpeg, Pillow, OpenTelemetry hoặc Prometheus là dependency đã cài nếu `pyproject.toml` không khai báo chúng.
- FastAPI/API chỉ được trình bày như runtime hiện có/producer boundary trong quá trình chuyển đổi; target worker repository không nhận HTTP controller.

## Curriculum structure

| Module | Level | Current learning outcome | Deferred/target boundary |
|---|---|---|---|
| 01 Foundation | Beginner | Python 3.12, uv, Pydantic, FastAPI runtime hiện có, Docker Compose, test cơ bản. | FastAPI không phải target worker entrypoint. |
| 02 Data, jobs and storage | Intermediate | PostgreSQL, SQLAlchemy, Alembic, Redis, Celery, MinIO. | pgvector chỉ sau benchmark/dependency quyết định. |
| 03 Workflow orchestration | Advanced | Workflow request/run/step, JobIntent/FeatureJob, outbox, lease, retry/DLQ. | Bounded image/video/depth/scheduler theo version roadmap. |
| 04 Media workflows | Advanced | Policy, source approval, per-item result, MIME/magic-byte concepts. | Image v1.1; browser/video v1.2; yt-dlp/FFmpeg/Pillow only when installed. |
| 05 Observability and quality | Master | structlog, pytest, pytest-asyncio, respx, Ruff, security/release checks. | OpenTelemetry/Prometheus after dependencies and runtime wiring are added. |
| 06 Search and crawl capstone | Master | SearXNG, HTTPX, selectolax, markdownify, static fetch, classification, bounded `search_and_extract`. | Crawl4AI/Playwright chỉ sau khi dependency, recipe và sandbox được phê duyệt. |

## Content rules

Every module begins with a status table and ends with:

1. practice exercises restricted to local fixtures/controlled targets;
2. a checklist distinguishing knowledge from implemented capability;
3. links to the authoritative architecture/platform docs;
4. a transition to the next module.

`03-workflow-orchestration-and-ai.md` is repurposed as the orchestration module to match the project’s current learning needs. It retains a short “after MVP” section for LLM/MCP rather than teaching it as a present runtime component. Search is the final capstone, after learners have acquired workflow, policy and quality foundations.

## Acceptance criteria

- `docs/learning/README.md` provides a truthful Beginner → Master path and links every module.
- A learner can identify what is installed now versus what requires a future dependency/approved architecture step.
- Modules 03–04 explain shared job lifecycle versus workflow orchestration without conflicting with `docs/platform/`.
- Local Markdown links remain valid across root docs and `docs/`.
