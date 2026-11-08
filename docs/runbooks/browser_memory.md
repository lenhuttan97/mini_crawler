# Runbook: Bộ nhớ trình duyệt cao (browser_memory_high)

## Tóm tắt
Cảnh báo khi bộ nhớ trình duyệt (Playwright/Crawl4AI) vượt quá ngưỡng (2048 MB).
Có thể do tab mở quá nhiều hoặc rò rỉ bộ nhớ.

## Bước khắc phục
1. Khởi động lại worker chạy trình duyệt.
2. Kiểm tra giới hạn bộ nhớ trong cấu hình worker.
3. Giảm concurrency của hàng đợi trình duyệt nếu cần.

## Nâng cấp
Nếu bộ nhớ tiếp tục tăng sau khởi động lại, liên hệ owner: infra-team.

## Tài liệu tham khảo
- [Benchmark SLO](../plan/08-quality-security-release.md)
