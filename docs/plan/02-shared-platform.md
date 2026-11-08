# P01 — Shared Platform

> **Mục tiêu:** xây các capability dùng chung bắt buộc cho F01/F02/F03.  
> **Dependency:** P00.  
> **Đầu ra:** Policy Gate, job platform, queue/storage adapter và audit contract.

## 1. Yêu cầu

- Một Policy Gate duy nhất kiểm tra URL, DNS/IP, redirect, allowlist, quota, robots/quyền nội dung theo thao tác.
- Job lifecycle thống nhất: idempotency, status, progress, retry classification, cancellation và authorization.
- PostgreSQL cho transaction/metadata; MinIO cho object; Redis/Celery cho queue.
- Queue tách `crawl`, `media`, `torrent`, `maintenance`; mỗi queue có concurrency/time/memory quota riêng.
- Audit log ghi caller/action/decision/reason/trace nhưng không chứa secret hoặc raw URL query.

## 2. Thiết kế và thực hiện

| # | Hạng mục | Thực hiện | Acceptance |
|---|---|---|---|
| 1 | Domain enums | Định nghĩa job type/status, policy decision/reason, source status. | Không có state mơ hồ; transition hợp lệ được test. |
| 2 | Migrations | Tạo `jobs`, `audit_events`, base object metadata và index idempotency/status. | Upgrade/rollback trên DB test pass. |
| 3 | Policy Gate | Parse URL, resolve A/AAAA, chặn IP non-public, validate mỗi redirect, quota/domain policy. | URL blocked không tạo network request downstream. |
| 4 | Job service | Create/claim/update/cancel job atomic, idempotency key, visibility theo caller. | Request lặp lại không tạo job trùng. |
| 5 | Queue workers | Celery routes, time limits, retry policy, heartbeat/progress throttling. | Worker mock claim/complete/fail/cancel job. |
| 6 | Storage adapter | Object key server-side, upload/download/delete metadata, presigned access TTL. | Object không public, lỗi upload không đánh completed. |
| 7 | Audit/metrics | Audit event, trace ID, counter/histogram cho job state/queue. | Không có secret trong log/audit/metric label. |

## 3. API/service contracts

- `evaluate_policy(command) -> PolicyDecision`; phải gọi trước mọi adapter network.
- `create_job(command) -> Job`; chỉ tạo khi policy `allowed`.
- `get_job(job_id, caller)`, `cancel_job(job_id, caller)` và `list_jobs(filter, caller)` kiểm tra ownership.
- Worker nhận `job_id`, tự load job và policy context; không nhận URL/raw command trực tiếp từ queue message không xác thực.

## 4. Test plan

- Unit: policy scheme/IP/DNS/redirect, allowed/blocked transition, idempotency, retry classification.
- Integration: PostgreSQL transaction/unique index, Redis/Celery mock, MinIO fake/test bucket.
- Security: redirect private IP, DNS multi-record, stale/cancelled job, object authorization.

## 5. Risks và DoD

| Risk | Mitigation |
|---|---|
| SSRF/DNS rebinding | Validate DNS/IP/connection/redirect, egress restriction. |
| Orphan job/object | Transactional state + compensating cleanup task. |
| Retry gây duplicate | Idempotency key, atomic claim, checksum/hash. |

- [ ] Migrations, policy, job service và worker mock có test pass.
- [ ] F01/F02/F03 chỉ có một path tạo job/policy.
- [ ] Queue/object authorization, audit và cancellation được kiểm chứng.
