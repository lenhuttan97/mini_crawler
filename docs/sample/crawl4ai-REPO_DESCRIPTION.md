# 📄 Mô tả Repository: Crawl4AI

> File này được tạo để tổng quan về repo, mục đích, công nghệ và hướng dẫn xây dựng phiên bản "mini".

---

## 1. Repo này là gì?

**Crawl4AI** là một mã nguồn mở (open-source), viết bằng **Python**, dùng để **trích xuất và cào dữ liệu web** (web crawler & scraper) thân thiện với các mô hình ngôn ngữ lớn (LLM). Mục tiêu chính là biến các trang web thành **Markdown sạch**, **JSON có cấu trúc**, hoặc dữ liệu tìm kiếm — phù hợp cho hệ thống RAG (Retrieval-Augmented Generation), pipeline dữ liệu AI, và các agent tự động.

Repo được duy trì bởi **unclecode**, giấy phép **Apache-2.0**, yêu cầu **Python ≥ 3.10**.

- Trang chủ: https://crawl4ai.com
- GitHub: https://github.com/unclecode/crawl4ai

---

## 2. Mục đích

### 2.1 Mục đích kỹ thuật
- **Cào trang web** và chuyển đổi HTML sang Markdown sạch (loại bỏ quảng cáo, menu, footer, v.v.).
- **Trích xuất dữ liệu có cấu trúc** (JSON) từ trang web bằng các chiến lược extraction (LLM, CSS, xpath, regex...).
- **Deep crawling**: duyệt sâu nhiều trang liên quan trong cùng một domain (BFS, DFS, Best-First...).
- **Tương thích LLM**: đầu ra tối ưu để đưa vào vector database, LLM context, RAG.

### 2.2 Mục đích chiến lược (theo MISSION.md)
Dự án là nền tảng mở đầu tiên trong một con đường lớn hơn về **Data Capitalization** (tinh hóa dữ liệu thành tài sản):

1. **Open-source foundation** — công cụ trích xuất dữ liệu minh bạch, bảo mật, do cộng đồng phát triển.
2. **Data capitalization platform** — giúp cá nhân/doanh nghiệp biến chân trải nghiệm số thành tài sản có cấu trúc.
3. **Data marketplace** — sàn giao dịch dữ liệu tự nguyện, tạo giá trị cho cả người tạo dữ liệu và nhà phát triển AI.

---

## 3. Cách tiếp cận (Architecture & Flow)

Crawl4AI tuân theo mô hình **async-first**, chạy trên `asyncio` và chia thành các thành phần chính:

| Thành phần | Vai trò |
|---|---|
| `AsyncWebCrawler` | Điểm vào chính (high-level API), điều phối toàn bộ quá trình crawl. |
| `BrowserConfig` / `CrawlerRunConfig` | Cấu hình trình duyệt (Playwright) và cấu hình lần chạy crawl. |
| `AsyncCrawlerStrategy` | Chiến lược crawl: `Playwright` (render JS) hay `HTTP` (nhẹ, nhanh). |
| `BrowserManager` / `BrowserAdapter` | Quản lý vòng đời trình duyệt, tab, stealth (anti-bot). |
| `AsyncUrlSeeder` | Sinh seed URLs (sitemap, RSS, tìm kiếm Google...). |
| `DomainMapper` | Ánh xạ domain, quy tắc vào/ra (egress policy). |
| `DeepCrawlDecorator` | Deep crawling với BFS / DFS / Best-First / Crazy 전략. |
| `ContentFilterStrategy` | Lọc nội dung (loại bỏ noise, giữ phần chính). |
| `ExtractionStrategy` | Trích xuất dữ liệu có cấu trúc (LLM, CSS, xpath...). |
| `MarkdownGenerationStrategy` | Sinh Markdown từ HTML. |
| `ChunkingStrategy` | Chia nhỏ văn bản cho RAG / vector DB. |
| `AsyncDispatcher` | Điều phối crawl song song nhiều URL (MemoryAdaptive, RateLimiter...). |
| `AsyncDatabase` | Lưu trữ cache và kết quả crawl (SQLite qua aiosqlite). |

**Luồng xử lý điển hình:**

```
URL seed → AsyncUrlSeeder → DomainMapper → AsyncCrawlerStrategy
   → BrowserManager (Playwright) → HTML
   → ContentFilter → MarkdownGeneration → ExtractionStrategy
   → CrawlResult (Markdown + JSON + metadata)
   → (tùy chọn) Chunking → Vector DB / RAG
```

### Đặc điểm nổi bật
- **Async & concurrent**: crawl nhiều URL đồng thời, kiểm soát bộ nhớ và tốc độ.
- **Stealth / anti-bot**: giả mạo user-agent, TLS fingerprint, tránh bị chặn.
- **Render JavaScript**: hỗ trợ SPA, trang tải nội dung dynamique qua Playwright/patchright.
- **Cache**: tránh crawl lại trang đã có.
- **CLI**: lệnh `crwl` để crawl từ dòng lệnh.
- **Docker**: có sẵn `docker-compose.yml`, `Dockerfile` để tự triển khai server.

---

## 4. Công nghệ sử dụng

### Ngôn ngữ & môi trường
- **Python 3.10+** (khuyên dùng 3.11 / 3.12 / 3.13)
- Quản lý phụ thuộc: `uv`, `pip`, `setuptools`

### Thư viện chính (từ `pyproject.toml`)

| Thuật ngữ | Thư viện | Vai trò |
|---|---|---|
| Trình duyệt headless | `playwright`, `patchright`, `playwright-stealth` | Render JS, anti-detection |
| HTTP async | `aiohttp`, `httpx` (http2) | Crawl nhẹ không cần trình duyệt |
| HTML parsing | `beautifulsoup4`, `lxml`, `cssselect` | Phân tích DOM, chọn phần tử |
| Markdown | `html2text` (thư mục內建) | Chuyển HTML → Markdown |
| LLM / Embedding | `unclecode-litellm`, `transformers`, `sentence-transformers`, `torch` | Extraction, vector hóa |
| CSDL | `aiosqlite`, `aiosqlite` | Cache & lưu kết quả (SQLite async) |
| Config | `pydantic`, `PyYAML`, `python-dotenv` | Xác thực cấu hình, biến môi trường |
| CLI | `click`, `rich` | Giao diện dòng lệnh đẹp |
| Tiện ích | `numpy`, `pillow`, `fake-useragent`, `chardet`, `nltk`, `rank-bm25`, `xxhash`, `shapely`, `alphashape`, `lark` | Xử lý văn bản, hình ảnh, băm,Similarity, v.v. |
| PDF | `pypdf` (tùy chọn) | Trích xuất PDF |

### Triển khai
- **Docker**: `Dockerfile`, `docker-compose.yml` (chạy server trên cổng 11235)
- **PyPI**: `pip install -U crawl4ai`

---

## 5. Nếu muốn tạo 1 phiên bản "mini" thì cần thực hiện gì?

Một phiên bản mini của Crawl4AI nên tập trung vào **cốt lõi**: crawl một danh sách URL → chuyển sang Markdown → trích xuất đơn giản → lưu kết quả. Dưới đây là bản roadmap giảm bớt.

### Bước 1: Xác định phạm vi (scope)
| Thành phần | Full Crawl4AI | Mini version |
|---|---|---|
| Trình duyệt | Playwright (JS render) | `httpx`/`aiohttp` (chỉ HTML tĩnh) |
| Deep crawl | BFS/DFS/Best-first | Chỉ crawl 1 trang (hoặc 1 cấp liên kết) |
| Lọc nội dung | Nhiều chiến lược | Lọc thẻ `<script>`, `<style>`, quảng cáo cơ bản |
| Trích xuất | LLM, CSS, xpath | Regex / CSS selector đơn giản |
| Đầu ra | Markdown + JSON + metadata | Markdown thuần |
| Lưu trữ | SQLite cache | File JSON / in-memory |
| Song song | Dispatcher phức tạp | `asyncio.gather` cơ bản |
| CLI | `crwl` đầy đủ | Lệnh đơn giản |

### Bước 2: Cấu trúc gợi ý cho mini

```
crawl4ai-mini/
├── pyproject.toml          # dependencies ít: httpx, beautifulsoup4, pydantic, click
├── crawl4ai_mini/
│   ├── __init__.py
│   ├── crawler.py          # AsyncWebCrawler đơn giản (httpx + bs4)
│   ├── config.py           # CrawlerConfig (timeout, user-agent, headers)
│   ├── markdown.py         # html2text hoặc regex cơ bản
│   ├── extractor.py        # trích xuất theo CSS selector
│   ├── models.py           # CrawlResult (url, markdown, status, error)
│   └── cli.py              # lệnh crawl <url> [--output file.md]
├── tests/
└── README.md
```

### Bước 3: Các công nghệ tối thiểu cần cài

```toml
dependencies = [
    "httpx>=0.27",          # HTTP client async
    "beautifulsoup4>=4.12", # parse HTML
    "html2text>=2020",      # HTML → Markdown (tuỳ chọn)
    "pydantic>=2",          # validate config/result
    "click>=8",             # CLI
]
```

### Bước 4: Triển khai từng giai đoạn

| Giai đoạn | Công việc | Ước tính |
|---|---|---|
| **Giai đoạn 1** | Viết `CrawlerConfig` + `CrawlResult` (Pydantic models) | 1–2 ngày |
| **Giai đoạn 2** | Viết `AsyncWebCrawler.crawl(url)` dùng `httpx` + `BeautifulSoup` | 2–3 ngày |
| **Giai đoạn 3** | Sinh Markdown bằng `html2text` hoặc regex cơ bản | 1 ngày |
| **Giai đoạn 4** | Thêm `ExtractionStrategy` đơn giản (CSS selector) | 1–2 ngày |
| **Giai đoạn 5** | CLI `crawl4ai-mini crawl <url> --output out.md` | 1 ngày |
| **Giai đoạn 6** (tuỳ chọn) | Thêm Playwright cho render JS, cache SQLite | 3–5 ngày |

### Bước 5: Code ví dụ nhanh (mini crawler)

```python
import httpx
from bs4 import BeautifulSoup
import html2text


async def crawl(url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # Loại bỏ noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    markdown = html2text.html2text(str(soup))
    return markdown
```

---

## 6. Tóm tắt

| Mục | Chi tiết |
|---|---|
| **Tên repo** | Crawl4AI |
| **Ngôn ngữ** | Python 3.10+ |
| **Mục đích chính** | Web crawler & scraper sản xuất Markdown/JSON cho LLM & RAG |
| **Công nghệ cốt lõi** | Playwright, aiohttp/httpx, BeautifulSoup, lxml, html2text, Pydantic, Click |
| **Điểm mạnh** | Async, render JS, anti-bot, deep crawl, extraction có cấu trúc, cache |
| **Giấy phép** | Apache-2.0 |
| **Để làm phiên mini** | Bỏ Playwright/Deep crawl/LLM, giữ `httpx` + `BeautifulSoup` + Markdown + CLI đơn giản |

---

## 7. Công nghệ cần thêm để lấy link `.m3u8` từ trang stream video

Crawl4AI (và các công cụ quét HTML tĩnh) **không đủ** để phát hiện liên kết video `.m3u8` (luồng HLS) trên các trang stream phim/video hiện đại. Lý do: link `.m3u8` thường **không nằm trong HTML ban đầu**, mà được sinh động bởi JavaScript sau khi trình duyệt thực thi, gọi AJAX, hoặc nhúng qua `<iframe>` có `src` rỗng ban đầu.

### 7.1 Tại sao HTML tĩnh không đủ?

| Trường hợp | HTML tĩnh lấy được? | Lý do |
|------------|---------------------|-------|
| `<video src="file.mp4">` | ✅ Có | Thuộc tính `src` ghi sẵn trong HTML |
| `<source src="stream.m3u8">` | ✅ Có (chuỗi thô) | Lấy được link, nhưng không phân tích playlist bên trong |
| `<iframe src="">` + JS điền sau | ❌ Không | `src` rỗng ban đầu, được điền bởi JS |
| AJAX gọi API để lấy URL player | ❌ Không | Phản hồi JSON chỉ xuất hiện sau khi chạy JS |
| JWPlayer / Video.js / HLS.js khởi tạo luồng | ❌ Không | Manifest URL được truyền vào player qua JS, không in ra HTML |
| Link `.m3u8` có token/session tạm thời | ❌ Không | Yêu cầu cookie, header, hoặc mã hóa từ JS |

### 7.2 Công nghệ cần thêm

| Nhóm | Công cụ đề xuất | Vai trò |
|------|----------------|---------|
| **Trình duyệt tự động** | `playwright` (Python/Node.js), `puppeteer`, `selenium` | Chạy trình duyệt thực tế, thực thi JavaScript, theo dõi lưu lượng mạng |
| **Lắng nghe phản hồi mạng** | `page.on("response")` của Playwright/Puppeteer | Lọc các response chứa `.m3u8`, `.mpd`, `.ts` |
| **Tải manifest HLS** | `httpx`, `requests`, `aiohttp` | Tải file `.m3u8` sau khi đã có URL |
| **Phân tích playlist HLS** | Thư viện `m3u8` (Python), hoặc xử lý thô bằng text | Đọc danh sách chất lượng (360p/720p/1080p) và các đoạn `.ts` |
| **Proxy / đầu vào** | Proxy residential, VPN | Bypass geo-blocking, chặn IP |
| **Anti-bot / stealth** | `playwright-stealth`, `patchright`, thay User-Agent/TLS fingerprint | Tránh bị phát hiện là bot |
| **Gỡ gói HTTPS (tuỳ chọn)** | `mitmproxy`, Charles Proxy, Fiddler | Xem toàn bộ request/response để tìm `.m3u8` |

### 7.3 Luồng làm việc kỹ thuật (khái niệm)

```
1. Khởi động Playwright (Chromium headless)
2. Mở trang video
3. Lắng nghe sự kiện 'response' của mọi request HTTP
4. Lọc response có URL chứa '.m3u8' hoặc Content-Type 'application/vnd.apple.mpegurl'
5. Lưu URL kèm header (User-Agent, Referer, Cookie…)
6. (Tuỳ chọn) Tải .m3u8 và phân tích danh sách đoạn .ts
7. Đóng trình duyệt
```

### 7.4 Lưu ý pháp lý

- Việc lấy luồng video từ trang web **bạn không sở hữu** hoặc **không có quyền** có thể vi phạm bản quyền và điều khoản sử dụng.
- Một số kỹ thuật bypass anti-bot có thể bị coi là truy cập trái phép tùy theo pháp luật từng quốc gia.
- Nếu bạn là chủ sở hữu trang web hoặc có bản quyền nội dung, bạn hoàn toàn có quyền phân tích luồng mạng của trang mình.

---

*Tài liệu này được tổng hợp từ README.md, pyproject.toml, MISSION.md và cấu trúc thư mục nguồn của repository Crawl4AI tại thời điểm phân tích.*