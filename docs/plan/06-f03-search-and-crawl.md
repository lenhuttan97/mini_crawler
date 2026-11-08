# P05 — F03: Search rồi Crawl

> **Mục tiêu:** tìm URL qua provider, chuẩn hóa kết quả và để caller chọn URL để tạo F01 CrawlJob.  
> **Dependency:** P02 F01 Crawl URL; P01 Shared Platform.

## 1. Yêu cầu

- Search nhận query, page/limit trong quota/rate limit; trả title, canonical URL, snippet và provider metadata đã lọc.
- SearXNG là adapter; lỗi provider không làm API crawl tự fallback hoặc tự crawl hàng loạt.
- Caller chọn một result/URL; service gọi đúng API/service F01 create job.
- Search history theo authorization/retention, ưu tiên hash/redaction của query.

## 2. Work breakdown

| # | Hạng mục | Thực hiện | Done khi |
|---|---|---|---|
| 1 | Search request contract | Validation query/page/limit, rate-limit/quota, error mapping. | Invalid request không gọi provider. |
| 2 | Provider adapter | HTTPX timeout, JSON schema check, circuit/backoff policy. | Provider error được phân loại. |
| 3 | Normalization | Canonicalize URL, title/snippet sanitization, dedupe, response size limit. | Không lộ raw provider payload. |
| 4 | Selected crawl | Result ID/URL đã chọn gọi F01 create job qua shared service. | Không có crawler thứ hai. |
| 5 | History/audit | Authorization, retention/redaction và search metrics. | User chỉ thấy lịch sử của mình. |

## 3. API contract

| API | Input | Output |
|---|---|---|
| Search | query, page, limit | normalized result list + pagination/provider status |
| Crawl selected result | result ID hoặc URL | `crawl_job_id` từ F01 |
| Search history | filters/page | authorised, paginated history |

## 4. Test và acceptance

- Unit: query validation, result dedupe, URL canonicalization, page/limit cap.
- Integration (respx): valid JSON, malformed JSON, timeout, HTTP 429/5xx and circuit behavior.
- Contract: selected result tạo đúng F01 command; search request tự nó không tạo `CrawlJob`.
- Security: result URL vẫn qua Policy Gate lúc tạo F01 job; history không leak query cross-tenant.

## 5. Risks/DoD

| Risk | Mitigation |
|---|---|
| Provider rate limit/outage | Timeout, backoff/circuit, clear upstream error. |
| Search result độc hại | Normalize rồi vẫn Policy Gate tại F01. |
| Crawl hàng loạt ngoài ý muốn | Explicit selected-result endpoint, no auto-enqueue. |

- [ ] Search adapter/normalizer/selected-crawl tests pass.
- [ ] Không có code path tự crawl toàn bộ/danh sách kết quả.
- [ ] Search result crawl tái sử dụng F01 idempotency, policy và job status.
