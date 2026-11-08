# Mini Crawler — Kế hoạch triển khai chi tiết

> **Trạng thái:** kế hoạch thực hiện, chưa triển khai mã nguồn  
> **Nguồn yêu cầu:** `../feature-roadmap.md`, `../sample/mini_crawler_implementation_plan.md`  
> **Phạm vi:** ba feature chính — crawl URL, download media/video và search rồi crawl — cùng các feature hỗ trợ cần thiết để vận hành an toàn.

## 1. Mục tiêu sản phẩm và ranh giới

### Mục tiêu

1. Người dùng gửi một URL để crawl dữ liệu thành Markdown/metadata (**F01**).
2. Người dùng gửi URL media, trang video, torrent/magnet hoặc batch ảnh để tải **nội dung họ có quyền sử dụng** (**F02**).
3. Người dùng tìm kiếm, chọn một kết quả, rồi đưa URL đã chọn vào F01 (**F03**).
4. Mọi tác vụ dài chạy bất đồng bộ, có trạng thái, audit, quota, quan sát và lưu trữ bền vững.

### Không thuộc phạm vi

- Không crawl toàn bộ domain, deep crawl hoặc auto-crawl mọi kết quả search.
- Không bypass DRM, paywall, CAPTCHA, geo-blocking, anti-bot hay kiểm soát truy cập.
- Không nhận cookie, token, selector hoặc JavaScript tùy ý từ người dùng/LLM.
- Không hỗ trợ nguồn media/torrent chưa xác minh quyền phân phối. RSS chỉ dùng cho nguồn đã được allowlist và cấp phép.

## 2. Kiến trúc đích

```text
Client
  │
  ▼
FastAPI API ──► Policy Gate ──► PostgreSQL (jobs, metadata, audit)
  │                    │
  │                    └──► Redis/Celery queues
  │                                  │
  ├──► Search service/SearXNG        ├──► Crawl worker
  │                                  ├──► Media worker
  │                                  └──► Torrent worker (nguồn được phép)
  │                                             │
  └─────────────────────────────────────────────┼──► MinIO/S3 (assets)
                                                └──► OpenTelemetry/Prometheus/logs
```

### Quy tắc kiến trúc

- API validate request, tạo job và trả `job_id`; không crawl/download đồng bộ.
- Policy Gate là đường duy nhất trước mọi kết nối mạng: kiểm tra URL, DNS/IP, redirect, domain, quyền, quota và loại thao tác.
- F03 tái sử dụng F01; không có crawler thứ hai cho search results.
- F02 dùng một job platform chung, nhưng queue/worker tách với crawl để giới hạn tài nguyên.
- Object storage không public; API chỉ cấp quyền truy cập asset theo authorization và TTL ngắn.

## 3. Phases triển khai và deliverable

| Phase | Mục tiêu | Deliverable | Điều kiện đi tiếp |
|---|---|---|---|
| P00 | Foundation | repo Python, config, Docker local, health checks, CI tối thiểu | test/lint chạy, secret không vào Git |
| P01 | Platform dùng chung | policy gate, job lifecycle, queue, storage, observability cơ bản | tạo/đọc job được, worker mock hoạt động |
| P02 | F01 Crawl URL | static crawl, browser fallback, normalise, persist | crawl URL demo thành Markdown an toàn |
| P03 | F02 Direct/batch image | direct media, batch image, validation, asset storage | từng item có status và quota |
| P04 | F02 Video/torrent | video-page discovery, DRM gate, allowed torrent/magnet | chỉ source approved, worker sandbox/quota |
| P05 | F03 Search → selected crawl | SearXNG adapter, result normalization, chọn URL tạo CrawlJob | search không auto-crawl |
| P06 | Feature phụ sản phẩm | library, job retry/cancel, asset management, search nội bộ | authorization/audit đầy đủ |
| P07 | AI và vận hành | RAG citation, MCP adapter, dashboard/alert | đo được reliability/cost, tool quyền tối thiểu |
| P08 | Release | hardening, benchmark, backup/restore drill, runbook | đạt acceptance criteria và sign-off |

## 4. P00 — Foundation

### 4.1 Cấu trúc mã nguồn đề xuất

```text
app/
  api/                 # routers, request/response schemas
  core/                # settings, security, policy, exceptions
  domain/              # entities, enums, service interfaces
  services/            # application services
  workers/             # Celery app và task handlers
  adapters/            # SearXNG, HTTPX, browser, yt-dlp, torrent, storage
  repositories/        # persistence access
  observability/       # logging, metrics, tracing
tests/
  unit/
  integration/
  e2e/
infra/
  compose/
  searxng/
  monitoring/
```

### 4.2 Việc thực hiện

1. Khởi tạo Python 3.12, `uv`, `pyproject.toml` và `uv.lock`.
2. Tạo FastAPI app, `/health/live`, `/health/ready`, OpenAPI metadata.
3. Tạo `Settings` đọc environment; commit `.env.example`, ignore `.env`.
4. Docker Compose local cho API, PostgreSQL, Redis, MinIO và SearXNG; bind cổng local, pin image khi deploy.
5. Cấu hình Ruff, pytest, pytest-asyncio, respx và pre-commit/CI.
6. Tạo structured log với correlation ID; redaction mặc định cho token, cookie, authorization header và URL query.

### 4.3 Acceptance criteria

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` chạy trong CI.
- API không start khi thiếu required secret ở môi trường production.
- Health endpoint không lộ config, secret hoặc thông tin upstream nhạy cảm.

## 5. P01 — Platform dùng chung

### 5.1 Policy Gate

**Input:** URL, thao tác (`crawl`, `media_download`, `torrent`, `search_result`), caller identity và policy context.  
**Output:** quyết định `allowed`/`blocked` cùng reason code đã redaction.

Các bước bắt buộc:

1. Chỉ nhận `http`/`https` nơi phù hợp; torrent chỉ nhận magnet/torrent đã được xác thực theo policy.
2. Parse URL nghiêm ngặt; từ chối user-info, scheme nguy hiểm, port không cho phép và hostname bất thường.
3. Resolve toàn bộ DNS A/AAAA, chặn loopback/private/link-local/multicast/reserved/internal IP.
4. Kiểm tra địa chỉ kết nối thực tế và lặp lại kiểm tra trước mọi redirect để giảm DNS rebinding.
5. Kiểm tra allowlist, `robots.txt` với crawl, quyền nội dung và quota của caller/domain.
6. Ghi audit decision không chứa URL query, token, cookie hoặc body nhạy cảm.

### 5.2 Job Platform

**Job states dùng chung:** `pending`, `queued`, `running`, `completed`, `failed`, `cancelled`, `blocked_policy`, `blocked_drm`, `blocked_permission`, `expired`.

1. API tạo job với `idempotency_key`, caller ID, feature code, input đã redaction và policy decision.
2. Worker claim job atomically; cập nhật heartbeat/progress có kiểm soát tần suất.
3. Retry chỉ cho lỗi tạm thời (timeout, lỗi upstream, transient storage); không retry `blocked_*`, validation error hay lỗi quyền.
4. Cancellation là cooperative: worker kiểm tra cờ cancel giữa các bước/từng item batch.
5. Job status API chỉ trả dữ liệu caller có quyền xem.

### 5.3 Data model tối thiểu

| Bảng | Trường cốt lõi | Index/ràng buộc |
|---|---|---|
| `jobs` | id, type, status, caller_id, idempotency_key, attempts, progress, created_at, finished_at | unique `(caller_id, idempotency_key)`, index status/created_at |
| `crawl_jobs` | job_id, requested_url, canonical_url, policy_status, error_code | unique job_id, index canonical_url |
| `documents` | id, canonical_url, title, content_hash, markdown_key, crawled_at | unique canonical_url + content hash policy, index hash |
| `media_jobs` | job_id, input_type, source_url, policy_status, drm_status | unique job_id, index status |
| `media_job_items` | id, media_job_id, sequence, source_url, status, error_code | unique `(media_job_id, sequence)` |
| `media_assets` | id, job_id, object_key, mime_type, byte_size, checksum, metadata | index checksum/object_key |
| `search_requests` | id, caller_id, query_hash, provider, created_at | retention/authorization policy |
| `audit_events` | id, caller_id, action, decision, reason_code, trace_id, created_at | index caller/action/time |

Mọi migration phải có review thủ công, kế hoạch rollback và test upgrade từ database rỗng lẫn database phiên bản trước.

### 5.4 Storage & queue

- PostgreSQL: transaction/state/metadata; MinIO: raw HTML, Markdown và asset; Redis: broker/cache/ephemeral rate-limit.
- Object key không suy ra từ title do người dùng cung cấp; dùng ID/hash server-side.
- Tách queue: `crawl`, `media`, `torrent`, `maintenance`; đặt concurrency, time limit và memory limit riêng.

## 6. P02 — F01: Crawl data từ link người dùng cung cấp

### 6.1 API contract

| Operation | Request | Response |
|---|---|---|
| Create crawl job | `url`, optional idempotency key, optional `document_type_hint` | `crawl_job_id`, `status`, `policy_status` |
| Get crawl job | job ID | status, progress, error code an toàn, document ID khi hoàn tất |
| Get document | document ID | canonical URL, title, Markdown, `document_type`, confidence/reason và metadata theo quyền |
| Cancel crawl job | job ID | accepted/cancelled status |

### 6.2 Luồng worker

1. Claim job và thực hiện lại Policy Gate ngay trước network call.
2. Fetch bằng HTTPX streaming: timeout, response-size limit, content type allowlist, không tự follow redirect.
3. Với mỗi redirect hợp lệ: validate lại URL/DNS/IP rồi mới request tiếp.
4. Khi HTML tĩnh thiếu nội dung cần thiết: chuyển browser fallback có timeout, context sandboxed và `check_robots_txt`.
5. Browser chỉ dùng action recipe server-side đã review; không login, không chạy JS/selector từ caller hoặc LLM.
6. Normalise: clean HTML, remove noise, Markdown, canonical URL, title, links, content hash.
7. Classify một `document_type` chính từ HTML/JSON metadata và DOM; `document_type_hint` của caller chỉ là tín hiệu. Lưu confidence/reason/`needs_review`; fallback `generic_page`/`unknown` khi thiếu tín hiệu.
8. Nếu content hash không đổi: cập nhật metadata/status, không tạo duplicate chunks/assets.
9. Persist PostgreSQL/MinIO transactionally theo compensating workflow; cập nhật job `completed` hoặc error code.

### 6.3 Tests và acceptance

- Unit: URL policy, redirect validator, normalizer, document classifier, content-hash dedupe.
- Integration: mocked HTTPX/respx cho success, timeout, oversize, redirect-to-private-IP, invalid content type.
- E2E: website fixture do team kiểm soát cho static, JavaScript fallback, news article và generic/listing fallback.
- Done khi crawl fixture tạo được một document, không gọi browser khi static content đủ, và không gọi mạng thật trong unit test.

## 7. P03/P04 — F02: Download media, video và batch image

### 7.1 F02.1/F02.1a — Direct media và batch image

**Request:** một URL media hoặc danh sách/manifest ảnh từ source `approved`.  
**Response:** `media_job_id`; với batch, kết quả từng item qua `media_job_items`.

Worker thực hiện:

1. Validate policy từng URL; deduplicate theo canonical URL/checksum.
2. Áp dụng max item count, tổng byte, byte/item, concurrency và quota caller/domain.
3. Download streaming, chặn theo `Content-Length` và byte thực tải.
4. Validate content type + magic bytes trước persist; từ chối type không cho phép.
5. Lưu asset, checksum, dimensions (Pillow optional), sequence và trạng thái từng item.
6. Trả batch manifest: `completed`/`failed`/`blocked` trên từng item, không làm lộ secret URL.

### 7.2 F02.2 — Video page discovery

1. Chỉ chạy cho domain/recipe `approved`.
2. Browser worker dùng context không chia sẻ credential và giới hạn resource/time.
3. Recipe versioned chỉ gồm action hữu hạn đã review; có expected state và max actions.
4. Network capture được redaction trước log/persist; không lưu cookie, authorization header hay signed URL.
5. Phát hiện DRM/EME/`ContentProtection` thì đặt `blocked_drm` và dừng.
6. Nếu policy cho phép, dùng adapter đã phê duyệt để lấy metadata/download; format processing chạy trong worker.

### 7.3 F02.3/F02.4 — Torrent/magnet và licensed RSS

1. Chỉ chấp nhận torrent/magnet hoặc RSS source có quyền phân phối rõ ràng và nằm trong `approved source registry`.
2. RSS chỉ discovery; người dùng/caller phải chọn item, rồi tạo một `MediaDownloadJob` riêng.
3. Torrent worker chạy cách ly, quota peers/bandwidth/disk/time, không có quyền truy cập secret hoặc mạng nội bộ.
4. Kiểm tra metadata/tệp sau tải: allowlist loại tệp, số lượng file, kích thước, checksum khi có và malware scanning theo môi trường.
5. Không bật cho source `pending_review`, `blocked`, nguồn không xác minh quyền hoặc nội dung bị hạn chế.

### 7.4 F02.5–F02.8 — Policy, conversion và asset management

- Entitlement/DRM gate chạy trước download; mọi `blocked_*` trả reason code minh bạch.
- FFmpeg/yt-dlp chỉ là adapter cho luồng đã được phép; chạy process sandboxed, không shell command từ user input.
- Object access thông qua authorization + presigned URL TTL ngắn; support delete/retention theo policy.
- Có progress hook rate-limited; không ghi progress mỗi byte vào database.

### 7.5 Tests và acceptance

- Unit: quota, manifest parsing, dedupe, MIME/magic-byte validation, DRM/policy decision.
- Integration: storage mock, downloader adapter fake, batch partial failure, cancellation giữa batch.
- E2E: sample media/torrent hợp pháp do team kiểm soát; không dùng third-party copyrighted fixtures.
- Done khi partial failure không làm mất kết quả item khác, source không approved bị chặn trước network call, và asset không public.

## 8. P05 — F03: Search rồi crawl

### 8.1 API contract

| Operation | Request | Response |
|---|---|---|
| Search | query, page/limit | results: title, canonical URL, snippet, provider metadata |
| Crawl selected result | URL/result ID đã chọn | gọi lại API create crawl job của F01 |

### 8.2 Luồng thực hiện

1. Validate query length, rate limit và caller quota.
2. Gọi SearXNG với timeout; xử lý lỗi upstream tách biệt với lỗi input.
3. Normalise URL/title/snippet, dedupe, giới hạn response và không trả raw provider payload.
4. Người dùng chọn cụ thể một URL; API tạo F01 job qua service interface chung.
5. Không enqueue crawl tự động từ search result, kể cả khi LLM đề xuất URL.
6. Search history chỉ lưu theo authorization/retention policy, ưu tiên query hash/redaction.

### 8.3 Tests và acceptance

- Unit: query validation, dedupe, result mapping.
- Integration: SearXNG adapter qua respx cho JSON, timeout, malformed payload và rate limit.
- E2E: SearXNG local fixture; xác nhận search không tạo CrawlJob nếu chưa có selected URL.

## 9. P06 — Feature phụ sản phẩm

| Feature | Plan triển khai | Definition of done |
|---|---|---|
| S01 Authorization/tenant | Caller identity, ownership checks ở mọi API/query/object access. | Không caller nào xem/hủy/tải asset của caller khác. |
| S02 Retry/cancel | Retry classification, exponential backoff/jitter, cancellation cooperative. | Không retry lỗi policy; cancel không làm orphan asset/job. |
| S03 Audit trail | Ghi action, caller, decision, trace ID, retention/redaction. | Điều tra được quyết định mà không lộ secret. |
| S04 Document library | List/filter/paginate document, dedupe view, retention/delete policy. | Query có pagination và authorization. |
| S05 Search stored data | PostgreSQL full-text trước; pgvector sau benchmark. | Có benchmark/citation source ID cho mỗi result. |
| S06 RAG citation | Retrieve approved chunks, validate citation IDs, display source URL. | Citation bịa bị loại trước response. |
| S07 Agent/MCP | Tool typed, read-only default, approval cho side effect. | Agent không có shell/free network/database access. |
| S08 Dashboard/alert | Metrics, SLO, alerts queue/error/quota/cost. | Có runbook và cảnh báo được test. |

## 10. P07/P08 — Observability, security và release

### 10.1 Metrics và SLO ban đầu

- `jobs_total{type,status}`, queue depth, job duration histogram, retry count, blocked-policy count.
- HTTP/browser/torrent/media bytes duration, failure ratio và storage bytes.
- SLO đề xuất: job status API availability, queue delay percentile, crawl/media completion ratio theo source approved.
- Không đặt URL đầy đủ, raw query, token, cookie hoặc document body làm log/metric label/trace attribute.

### 10.2 Security review checklist

- SSRF verified trên URL ban đầu và mọi redirect.
- Egress network policy chặn internal services; worker/service account có quyền tối thiểu.
- Browser, ffmpeg/downloader/torrent process có time/memory/disk/network limits.
- Dependency scan, pin/lock version, secret scan và review third-party adapter update.
- Backup PostgreSQL/MinIO, restore drill và retention/deletion procedure.

### 10.3 Release plan

1. Deploy P00/P01 vào staging với fixtures do team kiểm soát.
2. Bật F01 cho allowlist hẹp; quan sát quota, SSRF blocks, latency và storage.
3. Bật F02 direct/batch trước, sau đó video/torrent source `approved` theo feature flag riêng.
4. Bật F03 sau khi F01 ổn định; không bật auto-crawl.
5. Bật S04–S08 theo feature flag, benchmark và security sign-off.
6. Rollback: disable feature flag/queue consumer trước; giữ dữ liệu/audit; rollback migration chỉ khi đã kiểm chứng tương thích dữ liệu.

## 11. Quy trình phát triển cho mỗi feature

1. Chốt requirement, policy rule, API contract, schema impact và acceptance criteria.
2. Viết test Red cho behaviour/edge case; xác nhận test thất bại.
3. Implement tối thiểu để Green; chạy unit test liên quan.
4. Refactor, lint/format, test integration và rà soát security/N+1/resource limits.
5. Cập nhật tài liệu API, runbook, metrics/audit events và migration notes.
6. Review diff, benchmark cần thiết, rollout bằng feature flag và theo dõi sau release.

## 12. Risk register

| Risk | Mức | Mitigation |
|---|---|---|
| SSRF/DNS rebinding | Cao | Policy Gate + egress restriction + validate redirect/connection address. |
| Nội dung không có quyền/DRM | Cao | Source registry, entitlement gate, deny-by-default, audit, blocked state. |
| Batch/torrent làm cạn disk/bandwidth | Cao | Quota, sandbox, queue riêng, disk/bandwidth/time limit, cancellation. |
| Browser worker ngốn RAM | Trung bình | Pool giới hạn, timeout, worker queue riêng, metrics memory. |
| Duplicate crawl/media | Trung bình | Idempotency key, content hash/checksum, unique constraints. |
| Upstream search/media thay đổi | Trung bình | Adapter boundary, contract tests, feature flags, graceful failure. |
| Rò rỉ secret qua log/capture | Cao | Redaction default, log review, test secret scanning. |

## 13. Checklist hoàn tất dự án MVP

- [ ] P00–P05 đạt acceptance criteria và test tự động.
- [ ] Migration upgrade/rollback được kiểm thử; backup/restore drill thành công.
- [ ] F01/F02/F03 dùng chung Policy Gate và Job Platform; không có pipeline trùng lặp.
- [ ] Source registry deny-by-default; source không approved không gây network request.
- [ ] Không có SSRF/private-network access, secret log hoặc public object storage.
- [ ] Metrics, trace, audit, alert và runbook sẵn sàng cho feature đã bật.
- [ ] Security, performance và legal/policy review sign-off trước production.

## 14. Tài liệu liên quan

- `../feature-roadmap.md` — catalog feature chính/phụ.
- `../sample/mini_crawler_implementation_plan.md` — lựa chọn công nghệ và kiến trúc tham chiếu.
- `../learning/README.md` — lộ trình học công nghệ.
