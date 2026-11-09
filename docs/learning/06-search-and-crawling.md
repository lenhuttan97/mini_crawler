# 06 — Search & Crawl Capstone

> **Status: Current repository + target architecture.** Đây là capstone cuối lộ trình: SearXNG, HTTPX, selectolax và markdownify kết hợp với workflow/job/policy đã học. Crawl4AI/Playwright chỉ là **After MVP**: chỉ dùng khi dependency, reviewed recipe, sandbox và policy được phê duyệt. Search độc lập không auto-crawl; chỉ workflow `search_and_extract` explicit mới tạo crawl job có budget.

> Học phần này dạy bạn cách tìm URL trên Internet, lấy nội dung trang HTML tĩnh và xử lý trang cần JavaScript. Sau khi hoàn thành, bạn có thể biến một từ khóa tìm kiếm thành danh sách URL, rồi đưa nội dung trang về định dạng Markdown cho LLM.

---

## Mục tiêu của học phần

- Hiểu SearXNG là công cụ tìm kiếm tổng hợp (metasearch) và cách gọi API của nó.
- Dùng HTTPX để gọi trang web mà không làm treo chương trình.
- Phân tích HTML bằng selectolax và chuyển sang Markdown bằng markdownify.
- Dùng Crawl4AI và Playwright khi trang web cần JavaScript để hiển thị nội dung.
- Áp dụng kiểm tra bảo mật trước khi truy cập bất kỳ URL nào.
- Viết test mà không gọi mạng thật.

---

## Lộ trình năng lực trong bài này

| Mức | Bạn tập trung vào | Khi nào nên đi tiếp? |
|-----|-------------------|----------------------|
| Beginner | Chạy SearXNG local, lấy một trang tĩnh và đọc được HTML/Markdown. | Bạn hiểu URL, request và vì sao cần timeout. |
| Intermediate | Xử lý trang có JavaScript, `robots.txt` và test không gọi mạng thật. | Bạn chỉ crawl nội dung mình được phép truy cập. |
| Advanced | Thêm giới hạn kích thước, concurrency, retry có kiểm soát và xử lý lỗi. | Bạn đo được lỗi, thời gian và tải tạo ra. |
| Master | Thiết kế pipeline có fallback và bảo vệ SSRF ở mọi bước. | Bạn review được rủi ro trước khi đưa crawler vào production. |

Bạn không cần hoàn thành cấp sau ngay. Hãy làm bài thực hành của cấp hiện tại trên trang demo, trang bạn sở hữu hoặc nơi bạn được phép truy cập.

---

## 1. Tổng quan: tìm URL là gì?

Khi bạn muốn tìm thông tin trên Internet, bạn thường nhập từ khóa vào công cụ tìm kiếm. Máy tìm kiếm trả về danh sách liên kết (URL). Trong dự án Mini Crawler, **SearXNG** là một lựa chọn mã nguồn mở mà bạn có thể tự vận hành để học cách gọi API tìm kiếm; đây không phải là yêu cầu bắt buộc để bắt đầu học crawler.

Luồng xử lý đơn giản:

```
Từ khóa người dùng
     │
     ▼
SearXNG tìm kiếm
     │
     ▼
Danh sách URL (title, URL, snippet)
     │
     ▼
Crawler lấy nội dung từng URL
     │
     ▼
Lưu làm Markdown cho LLM/RAG
```

---

## 2. SearXNG — công cụ tìm kiếm tổng hợp

### 2.1 SearXNG là gì?

SearXNG là một metasearch engine. Nó không tự crawl toàn bộ Internet, mà gửi yêu cầu của bạn đến nhiều máy tìm kiếm khác, thu thập kết quả rồi hiển thị lại. Khi tự vận hành SearXNG, bạn vẫn phải tôn trọng rate limit, CAPTCHA, điều khoản sử dụng và khả năng thay đổi của từng máy tìm kiếm nguồn; self-host không loại bỏ các ràng buộc đó.

### 2.2 Tại sao cần SearXNG trong dự án?

- Tìm URL từ từ khóa qua một SearXNG instance bạn đã cấu hình.
- Học cách tự kiểm soát cấu hình tìm kiếm và định dạng phản hồi.
- Bật định dạng JSON để chương trình dễ đọc kết quả.

Kết quả và mức tải được phép vẫn phụ thuộc vào các search engine nguồn. Không dùng cấu hình này để né giới hạn truy cập hoặc cơ chế bảo vệ của họ.

### 2.3 Cách chạy SearXNG bằng Docker

Ví dụ này chỉ dành cho máy local để học. Thay `secret_key` bằng giá trị ngẫu nhiên riêng và không commit nó. Image `latest` thuận tiện để thử nghiệm nhưng không phù hợp cho deployment: hãy pin một version hoặc digest đã review. Giữ cổng chỉ ở `127.0.0.1`, trừ khi bạn đã cấu hình xác thực, giới hạn truy cập và vận hành an toàn cho dịch vụ công khai.

Tạo `infra/searxng/settings.yml`:

```yaml
use_default_settings: true

general:
  debug: false
  instance_name: "Mini Crawler Search"

search:
  safe_search: 1
  formats:
    - json

server:
  secret_key: "thay-the-bang-mat-khau-ngau-nhien"
  limiter: false
```

Tạo `docker-compose.yml` (phần SearXNG):

```yaml
services:
  searxng:
    image: searxng/searxng:latest
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - ./infra/searxng:/etc/searxng:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
    restart: unless-stopped
```

Chạy:

```bash
docker compose up -d searxng
```

Kiểm tra:

```bash
curl "http://127.0.0.1:8080/search?q=python&format=json"
```

Nếu thấy JSON trả về danh sách kết quả, SearXNG đã chạy đúng.

### 2.4 Gọi SearXNG bằng Python (HTTPX)

Cài HTTPX:

```bash
uv add httpx
```

Ví dụ gọi tìm kiếm:

```python
import httpx

async def search_searxng(query: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "http://127.0.0.1:8080/search",
            params={"q": query, "format": "json", "language": "all"},
        )
        response.raise_for_status()
        return response.json()
```

### 2.5 Bảo mật khi gọi SearXNG

- Chỉ gọi SearXNG chạy trên máy nội bộ hoặc mạng bạn kiểm soát.
- Không gửi API key hoặc token nhạy cảm trong query search.
- Giới hạn số lượng kết quả trả về để không quá tải.

---

## 3. HTTPX — gọi trang web không đồng bộ

### 3.1 HTTPX là gì?

HTTPX là thư viện Python gọi HTTP (trang web, API) theo cách không đồng bộ (async). Nó cho phép chương trình tiếp tục làm việc khác trong khi chờ trang web phản hồi, không bị treo.

### 3.2 Ví dụ lấy nội dung trang web

```python
import httpx

async def fetch_page(url: str) -> str:
    # Không tự theo redirect khi URL có thể đến từ người dùng hoặc kết quả search.
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
```

### 3.3 Các tham số quan trọng

| Tham số | Ý nghĩa | Giá trị đề xuất |
|---------|---------|-----------------|
| `timeout` | Thời gian chờ tối đa | 10–30 giây |
| `headers` | Thông tin gửi kèm yêu cầu | User-Agent minh bạch |
| `follow_redirects` | Tự động theo liên kết chuyển hướng | `False` (mặc định); chỉ theo từng hop sau khi kiểm tra lại URL |
| Kích thước response | Giới hạn dung lượng tải về khi stream | Từ chối theo `Content-Length` và dừng khi vượt mức, ví dụ 5 MB |

### 3.4 Bảo mật trước khi gọi URL (SSRF)

**Cảnh báo:** đoạn mã dưới đây chỉ minh họa cách đọc URL, **không phải** cơ chế chống SSRF đủ dùng trong production. Không mở endpoint nhận URL từ người dùng trước khi phần này được review bảo mật.

Một triển khai production cần, tối thiểu:

1. Chỉ cho phép `http` hoặc `https`.
2. Không cho phép `file:`, `data:`, `javascript:`.
3. Phân giải mọi bản ghi DNS của hostname và từ chối toàn bộ địa chỉ loopback, private, link-local, multicast, reserved hoặc địa chỉ nội bộ khác.
4. Chỉ kết nối tới địa chỉ đã được kiểm tra, giảm rủi ro DNS rebinding, và kiểm tra lại trước **mỗi** redirect rồi mới gửi request tiếp theo.
5. Giới hạn port, thời gian, kích thước response và số lần redirect theo chính sách đã review.

Ví dụ chỉ dùng cho bài tập (không dùng làm `is_safe_url` trong production):

```python
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

def looks_safe_for_demo(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    return True
```

Trong production, hãy dùng một giải pháp SSRF đã được đội bảo mật review, thực hiện kiểm tra DNS/IP và redirect ở tầng kết nối; chỉ so chuỗi hostname như trên là không đủ.

---

## 4. selectolax — phân tích HTML nhanh

### 4.1 selectolax là gì?

selectolax là thư viện Python phân tích HTML cực nhanh, dùng CSS selector để lấy phần tử bạn cần (ví dụ: tiêu đề, liên kết, nội dung chính).

### 4.2 Ví dụ lấy tiêu đề và liên kết

```python
from selectolax.parser import HTMLParser

html = "<html><body><h1>Tiêu đề trang</h1><a href='/trang-1'>Liên kết 1</a></body></html>"
parser = HTMLParser(html)

title = parser.css_first("h1").text()
link = parser.css_first("a").attributes.get("href")

print(title)   # Tiêu đề trang
print(link)    # /trang-1
```

### 4.3 Loại bỏ phần không cần thiết

Trước khi chuyển sang Markdown, hãy xóa các thẻ gây nhầm như `script`, `style`, `nav`, `footer`:

```python
for tag in parser.css("script, style, nav, footer"):
    tag.decompose()
```

---

## 5. markdownify — chuyển HTML sang Markdown

### 5.1 Tại sao cần Markdown?

LLM dễ đọc và xử lý Markdown hơn HTML thô. Markdown bỏ bớt thẻ phức tạp, giữ lại cấu trúc đoạn văn, tiêu đề, liên kết.

### 5.2 Ví dụ chuyển đổi

```python
import markdownify

html = "<h1>Tiêu đề</h1><p>Nội dung đoạn văn.</p><a href='https://example.com'>Liên kết</a>"
markdown = markdownify.markdownify(html)

print(markdown)
# # Tiêu đề
#
# Nội dung đoạn văn.
# [Liên kết](https://example.com)
```

---

## 6. Crawl4AI — crawler thân thiện với LLM

### 6.1 Crawl4AI là gì?

Crawl4AI là công cụ cào trang web mã nguồn.open-source, xuất ra Markdown sạch, hỗ trợ render JavaScript và trích xuất dữ liệu có cấu trúc. Nó rất phù hợp cho hệ thống RAG (Retrieval-Augmented Generation) và AI agent.

### 6.2 Cài Crawl4AI

```bash
uv add crawl4ai
```

Sau đó cài trình duyệt Playwright đi kèm:

```bash
uv run playwright install chromium
```

### 6.3 Ví dụ cào một trang

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://example.com")
        print(result.markdown[:500])

asyncio.run(main())
```

### 6.4 Cấu hình Crawl4AI

| Cấu hình | Ý nghĩa |
|----------|---------|
| `BrowserConfig(headless=True)` | Chạy trình duyệt không hiển thị cửa sổ. |
| `CrawlerRunConfig(cache_mode=...)` | Kiểm soát việc lưu đệm (cache) kết quả cào. |
| `check_robots_txt=True` | Tuân thủ quy tắc `robots.txt` của trang web. |

---

## 7. Playwright — điều khiển trình duyệt cho trang cần JavaScript

### 7.1 Tại sao cần Playwright?

Một số trang web không hiển thị nội dung trong HTML ban đầu. Nội dung chỉ xuất hiện sau khi JavaScript chạy (ví dụ: nhấn nút "Xem thêm", cuộn trang, hoặc trình phát video khởi tạo). HTTPX không chạy JavaScript, nên cần Playwright.

### 7.2 Playwright trong Crawl4AI

Crawl4AI đã tích hợp Playwright. Khi bạn cần render JavaScript, hãy dùng `CrawlerRunConfig` với `wait_for` hoặc `js_code`.

Ví dụ chờ nội dung xuất hiện:

```python
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

config = CrawlerRunConfig(
    wait_for="css:.video-player",
    cache_mode=CacheMode.BYPASS,
)

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun("https://example.com/video-page", config=config)
```

### 7.3 Action recipe cho media (sau này)

Chỉ thực hành trên trang demo, nội dung bạn sở hữu hoặc nơi bạn có quyền tự động hóa. Với media đó, Playwright có thể giúp kiểm tra rằng trình phát khởi tạo đúng theo một recipe cố định đã review:

1. Mở trang được phép kiểm tra.
2. Chờ phần tử trình phát xuất hiện.
3. Nhấn nút Play theo recipe đã review.
4. Ghi nhận trạng thái hoặc lỗi để phục vụ kiểm thử.

Không dùng automation để trích xuất, lưu hay phát lại URL media nhằm vượt DRM, paywall, CAPTCHA, geo-blocking hoặc điều khoản của dịch vụ. Không nhận selector hoặc JavaScript do người dùng/LLM truyền vào; chỉ dùng action recipe đã được kiểm tra và lưu trong mã nguồn.

---

## 8. Luồng cào dữ liệu trong dự án

```
URL từ SearXNG
     │
     ▼
Kiểm tra bảo mật (SSRF, robots.txt, domain cho phép)
     │
     ▼
Thử lấy bằng HTTPX (trang HTML tĩnh)
     │
     ├─ Thành công → phân tích selectolax → markdownify → lưu Markdown
     │
     └─ Thất bại hoặc cần JavaScript → dùng Crawl4AI/Playwright
           │
           ▼
     Kết quả Markdown từ Crawl4AI → lưu cùng cách trên
```

**Classification does not trigger downloads.** `document_type` (kể cả `media_page`) chỉ chọn cách xử lý/lưu document. Nó không tự tạo image/video candidate hay download job; page-driven media chỉ chạy trong workflow `extract_images`/`extract_video` được caller yêu cầu rõ ràng. Xem [media candidate workflows](../platform/media-candidate-workflows.md).

---

## 9. Bài thực hành

### Bài 1: Chạy SearXNG và gọi tìm kiếm

1. Khởi động SearXNG bằng Docker Compose.
2. Gọi `curl` với `format=json` và quan sát kết quả.
3. Viết hàm Python dùng HTTPX gọi SearXNG và in ra 5 kết quả đầu tiên.

### Bài 2: Lấy nội dung trang tĩnh

1. Chọn một trang web bạn sở hữu hoặc được phép truy cập.
2. Dùng HTTPX lấy HTML.
3. Dùng selectolax lấy tiêu đề và liên kết đầu tiên.
4. Dùng markdownify chuyển HTML đã làm sạch sang Markdown.
5. In ra độ dài của Markdown trước và sau khi làm sạch.

### Bài 3: Cào trang cần JavaScript

1. Tạo một trang demo đơn giản có nội dung xuất hiện sau 2 giây (dùng JavaScript).
2. Dùng Crawl4AI với `wait_for` để chờ nội dung xuất hiện.
3. So sánh kết quả HTTPX (không có nội dung) và Crawl4AI (có nội dung).

### Bài 4: Kiểm tra bảo mật

1. Viết hàm `looks_safe_for_demo` chỉ để nhận biết scheme và localhost.
2. Thử truyền URL `http://localhost:5432` và đảm bảo hàm từ chối.
3. Ghi ra vì sao hàm này chưa đủ cho production: DNS/IP, DNS rebinding, redirect và giới hạn response phải được kiểm tra riêng.

---

## 10. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Chạy được SearXNG local; gọi HTTPX lấy trang tĩnh; chuyển HTML sang Markdown. |
| Intermediate | Dùng Crawl4AI crawl trang cần JavaScript; áp dụng `robots.txt`; viết test mock HTTPX. |
| Advanced | Tối ưu timeout, giới hạn kích thước phản hồi, xử lý lỗi mạng, giới hạn concurrency theo domain. |
| Master | Thiết kế quy trình fallback tĩnh → browser, đánh giá hiệu năng crawl, bảo mật SSRF nghiêm ngặt. |

---

## 11. Liên kết tài liệu chính thức

- [SearXNG Search API](https://docs.searxng.org/dev/search_api.html)
- [SearXNG installation](https://docs.searxng.org/admin/installation.html)
- [HTTPX async support](https://www.python-httpx.org/async/)
- [selectolax documentation](https://selectolax.readthedocs.io/)
- [markdownify repository](https://github.com/matthewwithanm/python-markdownify)
- [Crawl4AI quick start](https://docs.crawl4ai.com/core/quickstart/)
- [Crawl4AI markdown generation](https://docs.crawl4ai.com/core/markdown-generation/)
- [Playwright Python introduction](https://playwright.dev/python/docs/intro)
- [Playwright network events](https://playwright.dev/python/docs/network)

---

**Bạn đã hoàn tất toàn bộ 6 học phần. Hãy quay lại [`../INDEX.md`](../INDEX.md) để đọc active worker contracts, chọn workflow/version roadmap phù hợp và bắt đầu triển khai theo evidence/test.**
