# P07–P08 — Quality, Security và Release

> **Mục tiêu:** harden toàn bộ feature, đo được chất lượng và rollout có kiểm soát.  
> **Dependency:** P00–P06.

## 1. Quality strategy

| Tầng | Phạm vi | Quy tắc |
|---|---|---|
| Unit | policy, state machine, normalizer, quota, mapper | Không gọi mạng/dịch vụ thật. |
| Integration | DB migration, queue, storage, HTTP adapter mock | Fixture do team kiểm soát. |
| E2E | F01/F02/F03 happy/error path | Source/website/media hợp pháp, approved. |
| Regression | security failures, partial batch, retry/cancel, permission | Mỗi bug có test ngăn tái diễn. |

- Mọi feature theo TDD Red → Green → Refactor.
- Coverage theo changed code; ưu tiên branch policy/state/error path.
- CI bắt buộc lint, format, dependency/secret scan, unit/integration test trước merge.

## 2. Security hardening

1. SSRF test matrix: scheme, user-info, IPv4/IPv6/private/link-local, DNS multi-record/rebinding, redirect chain, port policy.
2. Process/network isolation cho browser, downloader, FFmpeg và torrent worker; set CPU/RAM/disk/time/network limits.
3. Authorization test matrix caller/tenant/resource; object storage private và presigned URL TTL/permission.
4. Log/trace/audit redaction test; no raw network payload, token, cookie, signed URL, secret or high-cardinality URL label.
5. Source registry review process: evidence quyền phân phối, owner, expiry/review date, feature flag; deny-by-default.

## 3. Benchmark và reliability

- Benchmark fixture static article, JavaScript article, direct media, batch image và approved media/torrent sample.
- Đo queue delay, job duration, failure/retry ratio, browser memory, download bytes, storage growth và cost.
- Thiết lập threshold theo dữ liệu baseline; chỉ thêm pgvector/search scale-out khi benchmark chứng minh nhu cầu.
- Load test API metadata/job-status, không load test upstream public website.

## 4. Operations và recovery

| Hạng mục | Plan | Bằng chứng |
|---|---|---|
| Monitoring | Dashboard metrics/trace/log alert theo S08. | Alert test và runbook link. |
| Backup | PostgreSQL dump/PITR policy, MinIO version/backup policy. | Restore drill định kỳ. |
| Incident | Severity, owner, disable feature flag/consumer, preserve audit. | Tabletop exercise. |
| Retention | Document/media/audit/history expiry và deletion workflow. | Deletion test/audit record. |

## 5. Rollout và rollback

1. Staging với fixtures controlled; chạy migration forward/backward compatibility check.
2. Rollout P00/P01 rồi F01 allowlist hẹp; quan sát metrics/error/security blocks.
3. Bật F02 direct/batch trước; video/torrent chỉ source `approved`, feature flag độc lập.
4. Bật F03 sau khi F01 ổn định; xác nhận không auto-crawl.
5. Bật feature phụ/AI adapter theo review, benchmark và authorization audit.
6. Rollback bằng disable feature flag/queue consumer trước; không xóa data/audit; migration rollback chỉ sau kiểm chứng data compatibility.

## 6. Release gate / Definition of Done

- [ ] P00–P06 status `Done` trong `plan/INDEX.md`, có link evidence test/review.
- [ ] Security review sign-off: SSRF, source policy, auth, redaction, process isolation.
- [ ] Migration/backup/restore drill pass; runbook/alert owner xác định.
- [ ] Benchmark baseline và SLO/threshold được phê duyệt.
- [ ] No critical/high unresolved issue; feature flag và rollback đã diễn tập.
- [ ] API/docs/changelog/user-facing limitation cập nhật đầy đủ.
