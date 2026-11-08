# Mini Crawler — Feature Roadmap

> Trạng thái: đề xuất tổ chức feature
> Phạm vi: MVP nhận URL/từ khóa từ người dùng, xử lý bất đồng bộ và chỉ làm việc với nội dung được phép.

## 1. Nguyên tắc tổ chức

- Ba feature sản phẩm bên dưới là luồng người dùng chính; không gộp chúng thành một endpoint đa mục đích.
- Mọi URL đều phải qua cùng một lớp policy: schema HTTP(S), SSRF/DNS/IP/redirect, domain allowlist, `robots.txt`, quyền nội dung và giới hạn tài nguyên.
- API chỉ tạo job và trả `job_id`; worker mới được gọi mạng, browser hoặc downloader.
- Không triển khai bypass DRM, paywall, CAPTCHA, geo-blocking, anti-bot hay kiểm soát truy cập.

## 2. Nền tảng dùng chung — bắt buộc trước feature chính

| Thành phần | Trách nhiệm | Dùng bởi |
|---|---|---|
| URL & Policy Gate | Kiểm tra URL, SSRF, redirect, allowlist, quyền và quota trước khi tạo job. | F01, F02, F03 |
| Job Platform | Tạo job, idempotency key, trạng thái, retry có chọn lọc, audit log và truy vấn trạng thái. | F01, F02, F03 |
| Worker & Queue | Celery/Redis tách tác vụ dài khỏi HTTP request. | F01, F02, F03 |
| Storage | PostgreSQL lưu metadata/trạng thái; MinIO lưu HTML/Markdown/media được phép. | F01, F02, F03 |
| Observability | Correlation ID, log đã redaction, metrics và trace. | F01, F02, F03 |

Các thành phần này là dependency kỹ thuật, không phải feature người dùng độc lập.

## 3. Ba feature chính

### F01 — Crawl data từ link người dùng cung cấp

**Mục tiêu:** người dùng gửi một URL được phép; hệ thống crawl và lưu nội dung chuẩn hóa để dùng lại.

**Luồng:**

```text
URL người dùng → Policy Gate → CrawlJob → worker
→ HTTPX (trang tĩnh) → fallback browser khi cần JavaScript
→ clean HTML/Markdown + metadata → PostgreSQL/MinIO → trạng thái job
```

**Kết quả tối thiểu:** `crawl_job_id`, trạng thái job, canonical URL, tiêu đề, Markdown và metadata an toàn.

**Không thuộc phạm vi:** deep crawl, crawl toàn bộ domain, đăng nhập tự động hoặc thực thi action/JavaScript do người dùng hoặc LLM cung cấp.

### F02 — Download video từ link người dùng cung cấp

**Mục tiêu:** người dùng yêu cầu tải media/video từ URL mà họ sở hữu hoặc có quyền tải; hệ thống xử lý trong worker và lưu asset được phép.

**Luồng:**

```text
URL media/trang video → Policy + quyền nội dung + DRM gate
→ MediaDownloadJob → media worker
→ metadata/discovery đã review (nếu cần) → yt-dlp/FFmpeg
→ MinIO + metadata → trạng thái job
```

**Kết quả tối thiểu:** `media_job_id`, trạng thái/progress, MIME type, byte size và object metadata; URL lưu trữ chỉ được cấp ngắn hạn cho caller được phép.

**Quy tắc bắt buộc:** phát hiện DRM thì chuyển `blocked_drm` và dừng; không đăng nhập, không giải CAPTCHA, không vượt paywall/geo-blocking. Nếu cần browser, chỉ chạy recipe cố định theo domain đã review.

#### Ba luồng download chính của F02

| Luồng | Input | Xử lý | Kết quả |
|---|---|---|---|
| F02.1 — Direct media & batch image | Một URL media hoặc danh sách/manifest ảnh từ nguồn được phép | Policy gate cho từng URL → giới hạn số ảnh/tổng dung lượng → kiểm tra MIME/magic bytes → download worker | Asset trong object storage và trạng thái từng item |
| F02.2 — Video page | URL trang video được phép | Policy gate → discovery recipe đã review → DRM gate → yt-dlp/FFmpeg worker | Asset hoặc trạng thái `blocked_*` |
| F02.3 — Torrent/magnet | Torrent file hoặc magnet link từ nguồn được phép | Policy gate → xác minh nguồn/quyền → torrent worker bị quota → kiểm tra tệp sau tải | Asset hợp lệ hoặc trạng thái bị chặn/lỗi |

**F02.3 là luồng chính, không phải shortcut để bỏ qua chính sách.** RSS chỉ là một nguồn discovery tùy chọn cho torrent đã được cấp phép và đã cấu hình allowlist. Không tích hợp Nyaa hoặc nguồn không xác minh quyền phân phối; hệ thống không dùng torrent để tải nội dung có bản quyền khi chưa có quyền rõ ràng.

### F03 — Search rồi crawl data

**Mục tiêu:** người dùng gửi từ khóa, xem kết quả tìm kiếm đã chuẩn hóa, rồi chọn rõ URL nào cần crawl.

**Luồng:**

```text
Query → Search service/SearXNG → danh sách URL đã chuẩn hóa
→ người dùng chọn URL → F01 Crawl data
```

**Quyết định quan trọng:** search **không** tự crawl toàn bộ kết quả. Mỗi URL được chọn vẫn phải qua Policy Gate và tạo `CrawlJob` riêng của F01.

**Kết quả tối thiểu:** danh sách title/URL/snippet có phân trang hoặc giới hạn; request crawl sử dụng lại F01, không có pipeline crawl thứ hai.

## 4. Catalog feature phụ

Các mã bên dưới là catalog trong phạm vi Mini Crawler; một feature phụ chỉ được triển khai khi feature chính và dependency của nó đã ổn định.

### 4.1 Feature phụ của F01 — Crawl data từ URL

| Mã | Feature phụ | Mô tả ngắn | Dependency |
|---|---|---|---|
| F01.1 | Submit crawl request | Nhận một URL, idempotency key và tạo `CrawlJob`. | URL & Policy Gate, Job Platform |
| F01.2 | URL safety validation | Kiểm tra scheme, DNS/IP, port, redirect, quota và allowlist trước mỗi request. | URL & Policy Gate |
| F01.3 | Static fetch | Lấy HTML bằng HTTPX streaming, timeout và giới hạn kích thước. | F01.2 |
| F01.4 | JavaScript fallback | Chạy browser/Crawl4AI chỉ khi static fetch không đủ nội dung. | F01.2, Worker & Queue |
| F01.5 | Content normalization | Loại phần không cần thiết, tạo clean HTML/Markdown, canonical URL và content hash. | F01.3 hoặc F01.4 |
| F01.5a | Document type classification | Gán một loại tài liệu chính từ HTML/JSON metadata và DOM; caller hint chỉ là tín hiệu; lưu confidence, reason và `needs_review` khi không chắc. MVP chỉ xuất HTML/JSON thành Markdown. | F01.5 |
| F01.6 | Document persistence | Lưu metadata/chỉ mục trong PostgreSQL và raw/Markdown trong MinIO. | F01.5, Storage |
| F01.7 | Crawl job status | Xem trạng thái, lỗi đã redaction, retry policy và hủy job khi hỗ trợ. | Job Platform |

### 4.2 Feature phụ của F02 — Download video/media

| Mã | Feature phụ | Mô tả ngắn | Dependency |
|---|---|---|---|
| F02.1 | Direct media download | Tải một ảnh/audio/video trực tiếp từ URL đã được policy cho phép. | URL & Policy Gate, Worker & Queue |
| F02.1a | Batch image download | Tải danh sách/manifest ảnh từ nguồn được phép; kiểm tra policy cho từng URL, deduplicate và ghi trạng thái từng ảnh. | F02.1, Job Platform |
| F02.1b | Batch quota & validation | Giới hạn số item, tổng byte, kích thước mỗi ảnh; kiểm tra MIME/magic bytes trước persist. | F02.1a, Policy Gate |
| F02.2 | Video-page discovery | Dùng recipe cố định để phát hiện metadata/media từ trang video được phép. | URL & Policy Gate, browser worker |
| F02.3 | Torrent/magnet download | Nhận torrent/magnet từ nguồn được phép; chạy torrent client trong worker có quota. | URL & Policy Gate, torrent worker |
| F02.4 | Licensed RSS discovery | Đọc RSS từ nguồn đã allowlist để đề xuất torrent/media; người dùng vẫn phải chọn item. | F02.3, RSS source policy |
| F02.5 | DRM & entitlement gate | Chặn DRM, thiếu quyền nội dung hoặc điều khoản không cho phép download. | Policy Gate |
| F02.6 | Format processing | Dùng yt-dlp/FFmpeg cho luồng được phép, xác minh MIME/magic bytes và giới hạn dung lượng. | F02.1/F02.2/F02.3 |
| F02.7 | Media asset management | Lưu metadata, checksum, progress, lỗi và cấp URL truy cập ngắn hạn theo quyền. | Storage, Job Platform |
| F02.8 | Batch result manifest | Trả danh sách item thành công/thất bại/blocked, thứ tự ảnh và lý do đã redaction. | F02.1a, F02.7 |

### 4.3 Feature phụ của F03 — Search rồi crawl

| Mã | Feature phụ | Mô tả ngắn | Dependency |
|---|---|---|---|
| F03.1 | Search query validation | Giới hạn query, page/limit và rate limit cho yêu cầu tìm kiếm. | API foundation |
| F03.2 | Search provider adapter | Gọi SearXNG, timeout và xử lý lỗi upstream. | F03.1 |
| F03.3 | Result normalization | Chuẩn hóa title/URL/snippet, loại trùng và chỉ trả dữ liệu an toàn. | F03.2 |
| F03.4 | Selected-result crawl | Người dùng chọn từng URL; chuyển sang F01.1, không tạo crawler riêng. | F01.1, F03.3 |
| F03.5 | Search history | Lưu lịch sử query theo quyền/retention policy, không lưu secret. | Storage, authorization |

### 4.4 Feature phụ dùng chung sau MVP

| Mã | Feature phụ | Giá trị | Dependency |
|---|---|---|---|
| S01 | Authorization & tenant boundary | Chỉ caller được phép mới xem/tạo job và asset. | API foundation |
| S02 | Job retry/cancel | Retry lỗi tạm thời, hủy job an toàn và không retry lỗi policy. | Job Platform |
| S03 | Audit trail | Lưu caller, policy decision, action và thời điểm mà không log secret. | S01, Observability |
| S04 | Document library | Duyệt, lọc, deduplicate và xem tài liệu đã crawl. | F01.6 |
| S05 | Search dữ liệu đã lưu | Full-text/vector search trên corpus nội bộ. | S04, PostgreSQL/pgvector |
| S06 | RAG với citation | Trả lời dựa trên source đã lưu, kiểm tra citation trước phản hồi. | S05 |
| S07 | Agent/MCP adapter | Tool quyền tối thiểu; mọi side effect vẫn cần approval. | S01, S03, F01–F03 ổn định |
| S08 | Dashboard & alert | Quan sát queue, quota, lỗi, chi phí và độ tin cậy. | Observability |

## 5. Thứ tự triển khai đề xuất

| Giai đoạn | Deliverable | Lý do |
|---|---|---|
| 0 | Foundation: API, policy gate, job platform, worker, storage và observability tối thiểu | Ba feature cần cùng một nền tảng an toàn. |
| 1 | F01 — Crawl URL | Tạo pipeline nội dung chuẩn và kiểm chứng policy/job/storage trước. |
| 2 | F02 — Download video/media | Tái sử dụng policy, queue, status và storage của F01; thêm DRM/quyền nội dung gate. |
| 3 | F03 — Search rồi chọn crawl | Tái sử dụng toàn bộ F01; chỉ thêm discovery URL qua SearXNG. |

## 6. Nhóm feature đề xuất sau ba feature chính

| Ưu tiên | Feature | Dependency | Giá trị |
|---|---|---|---|
| P1 | Theo dõi, retry và hủy job | Job Platform | Người dùng biết job đang làm gì và có thể xử lý lỗi an toàn. |
| P1 | Thư viện tài liệu đã crawl | F01 + Storage | Xem, lọc, loại trùng và tải lại Markdown/metadata theo quyền. |
| P1 | Quản lý media asset | F02 + Storage | Xem progress, lỗi policy/DRM và cấp quyền tải asset ngắn hạn. |
| P2 | Tìm kiếm trong dữ liệu đã lưu | F01 + PostgreSQL full-text/pgvector | Tìm lại tài liệu nội bộ mà không crawl lại web. |
| P2 | Trả lời RAG có citation | Thư viện tài liệu + search nội bộ | Câu trả lời chỉ dựa trên source đã lưu và kiểm tra citation. |
| P3 | Agent/MCP adapter | REST API, policy, audit ổn định | Cho AI client gọi tool giới hạn quyền; side effect vẫn cần approval. |
| P3 | Dashboard/alert vận hành | Observability | Theo dõi quota, queue depth, lỗi upstream, chi phí và độ tin cậy. |

## 7. Ranh giới MVP

- F01/F02/F03 chỉ hỗ trợ request đơn lẻ, có quota và trạng thái rõ ràng.
- Không auto-crawl mọi kết quả tìm kiếm hoặc mọi link xuất hiện trong trang.
- Không nhận cookie, token, selector hay JavaScript tùy ý từ người dùng/LLM.
- Không public object storage; mọi asset cần authorization trước khi cấp quyền truy cập.

## 8. Tài liệu liên quan

- [Kế hoạch kỹ thuật chi tiết](mini_crawler_implementation_plan.md)
- [Lộ trình học](learning/README.md)
