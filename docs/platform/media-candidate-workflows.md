# Media Candidate Workflows

> **Target workflow contract.** Đây là contract đích cho workflow ảnh/video. Repository hiện tại vẫn dùng layout đơn giản `app/services/`, `app/adapters/`, `app/workers/` và `app/api/`; chưa có `app/features/`. Hiện trạng từng feature được ghi trong tài liệu feature tương ứng.

Tài liệu này là nguồn duy nhất mô tả cách một URL trang trở thành media candidate, ai sở hữu candidate, và khi nào candidate trở thành download job. Nó không cho phép crawl tự động hoặc tự tải media.

## Workflow types

| Workflow | Input | Output | Ghi chú |
|---|---|---|---|
| `download_image` | Một URL ảnh trực tiếp hoặc manifest ảnh hữu hạn do caller cung cấp | `ImageManifest` | Direct URL workflow. |
| `extract_images` | Một URL trang | `Document` + `ImageCandidateManifest` → `ImageManifest` | Page-driven workflow; chỉ static evidence ở v1.1. |
| `download_video` | Một URL video/nguồn đã approved | `VideoAsset` | Direct URL workflow. |
| `extract_video` | Một URL trang/nguồn đã approved | `Document` reference + `VideoCandidateManifest` → `VideoAsset`/manifest | Page-driven workflow; recipe cố định, v1.2. |

Hai kiểu workflow có definition đăng ký riêng. Direct URL workflow không chạy discovery. Page-driven workflow không nhận selector, JavaScript, cookie hoặc credential từ request.

## Ownership

| Thành phần | Sở hữu | Không sở hữu |
|---|---|---|
| Crawl Data | `Document`, `document_type`, static parsing, `ImageCandidateManifest` | Download ảnh, chọn video candidate, quyết định DRM. |
| Image Download | Download execution, per-item policy/validation, `ImageManifest`, asset reference | Parse page HTML hoặc tự discovery candidate. |
| Video Download | `VideoCandidateManifest`, approved-source registry, recipe version, DRM/entitlement decision, `VideoAsset` | Crawl document chung hoặc tải torrent. |
| Workflow Orchestration | Step graph, selection rule, budget, fan-out/fan-in và aggregate result | Job lease/retry, network call hoặc feature execution. |

**Crawl Data owns `ImageCandidateManifest`** và static image parsing; **Image Download never parses page HTML** hoặc discovers candidates itself.

**Video Download owns `VideoCandidateManifest`** và approved-source recipe; **Crawl Data never selects video candidates** và không quyết định video có được tải hay không.

## Two-stage page workflow

Page workflow là **two-stage**:

```text
WorkflowRequest
  ├─ extract_images(page)
  │    → Crawl Data: Policy Gate → static fetch → Document
  │    → Crawl Data: ImageCandidateManifest (static evidence)
  │    → Workflow Orchestration: selection + budget
  │    → Image Download: ImageDownloadJob → ImageManifest
  │
  └─ extract_video(page/source)
       → Crawl Data (nếu chạy): Document reference
       → Video Download: approved recipe → VideoCandidateManifest
       → Workflow Orchestration: selection + budget
       → Video Download: VideoDownloadJob → VideoAsset/manifest
```

Stage 1 luôn persist `Document` khi Crawl Data chạy. Với `extract_images`, Crawl Data persists `Document` rồi `ImageCandidateManifest`. Với `extract_video`, Video Download persists `VideoCandidateManifest` sau approved recipe. Download job tương ứng thực thi sau selection/budget. Workflow result mang cả **`document_reference`** và media-manifest reference để audit/provenance.

Crawl Data, Image Download và Video Download không gọi nhau và không publish downstream job. **Only Workflow Orchestration may fan out** từ một candidate manifest.

## Candidate manifest

Candidate manifest là **durable evidence**, không phải list tạm:

- Giữ source page reference, candidate ID, ordered safe metadata và candidate URL chỉ trong durable feature record khi cần URL đó để thực thi.
- **Result events expose candidate IDs**, outcome/reason code và asset reference.
- Result events, UI-facing manifests và logs **never raw candidate URLs, cookies, authorization headers, signed URLs or browser capture**.
- URL có user-info hoặc credential bị từ chối. Signed URL hết hạn được feature sở hữu resolve lại lúc thực thi, không persist.
- Download job downstream tham chiếu manifest ID + selected candidate IDs, không nhận URL thay thế từ caller.
- Retention/delete theo source policy và storage contract; xóa manifest không để lại asset orphan có thể tải.

## Image workflow

1. Direct `download_image`: validate URL/manifest, policy gate từng URL, stream trong giới hạn per-item/total byte.
2. Page `extract_images`: Crawl Data trích static evidence (`img`, responsive sources, metadata được duyệt); Workflow Orchestration dedupe/select trong count/byte/time budget.
3. Mỗi candidate được Network Policy kiểm tra **trước** network call.
4. Validate declared MIME và magic bytes trước khi persist.
5. Persist checksum/size/MIME/object metadata qua asset storage; item outcome là `completed`, `failed` hoặc `blocked`.

Image Download không chạy browser lazy-load, không tự mở rộng page và không tải video.

## Video workflow

1. Direct `download_video`: một URL/nguồn đã approved.
2. Page `extract_video`: reviewed recipe trích static evidence (`video`, `source`, allowed Open Graph media, approved `.mp4`/`.m3u8` reference). Wait/click/capture chỉ thuộc v1.2.
3. Worker kiểm tra lại approved source, Network Policy, entitlement và DRM trước download.
4. **`.mp4`** là bounded stream.
5. **`.m3u8`** là playlist: chỉ parse cho approved source; segment/variant URL được policy-check và giới hạn; playlist encrypted/DRM/unsupported là terminal.
6. Không login, CAPTCHA, paywall hoặc geo-bypass. Không persist cookie, authorization header, signed URL hoặc raw capture.

## Torrent boundary

`.torrent` hoặc magnet link có thể được ghi thành safe candidate reference, nhưng Video Download không bao giờ tải nó. **Torrent Download is a separate deferred capability** vì peer, disk, bandwidth, file-count, legal/source và retention khác HTTP/HLS. `torrent_download` cần quyết định product/legal riêng, approved source, workflow/quota/audit riêng.

## Budgets and terminal outcomes

- Budget gồm candidate count, request count, bytes, time và concurrency; HLS thêm segment/playlist limit.
- `blocked_policy`, invalid MIME, quota, DRM, entitlement và unsupported playlist là terminal, không retry.
- Chỉ typed transient network/storage failure mới retry qua Queue Management.
- Direct và page workflow không được vượt quyền của caller hoặc approved source.

## Version roadmap

| Version | Workflow được phép | Loại trừ |
|---|---|---|
| MVP v1 | `search`, `crawl_url`, `search_and_extract`; static document classification | Media child job, browser action, recursive links, schedule |
| v1.1 | `download_image`, `extract_images` từ static page evidence với item/byte budget | Browser lazy-load, automatic page expansion |
| v1.2 | `download_video`, `extract_video` từ approved source; bounded `.mp4` và approved `.m3u8` | Login, paywall/CAPTCHA/geo bypass, request-provided browser input |
| Later | `torrent_download` chỉ sau quyết định riêng; bounded collection crawl xem xét riêng | Coi magnet/`.torrent` là video URL thông thường |

## Related docs

- [Search](../features/search.md)
- [Web Crawl](../features/web-crawl.md)
- [Image Download](../features/image-download.md)
- [Video Download](../features/video-download.md)
- [Workflow orchestration](workflow-orchestration.md)
- [Document classification](../document-classification.md)
- [Network policy](network-policy.md)
- [Storage](storage.md)
