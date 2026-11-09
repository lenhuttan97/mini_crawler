# Hướng dẫn xây dựng Mini Search bằng Python (học từ SearXNG)

Tài liệu này hướng dẫn xây dựng một **meta-search engine tối giản** để học kiến
trúc của SearXNG: nhận truy vấn, gọi nhiều nguồn dữ liệu, chuẩn hoá kết quả,
khử trùng lặp và hiển thị chúng trong một web UI nhỏ.

Đây không phải bản sao SearXNG. SearXNG là dự án AGPL-3.0-or-later; hãy tham
khảo ý tưởng và tự viết mã của mình, thay vì sao chép mã nguồn vào dự án khác.

## Trạng thái trong Mini Crawler

**SearXNG là provider tìm kiếm hiện tại** của Mini Crawler, được gọi qua
`SearchService` và URL cấu hình hiện có. **Mini Search là mục tiêu standalone
trong tương lai**: đây là ứng dụng học tập/sản phẩm riêng, chưa phải module hay
capability đang chạy trong crawler.

| Giai đoạn | Service dùng cho search | Ranh giới giữ nguyên |
|---|---|---|
| Hiện tại | Self-hosted SearXNG qua `SearchService` | `search()` chuẩn hoá/deduplicate kết quả và **không tự crawl** URL result. |
| Khi Mini Search sẵn sàng | Mini Search thay SearXNG tại call site hiện có | Kết quả vẫn là title/URL/snippet đã chuẩn hoá; workflow quyết định crawl explicit, không phải provider. |

Không tạo `app/features/search/`, provider interface, wrapper hay cờ cấu hình
mới chỉ để chuẩn bị cho Mini Search. Chỉ khi Mini Search là implementation thứ
hai đang chạy mới trích seam nhỏ nhất tại call site hiện có; cấu trúc
`app/services/`, `app/adapters/` và `app/workers/` vẫn giữ nguyên.

### Điều kiện chuyển provider sau này

Chỉ chuyển controlled traffic từ SearXNG khi Mini Search:

1. qua cùng contract/integration test cho kết quả đã chuẩn hoá, timeout và lỗi upstream;
2. giữ Search là discovery-only, không tạo crawl job hay gọi crawler;
3. có rollback về SearXNG; và
4. không đưa raw provider payload, credential hoặc cấu hình provider vào result hay job data.

Đây không phải dual-write hoặc data migration. Nếu thử provider mới lỗi, quay
về SearXNG; việc thay đổi workflow/job architecture là một project riêng.

## 1. Phạm vi của bản mini

### Mục tiêu

- Có trang `GET /` với ô tìm kiếm.
- Có endpoint `GET /search?q=<query>`.
- Gọi đồng thời 2 nguồn có API công khai hoặc API chính thức.
- Chuẩn hoá mọi kết quả về cùng một kiểu dữ liệu.
- Gộp kết quả trùng URL, xếp hạng đơn giản và hiển thị tối đa 20 kết quả.
- Mỗi nguồn bị giới hạn thời gian; một nguồn lỗi không làm hỏng toàn bộ tìm kiếm.

### Không làm ở phiên bản đầu

- Không scrape HTML của công cụ tìm kiếm hoặc né CAPTCHA/rate limit.
- Không có tài khoản, cookie tuỳ biến, cache phân tán, proxy, plugin hay i18n.
- Không cố tái tạo các tính năng đầy đủ của SearXNG như bang syntax, ảnh,
  RSS/JSON, metrics, preference và nhiều loại kết quả.

Với bản đầu, hãy dùng một `MockEngine` để phát triển giao diện, rồi thay bằng
hai adapter dùng API có điều khoản phù hợp. Ví dụ: API Wikipedia và Stack
Exchange; nếu muốn web-search thực sự, dùng API chính thức của một nhà cung
cấp mà bạn có quyền sử dụng.

## 2. Những phần cần học từ repo này

SearXNG là ứng dụng Flask/Python (Python >= 3.10). Luồng rút gọn trong repo:

```text
HTTP /search
  -> searx/webadapter.py: kiểm tra và tạo SearchQuery
  -> searx/search/__init__.py: tạo request cho từng engine, chạy song song
  -> searx/engines/<engine>.py: tạo request và parse response từng nguồn
  -> searx/results.py: gộp kết quả trùng, tính điểm, sắp xếp
  -> searx/webapp.py: render HTML/response
```

Các file đáng đọc:

- `searx/webapp.py`: ứng dụng Flask và route `/search`.
- `searx/webadapter.py`: validation cho `q`, trang, ngôn ngữ và timeout.
- `searx/search/__init__.py`: điều phối engine song song và giới hạn timeout.
- `searx/engines/demo_online.py`: mẫu engine có `request()` và `response()`.
- `searx/results.py`: container gộp, khử trùng lặp và sắp xếp kết quả.

Trong mini project, chỉ giữ bốn ý tưởng: **route mỏng, adapter riêng cho từng
nguồn, model kết quả chung, service điều phối**.

## 3. Kiến trúc đề xuất

```text
Trình duyệt
   -> Flask route /search
      -> validate query
      -> SearchService
         -> WikipediaEngine  -- HTTP --> Wikipedia API
         -> StackExchangeEngine -- HTTP --> Stack Exchange API
      -> normalize + deduplicate + rank
   <- Jinja template hiển thị SearchResult
```

Mỗi engine chỉ biết cách hỏi và parse **một** nhà cung cấp. `SearchService`
không biết chi tiết URL hay schema JSON của nhà cung cấp; nó chỉ nhận danh sách
`SearchResult`. Nhờ vậy có thể bỏ hoặc thêm engine mà không sửa route.

## 4. Chuẩn bị môi trường

Yêu cầu: Python 3.10+ và `venv`.

```bash
mkdir mini-searxng
cd mini-searxng
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install flask httpx pytest
```

`Flask` cung cấp web app nhỏ; `httpx` dùng gọi HTTP với timeout rõ ràng;
`pytest` dùng cho các kiểm tra cơ bản. Ghi các dependency này vào
`requirements.txt` khi bắt đầu dự án.

## 5. Cấu trúc thư mục nhỏ nhất

```text
mini-searxng/
├── app.py                 # Flask app và route
├── models.py              # SearchResult
├── engines.py             # protocol/base class và các adapter
├── search_service.py      # chạy engine, gộp và xếp hạng
├── templates/
│   ├── index.html
│   └── results.html
├── tests/
│   ├── test_engines.py
│   └── test_search_service.py
├── requirements.txt
└── README.md
```

Không cần database ở phiên bản đầu. Chỉ thêm cache sau khi đã đo được độ trễ
và xác định dữ liệu nào an toàn để cache.

## 6. Thiết kế dữ liệu và contract engine

Mọi adapter phải trả về cùng một kiểu dữ liệu. URL là khoá tốt nhất để phát
hiện kết quả trùng ở phiên bản đầu.

```python
# models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    position: int
```

```python
# engines.py
from collections.abc import Sequence
from typing import Protocol

from models import SearchResult


class SearchEngine(Protocol):
    name: str

    def search(self, query: str, limit: int) -> Sequence[SearchResult]:
        """Trả về kết quả đã được chuẩn hoá; không ném lỗi HTTP ra route."""
```

Quy ước nên giữ:

- Engine trả về `[]` khi nhà cung cấp timeout, trả HTTP lỗi hoặc dữ liệu sai.
- Engine ghi log ngắn với tên nguồn và loại lỗi, không ghi nguyên văn `query`
  nếu truy vấn có thể chứa dữ liệu riêng tư.
- Chỉ cho phép endpoint được hard-code trong adapter; không lấy URL đích từ
  tham số người dùng.
- Đặt timeout ngắn, ví dụ 2–3 giây cho từng engine.

## 7. Xây dựng theo từng bước

### Bước 1 — Làm UI và route với dữ liệu giả

1. Tạo `GET /` render `index.html` gồm form `method="get"` gửi đến `/search`.
2. Tạo `GET /search`; lấy `q`, gọi `strip()` và từ chối chuỗi rỗng hoặc dài
   hơn 200 ký tự với HTTP 400.
3. Viết `MockEngine.search()` trả ba `SearchResult` cố định.
4. Render `results.html` từ danh sách kết quả mock.

Mục tiêu là kiểm tra toàn bộ đường đi trình duyệt → Flask → template trước khi
phụ thuộc vào bất kỳ API bên ngoài nào.

### Bước 2 — Viết một adapter API

Với mỗi API chính thức, đọc tài liệu của nhà cung cấp trước để biết quota, yêu
cầu attribution và giới hạn sử dụng. Adapter làm đúng bốn việc:

1. Mã hoá `query` thành query parameter bằng `params=...`, không nối chuỗi URL.
2. Gọi `httpx.Client(timeout=2.5)` với `User-Agent` mô tả ứng dụng.
3. Kiểm tra HTTP status và parse JSON trong `try/except` hẹp.
4. Chuyển từng item hợp lệ thành `SearchResult`; bỏ qua item thiếu title hoặc URL.

Pseudo-code cho phần cốt lõi:

```python
def search(self, query: str, limit: int) -> list[SearchResult]:
    try:
        response = self.client.get(self.endpoint, params={"q": query})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    return [
        SearchResult(title=item["title"], url=item["url"],
                     snippet=item.get("snippet", ""), source=self.name,
                     position=index)
        for index, item in enumerate(payload_items(payload)[:limit], start=1)
        if item.get("title") and item.get("url")
    ]
```

`payload_items()` là hàm riêng của từng engine vì JSON của mỗi API khác nhau.
Đừng ép mọi nhà cung cấp vào cùng schema trước khi chuẩn hoá về `SearchResult`.

### Bước 3 — Điều phối nhiều engine

`SearchService` nhận danh sách engine đã khởi tạo. Dùng
`concurrent.futures.ThreadPoolExecutor` để các HTTP request chạy song song;
đợi tối đa một timeout tổng (ví dụ 3 giây), thu những future đã hoàn tất và bỏ
qua engine bị lỗi.

Thứ tự xử lý nên là:

1. Validate query tại route.
2. Gọi các engine đồng thời.
3. Nối các kết quả thành một danh sách.
4. Khử trùng lặp theo URL đã chuẩn hoá (`url.rstrip("/")`).
5. Ưu tiên kết quả xuất hiện ở nhiều nguồn; sau đó ưu tiên `position` nhỏ hơn.
6. Cắt danh sách còn tối đa 20 mục.

Quy tắc điểm đơn giản, đủ cho bản đầu:

```text
score = số nguồn cùng trả về URL đó * 100 - vị trí tốt nhất
```

Khi gộp kết quả trùng, giữ title/snippet không rỗng của kết quả đầu tiên và
gộp tên nguồn thành `Wikipedia, Stack Exchange` để người dùng thấy provenance.

### Bước 4 — Render an toàn

- Hiển thị title, snippet, URL và danh sách nguồn.
- Để Jinja auto-escape; không dùng `|safe` cho dữ liệu từ API.
- Link ngoài dùng `rel="noopener noreferrer"` khi mở tab mới.
- Hiển thị thông báo “Không có kết quả” thay vì HTTP 500 khi tất cả engine lỗi.
- Hiển thị tên engine không phản hồi chỉ khi hữu ích; không đưa traceback hoặc
  thông tin cấu hình nội bộ ra trình duyệt.

## 8. Kiểm thử tối thiểu

Không gọi API thật trong unit test. Mock HTTP response hoặc inject fake engine
vào `SearchService`.

| Kiểm tra | Kỳ vọng |
| --- | --- |
| Query rỗng hoặc toàn khoảng trắng | Route trả HTTP 400 |
| Một engine timeout | Kết quả từ engine còn lại vẫn hiển thị |
| Hai engine trả cùng URL | Chỉ còn một result và source được gộp |
| API trả item thiếu URL/title | Item bị bỏ qua, không làm route lỗi |
| Query hợp lệ | Tối đa 20 result, xếp theo score giảm dần |

Sau mỗi thay đổi, chạy:

```bash
pytest -q
flask --app app run --debug
```

Sau đó thử thủ công các case: query rỗng, query unicode tiếng Việt, API bị ngắt
mạng và hai kết quả có cùng URL.

## 9. Các bảo vệ cần có trước khi chia sẻ app

- Giới hạn độ dài query và số request mỗi IP (rate limiting).
- Dùng timeout theo engine và timeout tổng; không retry vô hạn.
- Không log query đầy đủ theo mặc định; không lưu lịch sử tìm kiếm nếu chưa có
  mục đích và chính sách riêng tư rõ ràng.
- Tôn trọng quota, robots/điều khoản và attribution của từng API.
- Lưu API key trong biến môi trường, không commit vào mã nguồn hay `.env` công khai.
- Nếu sau này thêm endpoint nhận URL từ người dùng, phải chặn SSRF; bản mini
  không nên có tính năng này.

## 10. Khi nào nâng cấp kiến trúc

Chỉ thêm các phần dưới đây khi bản mini đã hoạt động và có nhu cầu rõ ràng:

| Nhu cầu | Nâng cấp hợp lý |
| --- | --- |
| API chậm hoặc quota thấp | Cache TTL theo query đã chuẩn hoá |
| Nhiều engine | Registry/config YAML cho engine và health state |
| Tải đồng thời cao | Async HTTP (`httpx.AsyncClient`) thay vì thread pool |
| Chất lượng xếp hạng kém | Chuẩn hoá domain, đa dạng hoá nguồn, scoring có trọng số |
| Người dùng thật | Rate limit, observability, CSP và reverse proxy |

Đừng bắt đầu với plugin system, Redis, Docker hay một bộ parser query phức tạp.
Mục tiêu của mini project là hiểu pipeline tìm kiếm trước, không tái tạo toàn bộ
SearXNG.

## 11. Định nghĩa hoàn thành

Bản mini hoàn thành khi:

- Form tìm kiếm hoạt động ở local.
- Có ít nhất hai engine (có thể khởi đầu bằng một mock và một API thật).
- Một engine lỗi/timeout không làm request thất bại.
- Kết quả có schema chung, không trùng URL và được xếp hạng nhất quán.
- Unit test bao phủ validation, lỗi engine và deduplication.
- Không có API key, query history hoặc dữ liệu nhạy cảm bị commit/log vô ý.

Khi đã đạt các điểm trên, đọc lại `searx/search/__init__.py`,
`searx/results.py` và `searx/engines/demo_online.py` để so sánh các trade-off
của bản mini với triển khai production của SearXNG.
