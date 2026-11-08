# Runbook: Queue lag cao (queue_lag_high)

## Tóm tắt
Cảnh báo khi độ trễ hàng đợi crawl vượt quá ngưỡng SLO (60 giây). Có thể do worker
không đủ, broker Redis quá tải hoặc task bị treo.

## Bước khắc phục
1. Kiểm tra sức khỏe Redis: `redis-cli ping`.
2. Xem số lượng công việc đang pending/queued trong PostgreSQL.
3. Khởi động lại consumer worker hàng đợi `crawl`.
4. Nếu vẫn không hồi phục, kiểm tra log worker để tìm lỗi nhưng không khôi phục.

## Nâng cấp
Nếu không khôi phục trong 30 phút, liên hệ owner: platform-team.

## Tài liệu tham khảo
- [Benchmark SLO](../plan/08-quality-security-release.md)
- Dashboard hàng đợi (P06 S08)
