# 04 — Phát hiện và tải ảnh/video/audio được phép

> **Status: version-gated.** `extract_images` thuộc v1.1; `extract_video` thuộc v1.2. HTTP/policy/validation concepts dùng được ngay, nhưng Playwright, Crawl4AI, yt-dlp, FFmpeg và Pillow chưa là dependency hiện tại. Chỉ thêm chúng cùng reviewed source/recipe, sandbox, quota và controlled fixtures.

> Học phần này dạy bạn cách phát hiện liên kết ảnh, video, âm thanh trong trang web, kiểm tra chính sách trước khi tải, và xử lý trường hợp link media chỉ xuất hiện sau khi tương tác với trình phát video. Tất cả chỉ áp dụng đối với nội dung bạn sở hữu hoặc được phép truy cập.

---

## Mục tiêu của học phần

- Hiểu tại sao link ảnh/video có thể ẩn trong HTML hoặc chỉ xuất hiện sau khi nhấn Play.
- Dùng HTTPX để tải ảnh trực tiếp và kiểm tra loại tệp (MIME, magic bytes).
- Dùng Pillow để đọc thông tin ảnh và tạo ảnh thu nhỏ (tùy chọn).
- Dùng Playwright và Crawl4AI để phát hiện link video ẩn qua phản hồi mạng.
- Dùng yt-dlp và FFmpeg để tải video/audio từ nguồn được phép.
- Áp dụng gate chính sách, chặn DRM và không vượt kiểm soát truy cập.
- Viết test mà không gọi mạng thật và không tải media bên ngoài trong test đơn vị.

---

## Lộ trình năng lực trong bài này

| Mức | Bạn tập trung vào | Khi nào nên đi tiếp? |
|-----|-------------------|----------------------|
| Beginner | Tải một ảnh bạn sở hữu bằng streaming và xác thực loại/kích thước tệp. | Bạn luôn áp dụng policy trước khi tạo download job. |
| Intermediate | Dùng Pillow, Playwright trên trang demo và mock network capture. | Bạn không log cookie, token hay URL ký. |
| Advanced | Thiết kế recipe cố định, trạng thái `blocked_*` và worker tách biệt. | Bạn xử lý lỗi, retry và hạn mức mà không vượt quyền truy cập. |
| Master | Vận hành pipeline media được phép với kiểm toán, dung lượng và chi phí lưu trữ. | Bạn review quyền nội dung và rủi ro trước mọi thay đổi automation. |

Không dùng các ví dụ dưới đây để truy cập nội dung không được phép hoặc để vượt DRM, paywall, CAPTCHA hay geo-blocking.

---

## 1. Tổng quan: hai loại nguồn media

Trước khi đi vào công cụ, hãy phân biệt hai workflow:

| Workflow | Input | Ai discovery | Download |
|---|---|---|---|
| Direct URL | Một URL ảnh/video đã approved | Không có bước discovery | Feature tải trực tiếp sau policy/validation |
| Page URL | Một URL trang | `extract_images` do Crawl Data trích static image evidence; `extract_video` do Video Download chạy approved recipe | Workflow chọn candidate trong budget rồi tạo download job |

Page URL workflow là two-stage: Crawl Data persist `Document` trước; với ảnh, Crawl Data persist `ImageCandidateManifest`, còn với video, Video Download persist `VideoCandidateManifest` sau approved recipe. Workflow chọn candidate trong budget rồi tạo download job; result mang cả document và manifest reference. `.m3u8` là playlist HLS, không phải file `.mp4`; torrent/magnet là capability riêng, deferred, không thuộc Video Download. Contract đầy đủ ở [media candidate workflows](../platform/media-candidate-workflows.md).

Trong trang web, media có thể xuất hiện theo hai cách:

| Loại | Nguyên nhân | Công nghệ đề xuất |
|------|-------------|-------------------|
| Media lộ ngay trong HTML | Thẻ `img`, `video/source`, metadata Open Graph | HTTPX trực tiếp |
| Media chỉ xuất hiện sau tương tác | JavaScript khởi tạo trình phát, nhấn nút Play, iframe | Playwright + Crawl4AI capture mạng |

Luồng xử lý chung:

```
Trang web đã crawl
     │
     ▼
Phát hiện liên kết media (MediaLinkDiscoveryService)
     │
     ▼
Kiểm tra chính sách (domain, loại tệp, dung lượng, quyền truy cập)
     │
     ├─ Ảnh → HTTPX streaming → kiểm tra MIME/magic bytes → Pillow (tùy chọn) → MinIO
     │
     └─ Video/âm thanh → (nếu cần) Playwright action recipe → phát hiện .m3u8/.mpd/media
                         → gate DRM/chính sách → yt-dlp/FFmpeg worker → MinIO
```

---

## 2. HTTPX — tải tệp trực tiếp an toàn

### 2.1 HTTPX là gì?

HTTPX là thư viện Python gọi HTTP không đồng bộ. Ngoài việc lấy trang HTML, bạn cũng có thể dùng nó để tải ảnh hoặc tệp media nhỏ từ URL đã được phép.

### 2.2 Tải ảnh bằng streaming

```python
import httpx

MAX_IMAGE_BYTES = 5 * 1024 * 1024

async def download_image(url: str, destination: str):
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_IMAGE_BYTES:
                raise ValueError("Image is too large")

            downloaded = 0
            with open(destination, "wb") as f:
                async for chunk in response.aiter_bytes():
                    downloaded += len(chunk)
                    if downloaded > MAX_IMAGE_BYTES:
                        raise ValueError("Image is too large")
                    f.write(chunk)
```

### 2.3 Kiểm tra trước khi lưu

Không nên tin phần mở rộng của URL (ví dụ `.jpg` có thể chứa script). Hãy kiểm tra:

1. `Content-Type` từ phản hồi HTTP.
2. Magic bytes (dấu hiệu đầu tệp) của nội dung thực tế.
3. Kích thước tệp không vượt quá giới hạn cho phép.
4. URL đã qua kiểm tra SSRF và domain allowlist.

Ví dụ kiểm tra MIME đơn giản:

```python
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/avif"}

def is_allowed_image(content_type: str | None) -> bool:
    return content_type in ALLOWED_IMAGE_MIME if content_type else False
```

---

## 3. Pillow — xử lý ảnh cơ bản (tùy chọn)

### 3.1 Pillow là gì?

Pillow là thư viện Python xử lý ảnh. Trong dự án, bạn chỉ dùng Pillow ở worker nền để:

- Đọc kích thước ảnh (chiều rộng, chiều cao).
- Phát hiện ảnh lỗi hoặc không hợp lệ.
- Tạo ảnh thu nhỏ (thumbnail) nếu cần.

Không dùng Pillow trong xử lý API trực tiếp vì việc xử lý ảnh có thể tốn thời gian và bộ nhớ.

### 3.2 Ví đọc thông tin ảnh

```python
from PIL import Image

with Image.open("hinh-anh.jpg") as img:
    print(img.size)      # (chiều rộng, chiều cao)
    print(img.format)    # JPEG, PNG, ...
```

---

## 4. Playwright — điều khiển trình duyệt cho trang cần JavaScript

### 4.1 Tại sao cần Playwright?

Một số trang web không đưa link video vào HTML ban đầu. Link `.m3u8` (luồng video HLS), `.mpd` (luồng DASH) hoặc file video trực tiếp chỉ xuất hiện sau khi:

- Trình phát video khởi tạo.
- Người dùng nhấn nút Play.
- Iframe con được tải xong.

HTTPX không chạy JavaScript, nên bạn cần Playwright để điều khiển trình duyệt thực sự.

### 4.2 Chạy Playwright

```bash
uv add playwright
uv run playwright install chromium
```

### 4.3 Ví dụ mở trang và chờ trình phát

```python
from playwright.async_api import async_playwright

async def open_video_page(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=30000)

        # Chờ phần tử trình phát xuất hiện
        await page.wait_for_selector("video", timeout=10000)

        await browser.close()
```

### 4.4 Action recipe an toàn (đã review)

Đối với mỗi trang video được phép, bạn tạo một "recipe" (công thức hành động) đã được kiểm tra trong mã nguồn. Ví dụ:

```
wait_for(trình phát) → chọn iframe (nếu cần) → nhấn nút Play → chờ phản hồi mạng chứa .m3u8/.mpd
```

Quy tắc quan trọng:

- Không nhận selector hoặc JavaScript do người dùng/LLM truyền vào.
- Không tự động đăng nhập, điền thanh toán, giải CAPTCHA hay bấm đồng ý bất thường.
- Chỉ chạy trên domain được phép trong allowlist.
- Giới hạn số bước hành động và thời gian chờ để tránh vòng lặp vô hạn.

---

## 5. Crawl4AI network capture — theo dõi phản hồi mạng

### 5.1 Crawl4AI có thể làm gì ngoài cào trang?

Ngoài việc xuất Markdown, Crawl4AI có thể ghi lại các yêu cầu và phản hồi mạng xảy ra khi trình duyệt tải trang. Điều này hữu ích để tìm link video ẩn.

### 5.2 Bật ghi lại phản hồi mạng

```python
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

config = CrawlerRunConfig(
    capture_network_requests=True,
    cache_mode=CacheMode.BYPASS,
)

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun("https://trang-video.com", config=config)

    if result.network_requests:
        for req in result.network_requests:
            if req.get("event_type") == "response":
                url = req.get("url", "")
                if ".m3u8" in url or ".mpd" in url:
                    print("Phát hiện luồng media:", url)
```

### 5.3 Bảo mật khi lưu phản hồi mạng

- Không lưu hay log cookie, header `Authorization`, hoặc token ký trong URL.
- Loại bỏ thông tin nhạy cảm trước khi lưu vào database hoặc file log.

---

## 6. yt-dlp — trích xuất và tải video/audio

### 6.1 yt-dlp là gì?

yt-dlp là công cụ Python hỗ trợ trích xuất metadata và tải video/âm thanh từ các nguồn mà bạn có quyền sử dụng. Nó không cấp quyền truy cập, không thay thế điều khoản dịch vụ và không được dùng để vượt cơ chế bảo vệ.

### 6.2 Tại sao không tự viết trình tải video?

Việc phân tích trang YouTube, TikTok, Vimeo… rất phức tạp và thay đổi liên tục. yt-dlp đã được cộng đồng duy trì cập nhật, nên bạn nên dùng thư viện này thay vì tự viết từ đầu.

### 6.3 Cài yt-dlp

```bash
uv add yt-dlp
```

Cần cài FFmpeg riêng (xem phần sau).

### 6.4 Ví dụ trích xuất thông tin mà không tải

```python
import yt_dlp

ydl_opts = {}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://example.com/video", download=False)
    info_safe = ydl.sanitize_info(info)
    print(info_safe.get("title"))
    print(info_safe.get("duration"))
```

### 6.5 Ví dụ tải video

```python
ydl_opts = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": "%(title)s.%(ext)s",
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(["https://example.com/video"])
```

### 6.6 Theo dõi tiến độ

```python
def progress_hook(d):
    if d["status"] == "finished":
        print("Tải xong, đang xử lý sau khi tải...")

ydl_opts = {
    "progress_hooks": [progress_hook],
}
```

Trong dự án, tiến độ này được lưu vào trạng thái công việc (job) trong database, không in ra màn hình API.

---

## 7. FFmpeg — ghép và chuyển đổi media

### 7.1 FFmpeg là gì?

FFmpeg là công cụ dòng lệnh xử lý video và âm thanh. yt-dlp thường dùng FFmpeg để:

- Ghép video và âm thanh riêng thành một tệp.
- Chuyển đổi định dạng (ví dụ từ WebM sang MP4).
- Cắt tệp hoặc trích xuất âm thanh.

### 7.2 Cài FFmpeg

FFmpeg không phải thư viện Python, bạn phải cài đặt riêng trên hệ thống:

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: tải từ trang chủ ffmpeg.org

Kiểm tra đã cài chưa:

```bash
ffmpeg -version
```

---

## 8. Gate chính sách và DRM

### 8.1 Trước khi tải, bạn phải kiểm tra

1. Domain nằm trong danh sách cho phép (allowlist).
2. Loại tệp và kích thước phù hợp với chính sách.
3. Người dùng có quyền truy cập nội dung này hay không.
4. Không phải nội dung bị bảo vệ bằng DRM.

### 8.2 Chặn DRM

Nếu phát hiện dấu hiệu DRM (ví dụ: `ContentProtection` trong DASH, EME trong trình duyệt), hãy đánh dấu trạng thái `blocked_drm` và dừng. Không thử giải mã, bypass DRM, paywall, CAPTCHA hay geo-blocking.

### 8.3 Trạng thái công việc media

| Trạng thái | Ý nghĩa |
|------------|---------|
| `pending` | Đang chờ xử lý |
| `running` | Đang phát hiện hoặc tải |
| `completed` | Tải thành công |
| `failed` | Lỗi mạng hoặc hệ thống |
| `blocked_policy` | Bị chặn vì vi phạm chính sách |
| `blocked_drm` | Bị chặn vì có bảo vệ DRM |
| `stream_not_found` | Không tìm thấy luồng media hợp lệ |

---

## 9. MinIO — lưu tệp media đã tải

Sau khi tải ảnh/video/audio, hãy lưu tệp vào MinIO (lưu trữ đối tượng tương thích S3) và lưu metadata (object key, MIME type, kích thước, checksum) vào PostgreSQL. Không lưu tệp nhị phân trực tiếp trong database.

---

## 10. Bài thực hành

### Bài 1: Tải ảnh trực tiếp bằng HTTPX

1. Tạo một tệp ảnh thử nghiệm trên máy bạn hoặc dùng URL ảnh bạn sở hữu.
2. Viết hàm dùng HTTPX streaming tải ảnh về tệp cục bộ.
3. Kiểm tra `Content-Type` và magic bytes trước khi lưu.
4. Từ chối tệp vượt quá kích thước cho phép.

### Bài 2: Đọc thông tin ảnh bằng Pillow

1. Mở tệp ảnh đã tải bằng Pillow.
2. In ra kích thước và định dạng ảnh.
3. Thử mở một tệp không phải ảnh (ví dụ `.txt` đổi tên thành `.jpg`) và đảm bảo Pillow báo lỗi.

### Bài 3: Mở trang video và chờ trình phát

1. Tạo một trang demo đơn giản có thẻ `<video>` xuất hiện sau JavaScript chạy.
2. Dùng Playwright mở trang và chờ phần tử `video` xuất hiện.
3. In ra URL của trang sau khi tải xong.

### Bài 4: Phát hiện phản hồi mạng chứa media

1. Dùng Crawl4AI với `capture_network_requests=True` trên trang demo.
2. Lọc các phản hồi có URL chứa `.m3u8` hoặc `.mpd`.
3. Loại bỏ cookie và token khỏi dữ liệu in ra.

### Bài 5: Trích xuất thông tin video bằng yt-dlp (mock)

1. Không gọi yt-dlp tải video thật trong test đơn vị.
2. Viết hàm giả lập `YoutubeDL.extract_info` trả về metadata mẫu.
3. Kiểm tra `sanitize_info` và `progress_hooks` xử lý dữ liệu đúng cách.

### Bài 6: Kiểm tra chính sách trước tải

1. Tạo danh sách domain được phép và bị chặn.
2. Viết hàm kiểm tra URL media trước khi tạo công việc tải.
3. Thử URL từ domain không được phép, đảm bảo từ chối.

---

## 11. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Tải ảnh bằng HTTPX; đọc thông tin ảnh bằng Pillow; mở trang bằng Playwright. |
| Intermediate | Phát hiện phản hồi mạng media bằng Crawl4AI; dùng yt-dlp trích xuất metadata; áp dụng allowlist domain. |
| Advanced | Xây action recipe đã review; xử lý trạng thái `blocked_drm`/`blocked_policy`; chạy yt-dlp/FFmpeg trong worker nền. |
| Master | Thiết kế pipeline media đa loại, tối ưu dung lượng tệp, giám sát tiến độ tải và chi phí lưu trữ. |

---

## 12. Liên kết tài liệu chính thức

- [Playwright page actions](https://playwright.dev/python/docs/input)
- [Playwright frames](https://playwright.dev/python/docs/frames)
- [Playwright network events](https://playwright.dev/python/docs/network)
- [Crawl4AI network capture](https://docs.crawl4ai.com/advanced/network-console-capture/)
- [yt-dlp README / embedding](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp)
- [FFmpeg documentation](https://ffmpeg.org/documentation.html)
- [Pillow documentation](https://pillow.readthedocs.io/)
- [HTTPX async streaming](https://www.python-httpx.org/async/#streaming-responses)

---

## 13. Ranh giới bắt buộc (đọc lại trước khi thực hành)

1. Chỉ tải media từ domain bạn sở hữu hoặc được phép.
2. Không bypass DRM, paywall, CAPTCHA hay geo-blocking.
3. Không nhận selector/JavaScript/action từ người dùng hoặc LLM.
4. Không lưu cookie/token trong phản hồi mạng khi ghi log.
5. Chạy yt-dlp/FFmpeg trong worker nền, không trong xử lý API trực tiếp.

---

**Khi hoàn thành học phần 04, hãy chuyển sang [05-observability-and-quality.md](05-observability-and-quality.md) để học về ghi log, theo dõi và kiểm thử chất lượng.**
