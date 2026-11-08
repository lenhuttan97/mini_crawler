# P03 — F02.1: Direct Media và Batch Image

> **Mục tiêu:** tải một media trực tiếp hoặc nhiều ảnh từ manifest/danh sách của nguồn `approved`.  
> **Dependency:** P01 Shared Platform.

## 1. Phạm vi

- F02.1: một URL ảnh/audio/video trực tiếp đã qua Policy Gate.
- F02.1a: danh sách/manifest ảnh; policy và trạng thái cho từng item.
- F02.1b: quota item/tổng byte/kích thước, MIME và magic-byte validation.
- F02.8: batch result manifest có sequence, status và reason code đã redaction.

Không nhận HTML page để tự quét ảnh trong phase này; đó là capability F01 hoặc video-page discovery riêng. Không tải từ source `pending_review`/`blocked`.

## 2. Data/API contract

| Thành phần | Chi tiết |
|---|---|
| Create media job | Input type `direct`/`image_batch`, URL hoặc danh sách item, idempotency key. |
| Media job item | sequence, requested/canonical URL, policy decision, status, asset ID/error code. |
| Batch result | tổng số, completed/failed/blocked, danh sách item có pagination. |
| Asset | object key, MIME, byte size, checksum, optional dimensions. |

## 3. Work breakdown

1. Migration `media_jobs`, `media_job_items`, `media_assets`, checksum/index/foreign key.
2. Validate manifest schema: max item count, không duplicate request URL, không nhận field script/header/cookie.
3. Tạo job/item atomically; apply quota caller/domain và policy từng item trước enqueue.
4. Media worker stream từng item với byte limit cả header `Content-Length` lẫn bytes thực tế.
5. Validate MIME + magic bytes; Pillow optional cho dimensions/ảnh lỗi; object key do server tạo.
6. Cập nhật item progress/status rate-limited; job tổng hợp `completed`/`failed`/`blocked`.
7. Hỗ trợ cancel giữa item; cleanup object lỗi/orphan bằng maintenance task.

## 4. Test và acceptance

- Unit: manifest validation, max quota, item dedupe, state aggregation, MIME/magic bytes.
- Integration: fake downloader/storage cho success, oversize, bad content, partial failure, duplicate checksum, cancel.
- Security: item blocked không tạo request; asset không public; response không lộ signed URL/token.
- Done khi 1 item fail/blocked vẫn giữ item thành công, sequence ổn định và tổng byte không vượt quota.

## 5. Rủi ro/DoD

| Risk | Mitigation |
|---|---|
| Batch cạn disk/bandwidth | Item/byte/concurrency quota, queue riêng, cancel. |
| File giả ảnh | MIME + magic bytes + optional Pillow validation. |
| Kết quả không nhất quán | Transaction cho item state, checksum/object cleanup. |

- [ ] Item-level policy/quota/status có test pass.
- [ ] Partial failure, cancellation và retry không tạo asset trùng.
- [ ] API trả batch manifest theo authorization/pagination.
