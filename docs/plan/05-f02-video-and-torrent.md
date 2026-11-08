# P04 — F02: Video Page, Torrent/Magnet và Licensed RSS

> **Mục tiêu:** hoàn thiện F02 cho video page và torrent/magnet **từ nguồn được phép**.  
> **Dependency:** P03 Direct/Batch Media; P01 Shared Platform.

## 1. Source Registry và policy

| Trạng thái source | Hành vi |
|---|---|
| `approved` | Có bằng chứng quyền phân phối, allowlist domain/RSS/recipe, feature flag bật theo quota. |
| `pending_review` | Lưu đề nghị review, không discovery/download/network action. |
| `blocked` | Từ chối với reason code; không retry. |

- Không thêm nguồn chưa xác minh quyền phân phối.
- RSS chỉ discovery item từ source `approved`; caller phải chọn item trước khi tạo job.
- Không đăng nhập, giải CAPTCHA, bypass DRM/paywall/geo-blocking hoặc dùng credential/selector/JS do caller cung cấp.

## 2. F02.2 — Video page discovery

1. Tạo migration/source configuration cho domain, recipe version, timeout, max actions và expected state.
2. Policy Gate kiểm tra source/entitlement trước browser worker.
3. Browser context sandboxed, không chia sẻ session; recipe hữu hạn do server review/version control.
4. Network capture redaction trước persist; không lưu cookie, authorization header, signed URL/query token.
5. DRM/EME/`ContentProtection` hoặc policy violation → `blocked_drm`/`blocked_policy`, dừng ngay.
6. Adapter download/format chỉ nhận metadata đã qua gate; process không nhận shell argument từ caller.

## 3. F02.3/F02.4 — Torrent/magnet và RSS

1. Nhận magnet/torrent chỉ khi source registry là `approved`; validate identifier, metadata và quota trước enqueue.
2. RSS poller đọc endpoint approved theo lịch/ETag; normalise/dedupe item, không tự download.
3. Caller chọn item → tạo một media job có idempotency key và audit source decision.
4. Torrent worker cách ly khỏi mạng nội bộ/secret, có limits peers, bandwidth, disk, số file và thời gian.
5. Sau tải: kiểm tra loại/số lượng file, byte size, checksum nếu có, malware scanning theo môi trường; persist asset hợp lệ.
6. Cancellation/expiry dừng worker và cleanup dữ liệu tạm; không xóa audit record.

## 4. Test và acceptance

- Unit: source-state gate, recipe validation, DRM decision, RSS normalization/dedupe, torrent quota classification.
- Integration: browser fixture owned/allowed, fake torrent adapter, RSS fixture, process timeout/cancel, asset scan result.
- Security: pending/blocked source không gọi network; raw network capture/token không persist; caller input không thành selector/command.
- Done khi approved fixture hoàn tất job, DRM fixture bị blocked, RSS không tự enqueue download và quota/cancel hoạt động.

## 5. Risks/DoD

| Risk | Mitigation |
|---|---|
| Copyright/policy violation | Approved source registry, deny-by-default, audit và manual review. |
| Torrent resource abuse | Sandbox, network/disk/time/peer quota, queue riêng. |
| Browser/download exploit | Process isolation, fixed recipes/adapters, no caller shell/JS. |

- [ ] Source registry, feature flag và audit decision được implement/test.
- [ ] DRM/policy stop trước download; không có bypass path.
- [ ] Torrent/RSS chỉ chạy fixture/source approved, có cleanup/cancellation test.
