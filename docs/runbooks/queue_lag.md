# Runbook: Queue lag cao (`queue_lag_high`)

## Tóm tắt
Cảnh báo khi độ tuổi job/message của một feature queue vượt ngưỡng SLO. Queue cần
xác định rõ là `search.execute.v1`, `web-crawl.execute.v1`, `image.execute.v1` hoặc
`video.execute.v1`; không xử lý tất cả như một queue crawl chung.

## Bước khắc phục
1. Xác định feature queue, queue age/depth, consumer heartbeat và publish lag.
2. Kiểm tra Redis transport và outbox publisher; đối chiếu job `pending_publish`, `queued`, `running`, `retry_scheduled` trong PostgreSQL.
3. Kiểm tra lease hết hạn/reclaim và retry/DLQ count trước khi tăng consumer.
4. Scale hoặc restart **consumer của đúng feature** theo resource profile; không restart mọi worker.
5. Nếu có DLQ/publisher lag bất thường, preserve audit và theo runbook requeue đã được approval; không tự chạy lại job.

## Nâng cấp
Nếu queue age vẫn vượt SLO sau 30 phút hoặc consumer heartbeat mất, liên hệ owner: platform-team.

## Tài liệu tham khảo
- [Queue Management](../platform/queue-management.md)
- [Worker Architecture](../architecture/worker-crawler-rearchitecture.md)
