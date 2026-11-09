# Worker Release Sign-off

> Chỉ ký duyệt khi các worker feature được triển khai thực tế đã có bằng chứng kiểm thử và rollout. Đây không phải API release checklist.

## 1. Bảo mật

- [ ] Network Policy kiểm thử SSRF, DNS/redirect, allowlist, robots và quota cho feature áp dụng.
- [ ] Image kiểm tra từng URL; Video có approved source, entitlement và DRM gate.
- [ ] Browser/video process có sandbox, CPU/RAM/disk/time/network limits; không nhận credential, selector, JavaScript hay shell input từ job.
- [ ] Log, trace, outbox, DLQ và audit không chứa URL query, token, cookie, signed URL hoặc raw capture.

Owner: ____________________  Date: ___________  Signature: ____________

## 2. Sao lưu/phục hồi

- [ ] PostgreSQL job, lease, outbox, document/asset metadata backup và restore đã được kiểm thử.
- [ ] Object storage document/asset restore đã được kiểm thử.
- [ ] Restore drill xác minh không mất job state, audit hoặc result reference.

Owner: ____________________  Date: ___________  Signature: ____________

## 3. Benchmark và SLO

- [ ] Baseline được đo riêng cho Search, Web Crawl static/browser, Image batch và Video approved fixture.
- [ ] SLO được phê duyệt cho queue age, publish lag, execution duration, error ratio, retry/DLQ rate và browser memory.
- [ ] Concurrency, timeout và resource quota theo feature được benchmark và ghi nhận.

Owner: ____________________  Date: ___________  Signature: ____________

## 4. Queue, rollout và rollback

- [ ] Outbox/lease/retry/DLQ/cancellation được kiểm chứng với PostgreSQL + Redis/Celery thật.
- [ ] Feature queues có consumer heartbeat, metrics, alert và runbook.
- [ ] Rollback chỉ dừng feature consumer/flag; không xóa job, document, asset hoặc audit.
- [ ] Requeue DLQ cần authorization/audit; không tự replay job.

Owner: ____________________  Date: ___________  Signature: ____________

## 5. Feature readiness

- [ ] Search không auto-crawl.
- [ ] Web Crawl revalidates policy trước network/redirect và browser fallback được kiểm soát.
- [ ] Image có per-item quota, MIME/magic-byte validation và partial-result manifest.
- [ ] Video chỉ source approved; DRM/policy block là terminal; torrent ngoài scope nếu chưa phê duyệt riêng.
- [ ] Docs index, feature/platform contracts và runbooks được cập nhật.

Owner: ____________________  Date: ___________  Signature: ____________
