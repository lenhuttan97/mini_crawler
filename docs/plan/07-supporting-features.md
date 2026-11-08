# P06 — Supporting Features

> **Mục tiêu:** biến F01/F02/F03 thành sản phẩm dùng được, có quyền truy cập, lifecycle hoàn chỉnh và khai thác dữ liệu an toàn.  
> **Dependency:** P02–P05.

## 1. S01–S03: Authorization, retry/cancel, audit

| Feature | Yêu cầu thực hiện | Acceptance |
|---|---|---|
| S01 Authorization/tenant | Caller identity, ownership check ở mọi job/document/asset/history query, object access TTL ngắn. | Caller A không xem/hủy/tải tài nguyên của B. |
| S02 Retry/cancel | Retry transient error với backoff/jitter; cancellation cooperative, cleanup dữ liệu tạm. | Không retry `blocked_*`; job cancel không để orphan object. |
| S03 Audit trail | Ghi caller, action, policy decision, reason, trace ID, retention/redaction. | Truy vết được action mà không lộ secret. |

## 2. S04–S06: Khai thác document

1. **Document library:** list/filter/paginate, document/article metadata, dedupe, retention/delete theo authorization.
2. **Search stored data:** PostgreSQL full-text trước; thêm pgvector khi benchmark chứng minh cần thiết.
3. **RAG citation:** retrieve chunk theo quyền, LLM chỉ nhận context có `source_id`, validate toàn bộ citation ID trước response.
4. Article view dùng structured metadata của F01 khi có; không suy đoán author/time/content thiếu.

## 3. S07: Agent/MCP adapter

- Chỉ bắt đầu khi REST API, policy và audit đã ổn định.
- Tool read-only: search, get job, retrieve document, answer with citations.
- Tool side-effect: request crawl/media cần explicit approval/token, trả job ID ngay.
- Agent/MCP không có shell, direct DB, free network, raw HTML/network capture/cookie/token access.
- MCP resource authorization-aware; không expose presigned storage URL dài hạn.

## 4. S08: Dashboard và alert

- Dashboard job success/failure/duration/queue depth, blocked policy/DRM, bytes/storage/cost.
- Alert queue lag, error ratio, repeated policy block, disk quota, worker crash, storage failure.
- Mỗi alert có owner, severity, runbook và test/diễn tập định kỳ.

## 5. Test/DoD

- Authorization integration tests cho mọi resource type và object link TTL.
- Retry/cancel/audit tests; citation hallucination/unknown source bị loại.
- Agent/MCP contract test xác nhận tool chỉ có quyền dự kiến và side effect cần approval.
- Dashboard metric label không có URL/query/token/cardinality không kiểm soát.
- [ ] S01–S08 có API contract, audit event, test và documentation/runbook tương ứng.
