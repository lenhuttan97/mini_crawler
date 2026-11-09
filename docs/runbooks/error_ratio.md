# Runbook: Tỷ lệ lỗi công việc cao (error_ratio_high)

## Tóm tắt
Cảnh báo khi failure ratio của một worker feature vượt ngưỡng cấu hình. Phân biệt
`failed`, `blocked_*`, `retry_scheduled` và `dead_lettered`; policy block không phải
transient worker failure.

## Bước khắc phục
1. Xác định feature queue và tách ratio theo completed/failed/blocked/retry/DLQ.
2. Kiểm tra durable job state, reason code, attempts, lease expiry, outbox lag và audit bằng correlation ID.
3. `blocked_policy`, `blocked_permission`, `blocked_drm`, validation và malformed command không retry; review policy/source/contract thay vì restart worker.
4. Với transient upstream/storage/broker error, kiểm tra retry schedule, provider health và resource quota trước khi scale/restart consumer feature.
5. Nếu DLQ tăng, dừng auto requeue, preserve evidence và dùng authorized requeue sau khi nguyên nhân được xử lý.

## Nâng cấp
Nếu transient failure ratio hoặc DLQ count vượt ngưỡng SLO trong 15 phút, liên hệ owner: platform-team; policy blocks được theo dõi riêng.

## Tài liệu tham khảo
- [Queue Management](../platform/queue-management.md)
- [Network Policy](../platform/network-policy.md)
