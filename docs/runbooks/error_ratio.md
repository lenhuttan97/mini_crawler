# Runbook: Tỷ lệ lỗi công việc cao (error_ratio_high)

## Tóm tắt
Cảnh báo khi tỷ lệ công việc thất bại vượt quá ngưỡng (5%). Có thể do nguồn
bị chặn chính sách, storage lỗi hoặc downloader lỗi.

## Bước khắc phục
1. Xem lỗi công việc gần đây trong bảng `jobs` và `audit_events`.
2. Kiểm tra mã lỗi: `blocked_policy` (không retry), `download_error`, `storage_error`.
3. Nếu là `blocked_policy`, xem lại source registry và Policy Gate.
4. Khởi động lại worker hàng đợi liên quan.

## Nâng cấp
Nếu tỷ lệ lỗi > 20% trong 15 phút, liên hệ owner: platform-team.

## Tài liệu tham khảo
- [Benchmark SLO](../plan/08-quality-security-release.md)
