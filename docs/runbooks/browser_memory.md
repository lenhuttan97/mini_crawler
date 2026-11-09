# Runbook: Bộ nhớ trình duyệt cao (browser_memory_high)

## Tóm tắt
Cảnh báo khi bộ nhớ browser sandbox của `web-crawl.execute.v1` hoặc
`video.execute.v1` vượt ngưỡng cấu hình. Cần xác định feature, recipe/version và
worker instance trước khi can thiệp.

## Bước khắc phục
1. Kiểm tra browser process count, memory theo worker, current leases và job age.
2. Xác định Web Crawl fallback hay Video approved recipe gây tăng memory; không log URL/capture nhạy cảm.
3. Kiểm tra time/memory limit, sandbox cleanup và concurrency của **đúng feature queue**.
4. Drain/restart consumer feature có kiểm soát; lease hết hạn sẽ được Queue Management reclaim.
5. Giảm concurrency hoặc disable browser fallback/recipe qua feature flag nếu vượt giới hạn; không xóa job/audit.

## Nâng cấp
Nếu memory tiếp tục tăng sau một restart có kiểm soát, disable feature browser bị ảnh hưởng và liên hệ owner: platform-team.

## Tài liệu tham khảo
- [Web Crawl Worker](../features/web-crawl.md)
- [Video Download Worker](../features/video-download.md)
- [Queue Management](../platform/queue-management.md)
