# Queue Management

## Scope

`queue_management` là platform của worker repository. Nó giao job delivery; không thực thi Search, Web Crawl, Image hoặc Video business logic.

Nó nhận outbox event đã được `job_orchestration` commit. `workflow_orchestration` chỉ tạo `JobIntent`; chỉ Job Orchestration được tạo `FeatureJob`. Queue Management không đọc workflow graph, không diễn giải command và không tự tạo job downstream.

## Source of truth

- PostgreSQL lưu job state, attempts, leases, outbox events và audit.
- Redis/Celery chỉ vận chuyển message; delivery là **at-least-once**, không phải exactly-once.
- Message chỉ chứa `job_id`, `feature_code`, `contract_version`, `correlation_id`; payload được load từ durable store.

## Queues

| Queue | Consumer | Purpose |
|---|---|---|
| `search.execute.v1` | Search worker | Provider discovery job |
| `web-crawl.execute.v1` | Web Crawl worker | Website crawl job |
| `image.execute.v1` | Image worker | Direct/batch image job |
| `video.execute.v1` | Video worker | Approved video job |
| `worker.maintenance.v1` | Maintenance worker | Outbox publish, retry scheduling, expired-lease reclaim |
| `<feature>.dlq.v1` | Không auto-consume | Job exhausted hoặc failure cần điều tra |

Mỗi execution queue có concurrency, soft/hard timeout và quota riêng. Không có generic `media` queue và không có torrent queue trong scope hiện tại.

## Delivery lifecycle

```text
pending_publish → queued → running → completed
                         ├→ retry_scheduled → queued
                         ├→ failed → dead_lettered
                         ├→ blocked_*
                         └→ cancelled
```

1. Producer tạo feature job và outbox event trong cùng transaction.
2. Maintenance publisher đưa event vào đúng feature queue.
3. Consumer atomically acquire lease trước execution; job đã terminal/cancelled không chạy.
4. Feature service trả typed result/error; Job Orchestration commit state/result trước khi Queue Management acknowledge message.
5. Lease heartbeat/progress được rate-limit. Job hết lease chỉ được maintenance worker reclaim khi không terminal.

## Handoff với orchestration

1. `WorkflowOrchestrator` (hoặc producer được phép) tạo `JobIntent` cho một workflow step.
2. `JobOrchestrationService` persist atomically `FeatureJob`, typed command và request outbox event.
3. Queue Management publisher claim outbox rồi gửi safe delivery message tới feature queue.
4. Worker acquire lease, load command durable, gọi feature service và trả typed `ExecutionOutcome`.
5. Job Orchestration commit outcome/result outbox; Workflow Orchestration quan sát result reference để tiếp tục hoặc kết thúc step.

Không component nào trong chuỗi trên gọi trực tiếp feature service khác. Queue Management chỉ retry typed transient outcome; policy/DRM/entitlement/validation/cancellation là terminal.

## Retry, cancellation, DLQ

- Retry chỉ áp dụng cho typed transient error: provider/upstream timeout, temporary storage/broker failure hoặc rate limit có retry semantics.
- Validation, policy, DRM, entitlement, malformed command và cancellation không retry.
- Retry dùng bounded exponential backoff + jitter, lưu `next_run_at` trong database; maintenance worker mới publish lại.
- Sau `max_attempts`, job thành `dead_lettered`, lưu reason/audit và phát event tới feature DLQ.
- Requeue DLQ cần authorization/approval, tạo delivery attempt mới và giữ liên kết audit.
- Cancel là cooperative: trạng thái `cancellation_requested`, feature service kiểm tra checkpoint; message đến sau cancel được acknowledge mà không thực thi.

## Required ports

```text
QueuePublisher.publish(message)
JobLeaseStore.acquire(job_id, worker_id, now)
JobLeaseStore.heartbeat(lease_id, progress, now)
JobLeaseStore.finish(lease_id, outcome)
OutboxStore.claim_pending(now)
OutboxStore.mark_published(event_id)
```

## Operations and tests

Metrics: queue depth/age, publish lag, running leases, reclaim count, retry count/age, DLQ count/age, cancellation latency, consumer heartbeat and feature duration/error ratio.

Test mandatory: concurrent lease acquisition, outbox redelivery, crash before/after commit, expired lease reclaim, retry classification/scheduling, DLQ requeue authorization and cancellation checkpoints.
