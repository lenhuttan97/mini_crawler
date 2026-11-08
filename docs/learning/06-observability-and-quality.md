# 06 — Quan sát hệ thống và chất lượng code

> Học phần này dạy bạn cách ghi log có mã yêu cầu (correlation ID), theo dõi truy vết (tracing), đo lường số liệu (metrics), viết kiểm thử tự động mà không gọi mạng thật, và duy trì chất lượng mã nguồn bằng Ruff.

---

## Mục tiêu của học phần

- Hiểu tại sao cần logging có cấu trúc và mã liên kết yêu cầu (correlation ID).
- Dùng OpenTelemetry để theo dõi truy vết yêu cầu từ API đến worker và lưu trữ.
- Dùng Prometheus để thu thập số liệu hiệu năng (latency, queue depth, thành công/thất bại crawl/download).
- Viết test đơn vị với pytest và pytest-asyncio.
- Giả lập yêu cầu HTTP bằng respx, không gọi mạng thật trong test đơn vị.
- Dùng Ruff để kiểm tra và định dạng mã nguồn.
- Áp dụng quy trình TDD (Red → Green → Refactor).

---

## Lộ trình năng lực trong bài này

| Mức | Bạn tập trung vào | Khi nào nên đi tiếp? |
|-----|-------------------|----------------------|
| Beginner | Viết log cấu trúc, test nhỏ và chạy Ruff trên mã của chính bạn. | Bạn biết log nào không được chứa secret hay nội dung nhạy cảm. |
| Intermediate | Dùng respx cho HTTP giả lập và tạo trace giữa API với worker. | Bạn xác minh test không gọi mạng thật. |
| Advanced | Thiết kế metrics, retry test và propagation correlation ID xuyên dịch vụ. | Bạn dùng số liệu để tìm lỗi thay vì suy đoán. |
| Master | Đặt alert, dashboard, retention và quy trình phản hồi sự cố. | Bạn cân bằng khả năng quan sát với quyền riêng tư và chi phí. |

Hãy bắt đầu với test và log local. Chỉ export telemetry ra hệ thống dùng chung sau khi đã có redaction, quyền truy cập và retention policy.

---

## 1. Tổng quan: quan sát hệ thống là gì?

Khi hệ thống chạy, bạn cần biết:

- Yêu cầu tìm kiếm nào đang chậm?
- Tác vụ crawl nào bị lỗi?
- Tải video nào bị chặn chính sách?
- Có bao nhiêu tác vụ đang xếp hàng?

Quan sát hệ thống bao gồm ba trụ cột:

| Trụ cột | Ý nghĩa | Ví dụ trong dự án |
|---------|---------|-------------------|
| Logging (ghi log) | Ghi lại sự kiện xảy ra | "Crawl job 123 đã hoàn thành" |
| Tracing (theo dõi truy vết) | Gắn nối sự kiện qua nhiều dịch vụ | Yêu cầu API → Celery → HTTPX → PostgreSQL |
| Metrics (số liệu) | Đếm và đo lường hiệu năng | Số lượng crawl thành công mỗi phút |

---

## 2. structlog — ghi log có cấu trúc

### 2.1 Vấn đề log thuần văn bản

Log thông thường như `"Crawl started"` khó tìm và khó phân tích khi có hàng nghìn dòng. Ghi log có cấu trúc (structured log) giúp bạn lưu mỗi sự kiện dưới dạng đối tượng có các trường rõ ràng.

### 2.2 Cài structlog

```bash
uv add structlog
```

### 2.3 Ví dụ ghi log có mã yêu cầu

```python
import structlog

log = structlog.get_logger()

# Gán mã yêu cầu cho mỗi yêu cầu API. Không log URL đầy đủ nếu có query/token.
log.info(
    "crawl_job_created",
    request_id="req-abc-123",
    job_id=42,
    url_host="example.com",
    status="pending",
)
```

Kết quả log có thể là JSON:

```json
{
  "event": "crawl_job_created",
  "level": "info",
  "request_id": "req-abc-123",
  "job_id": 42,
  "url_host": "example.com",
  "status": "pending",
  "timestamp": "2026-11-07T08:00:00Z"
}
```

### 2.3 Các trường không được ghi vào log

- Mật khẩu, token, khóa API.
- Cookie, header `Authorization`.
- Token ký trong URL.
- Nội dung phản hồi mạng thô (raw network body).
- Nội dung nhạy cảm của người dùng.

---

## 3. OpenTelemetry — theo dõi truy vết (tracing)

### 3.1 OpenTelemetry là gì?

OpenTelemetry là tiêu chuẩn mở để tạo và thu thập dữ liệu quan sát (tracing, metrics, logs). Nó giúp bạn theo dõi một yêu cầu đi qua nhiều dịch vụ.

### 3.2 Tại sao cần tracing trong mini crawler?

Một yêu cầu tải video trải qua nhiều bước:

```
API nhận yêu cầu
     │
     ▼
Tạo công việc vào hàng chờ Celery
     │
     ▼
Worker xử lý (Playwright/yt-dlp)
     │
     ▼
Lưu tệp vào MinIO
     │
     ▼
Cập nhật trạng thái vào PostgreSQL
```

Nếu bước nào bị lỗi, tracing giúp bạn biết chính xác bước nào và tại sao.

### 3.3 Cài OpenTelemetry Python

```bash
uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### 3.4 Ví dụ tạo span (khung theo dõi)

```python
from opentelemetry import trace

tracer = trace.get_tracer("mini-crawler")

with tracer.start_as_current_span("crawl_page") as span:
    # Chỉ ghi giá trị đã redaction; URL đầy đủ có thể chứa query/token.
    span.set_attribute("url.host", "example.com")
    span.set_attribute("job_id", 42)
    # Thực hiện crawl tại đây
```

Mỗi span có thể ghi nhận thời gian bắt đầu, kết thúc, thuộc tính và lỗi.

---

## 4. Prometheus — thu thập số liệu hiệu năng

### 4.1 Prometheus là gì?

Prometheus là hệ thống giám sát và báo hiệu (alerting) mã nguồn mở. Nó thu thập số liệu số (metrics) từ ứng dụng và cho bạn tạo biểu đồ, cảnh báo.

### 4.2 Số liệu đề xuất cho mini crawler

| Số liệu | Loại | Ý nghĩa |
|---------|------|---------|
| `search_requests_total` | Counter | Tổng số yêu cầu tìm kiếm |
| `crawl_jobs_total{status}` | Counter | Tổng số công việc crawl theo trạng thái |
| `media_jobs_total{media_type}` | Counter | Tổng số công việc tải media theo loại |
| `crawl_http_duration_seconds` | Histogram | Thời gian gọi HTTP khi crawl |
| `browser_memory_bytes` | Gauge | Bộ nhớ trình duyệt đang dùng |
| `queue_size` | Gauge | Số lượng công việc đang xếp hàng |
| `llm_token_cost_total` | Counter | Tổng chi phí token LLM |

### 4.3 Cài Prometheus client cho Python

```bash
uv add prometheus-client
```

### 4.4 Ví dụ tạo counter

```python
from prometheus_client import Counter, generate_latest

SEARCH_REQUESTS = Counter("search_requests_total", "Tổng số yêu cầu tìm kiếm")

# Mỗi khi có yêu cầu tìm kiếm
SEARCH_REQUESTS.inc()
```

### 4.5 Xem số liệu

Ứng dụng có thể mở endpoint `/metrics` để Prometheus thu thập. Chỉ mở endpoint này khi đã có xác thực hoặc chỉ truy cập từ mạng nội bộ.

---

## 5. pytest và pytest-asyncio — viết kiểm thử

### 5.1 pytest là gì?

pytest là thư viện kiểm thử Python phổ biến, giúp bạn viết test đơn giản và mở rộng.

### 5.2 pytest-asyncio

Vì mini crawler dùng code bất đồng bộ (async/await), bạn cần pytest-asyncio để chạy test cho các hàm async.

```bash
uv add --group dev pytest pytest-asyncio
```

### 5.3 Ví dụ test đơn giản

```python
import pytest

def test_tong_hai_so():
    assert 1 + 1 == 2

@pytest.mark.asyncio
async def test_ham_async():
    x = await some_async_function()
    assert x == 10
```

---

## 6. respx — giả lập yêu cầu HTTP mà không gọi mạng thật

### 6.1 Tại sao cần respx?

Trong test đơn vị, bạn không nên gọi SearXNG, trang web thật hoặc tải video thật vì:

- Test sẽ chậm.
- Test sẽ thất bại khi mạng bị gián đoạn.
- Bạn có thể vô tình quá tải trang web mục tiêu.

respx giúp bạn giả lập phản hồi HTTP trong test.

### 6.2 Cài respx

```bash
uv add --group dev respx
```

### 6.3 Ví dụ giả lập SearXNG

```python
import respx
import httpx
import pytest

@pytest.mark.asyncio
@respx.mock
async def test_search_searxng():
    route = respx.get("http://127.0.0.1:8080/search").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"title": "Kết quả 1", "url": "https://example.com", "content": "Nội dung mẫu"}]},
        )
    )

    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8080/search", params={"q": "test", "format": "json"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
```

### 6.4 Giả lập lỗi

```python
@respx.mock
async def test_search_timeout():
    route = respx.get("http://127.0.0.1:8080/search").mock(side_effect=httpx.TimeoutException("Timeout"))

    # Kiểm tra code xử lý timeout đúng cách
    ...
```

---

## 7. Ruff — kiểm tra và định dạng mã nguồn

### 7.1 Ruff là gì?

Ruff là công cụ kiểm tra lỗi (linter) và định dạng mã (formatter) Python cực nhanh. Nó thay thế nhiều công cụ như flake8, Black, isort.

### 7.2 Cài Ruff

```bash
uv add --group dev ruff
```

### 7.3 Chạy Ruff

```bash
# Kiểm tra lỗi
uv run ruff check .

# Định dạng mã
uv run ruff format .
```

### 7.4 Chạy Ruff trước khi commit

Hãy thêm Ruff vào quy trình làm việc trước khi commit mã nguồn, nhưng không bỏ qua lỗi do kiểu định dạng gây khó hiểu trong logic bất đồng bộ.

---

## 8. Quy trình TDD (Test-Driven Development)

Dự án tuân thủ quy trình:

1. **Red:** Viết test trước, chạy thấy test thất bại vì chưa có code.
2. **Green:** Viết code tối thiểu để test pass.
3. **Refactor:** Dọn dẹp mã nguồn, giữ test vẫn pass.

Không bao giờ viết code production trước khi có test thất bại.

---

## 9. Bài thực hành

### Bài 1: Ghi log có mã yêu cầu

1. Cài `structlog`.
2. Viết middleware (hoặc hàm hỗ trợ) gán `request_id` cho mỗi yêu cầu API.
3. Ghi log khi tạo công việc crawl và khi tạo công việc tải media.
4. Kiểm tra log không chứa mật khẩu, token hay cookie.

### Bài 2: Tạo span tracing

1. Cài OpenTelemetry Python.
2. Tạo span cho yêu cầu tìm kiếm từ API đến SearXNG.
3. Tạo span cho tác vụ Celery từ lúc nhận công việc đến khi hoàn thành.
4. Kiểm tra mã yêu cầu (correlation ID) được truyền qua các span.

### Bài 3: Số liệu Prometheus

1. Cài `prometheus-client`.
2. Tạo counter cho số lượng yêu cầu tìm kiếm và công việc crawl theo trạng thái.
3. Tạo histogram cho thời gian gọi HTTP khi crawl.
4. Mở endpoint `/metrics` và xem số liệu ra sao.

### Bài 4: Viết test với respx

1. Viết test Red cho hàm gọi SearXNG (test sẽ fail vì chưa có hàm).
2. Dùng respx giả lập phản hồi JSON từ SearXNG.
3. Viết code tối thiểu để test pass (Green).
4. Viết thêm test cho trường hợp lỗi timeout và HTTP 429.

### Bài 5: Dùng Ruff

1. Chạy `ruff check` trên toàn bộ mã nguồn mới viết.
2. Chạy `ruff format` để định dạng mã.
3. Sửa các lỗi Ruff phát hiện trước khi chuyển sang bài sau.

---

## 10. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Ghi log có cấu trúc, viết test đơn giản với pytest, chạy Ruff check/format. |
| Intermediate | Tạo span OpenTelemetry, dùng respx giả lập HTTP, viết test async với pytest-asyncio. |
| Advanced | Thiết kế hệ thống metrics Prometheus, viết test cho lỗi mạng và retry, tối ưu tracing cross-service. |
| Master | Xây dựng dashboard giám sát, thiết lập cảnh báo (alert), tối ưu hiệu năng dựa trên số liệu thực. |

---

## 11. Liên kết tài liệu chính thức

- [structlog documentation](https://www.structlog.org/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry Python API reference](https://opentelemetry-python.readthedocs.io/)
- [OpenTelemetry tracing instrumentation](https://opentelemetry.io/docs/instrumentation/python/)
- [Prometheus documentation](https://prometheus.io/docs/introduction/overview/)
- [Prometheus OpenTelemetry guide](https://prometheus.io/docs/guides/opentelemetry/)
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/en/stable/)
- [RESPX documentation](https://lundberg.github.io/respx/)
- [Ruff documentation](https://docs.astral.sh/ruff/)

---

## 12. Ranh giới bảo mật trong quan sát

- Không ghi token, cookie, secret vào log hay metrics.
- Không expose endpoint `/metrics` công khai nếu chưa có xác thực.
- Không lưu phản hồi mạng thô (raw network body) vào log.
- Ghi nhật ký kiểm tra (audit log) cho việc tạo công việc và trạng thái thay đổi, nhưng không ghi nội dung nhạy cảm.

---

**Bạn đã hoàn tất toàn bộ 6 học phần của bộ tài liệu học Mini Crawler. Hãy quay lại [`../mini_crawler_implementation_plan.md`](../mini_crawler_implementation_plan.md) để bắt đầu triển khai MVP theo từng giai đoạn (Phase 0 → Phase 6).**
