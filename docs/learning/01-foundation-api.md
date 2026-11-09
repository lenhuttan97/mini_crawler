# 01 — Python, uv và API Foundation

> **Status: Current repository.** Python 3.12, uv, Pydantic, FastAPI, Uvicorn và Docker Compose có trong baseline hiện tại. FastAPI là runtime/producer boundary chuyển tiếp; kiến trúc đích chạy workflow và worker không đặt HTTP controller trong worker repository. Xem [`../INDEX.md`](../INDEX.md).

> Học phần này dành cho người chưa biết Python hoặc biết ít về xây dựng API. Sau khi hoàn thành, bạn có thể chạy một API an toàn, có kiểm tra sức khỏe và cấu hình không để lộ mật khẩu.

---

## Mục tiêu của học phần

- Hiểu Python là gì và tại sao dự án chọn Python 3.12.
- Cài đặt và quản lý thư viện bằng `uv` (không cài thủ công rắc rỗi).
- Xây dựng API đầu tiên bằng FastAPI.
- Chạy API bằng Uvicorn.
- Xác thực dữ liệu nhập vào bằng Pydantic.
- Quản lý cấu hình bằng `pydantic-settings`.
- Chuẩn bị chạy đa dịch vụ bằng Docker Compose.
- Viết test đơn giản và không bỏ qua kiểm tra an toàn.

## Cách học nếu bạn hoàn toàn mới

Với mỗi ví dụ, hãy làm theo bốn nhịp: **đọc → gõ lại → chạy → tự thay đổi một giá trị rồi chạy lại**. Đừng copy toàn bộ mà chưa hiểu lỗi nào xuất hiện khi bạn gõ sai.

| Sau khi xong | Bạn cần tự trả lời được |
|---|---|
| Beginner | API là gì, `uv run` làm gì, endpoint nhận/trả dữ liệu thế nào? |
| Intermediate | Vì sao schema, cấu hình và test phải tách khỏi endpoint? |
| Advanced | Khi nào dùng `lifespan`, biến môi trường và Docker Compose để quản lý tài nguyên? |

---

## 1. Python — ngôn ngữ lập trình của dự án

### 1.1 Python là gì?

Python là ngôn ngữ lập trình cho máy tính hiểu lệnh của con người bằng cú pháp gần ngôn ngữ tự nhiên. Nó được dùng rộng rãi trong trí tuệ nhân tạo, trích xuất dữ liệu web và xây dựng API.

### 1.2 Tại sao dự án dùng Python 3.12?

- Crawl4AI yêu cầu Python >= 3.10.
- yt-dlp yêu cầu Python >= 3.11.
- Python 3.12 đủ mới, hỗ trợ các tính năng typing hiện đại và ổn định cho production.

### 1.3 Khái niệm cơ bản cần nắm

| Khái niệm | Ý nghĩa đơn giản | Ví dụ trong dự án |
|-----------|------------------|-------------------|
| Biến | Tên gán cho một giá trị để dùng lại. | `app_name = "mini-crawler"` |
| Hàm | Khối lệnh thực hiện một việc nhất định. | Hàm tính toán hash của nội dung trang web. |
| Lớp (Class) | Mẫu tạo đối tượng có dữ liệu và hành vi. | Lớp `SearchService` quản lý việc tìm kiếm. |
| Import | Gọi thư viện khác đã viết sẵn. | `import httpx` để gọi trang web khác. |
| Async / await | Làm việc khác trong khi chờ phản hồi từ mạng. | Gọi SearXNG mà không làm treo toàn bộ API. |

### 1.4 Cách kiểm tra Python đã cài chưa

Mở terminal và gõ:

```bash
python3 --version
```

Nếu thấy `Python 3.12.x` là ổn. Nếu chưa có, hãy cài Python 3.12 từ trang chủ hoặc dùng trình quản lý phiên bản (ví dụ `pyenv`).

---

## 2. uv — công cụ quản lý môi trường và thư viện

### 2.1 Vấn đề uv giải quyết

Khi bạn viết dự án Python, bạn thường cài nhiều thư viện (FastAPI, Pydantic, HTTPX…). Nếu cài nhiều thư viện khác nhau vào cùng một nơi, chúng có thể xung đột về phiên bản. `uv` giúp:

- Tạo môi trường riêng cho dự án (virtual environment).
- Cài đặt thư viện nhanh.
- Khóa phiên bản chính xác trong `uv.lock` để mọi người cài giống hệt nhau.

### 2.2 Cài uv

Tùy hệ điều hành, bạn có thể cài uv theo hướng dẫn tại [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/). Sau khi cài, kiểm tra:

```bash
uv --version
```

### 2.3 Khởi tạo dự án Python bằng uv

Trong thư mục dự án:

```bash
uv init mini-crawler
cd mini-crawler
```

Lệnh này tạo các tệp cần thiết, bao gồm `pyproject.toml` — nơi khai báo thư viện dự án cần dùng.

### 2.4 Thêm thư viện

Ví dụ thêm FastAPI:

```bash
uv add fastapi uvicorn pydantic pydantic-settings
```

`uv` sẽ cập nhật `pyproject.toml` và `uv.lock`. **Không chỉnh tay `uv.lock`**; hãy để `uv` quản lý. Khi deploy, commit lockfile để môi trường cài đúng phiên bản đã kiểm thử.

### 2.5 Chạy lệnh trong môi trường dự án

```bash
uv run python main.py
uv run pytest
```

---

## 3. FastAPI — xây dựng API web

### 3.1 FastAPI là gì?

FastAPI là thư viện Python giúp bạn xây dựng API nhanh, hiện đại và tự động tạo tài liệu (Swagger UI). Nó dùng type hints của Python để kiểm tra dữ liệu đầu vào và đầu ra.

### 3.2 Tạo API đầu tiên

Tạo tệp `app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Mini Crawler API")

@app.get("/")
def read_root():
    return {"message": "Chào mừng đến với Mini Crawler"}
```

Chạy bằng Uvicorn:

```bash
uv run uvicorn app.main:app --reload
```

Mở trình duyệt tại `http://127.0.0.1:8000/docs` bạn sẽ thấy tài liệu API tự động sinh ra.

### 3.3 Giải thích code trên

| Dòng code | Ý nghĩa |
|-----------|---------|
| `from fastapi import FastAPI` | Nhập thư viện FastAPI. |
| `app = FastAPI(...)` | Tạo đối tượng ứng dụng API. |
| `@app.get("/")` | Báo cho FastAPI biết: khi có yêu cầu GET đến đường dẫn `/`, chạy hàm dưới đây. |
| `def read_root():` | Hàm xử lý yêu cầu, trả về đối tượng Python (FastAPI tự chuyển thành JSON). |

### 3.4 Tại sao dùng `--reload`?

Chỉ dùng ở phát triển (development). Khi bạn sửa code, server sẽ khởi động lại tự động. **Không dùng `--reload` khi triển khai thực tế (production)** vì làm chậm và kém bảo mật.

---

## 4. Uvicorn — máy chủ chạy API

### 4.1 Uvicorn là gì?

FastAPI chỉ định nghĩa logic API, còn cần một máy chủ để lắng nghe yêu cầu từ trình duyệt hoặc ứng dụng khác. Uvicorn là máy chủ ASGI phổ biến cho Python.

### 4.2 Cách chạy

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- `app.main:app` nghĩa là: vào tệp `app/main.py`, lấy đối tượng tên `app`.
- `--host 0.0.0.0` cho phép truy cập từ các thiết bị trong cùng mạng (chỉ dùng khi cần thiết).
- `--port 8000` là cổng giao tiếp.

---

## 5. Pydantic — xác thực dữ liệu

### 5.1 Vấn đề Pydantic giải quyết

Khi client gửi dữ liệu đến API (ví dụ JSON), bạn cần kiểm tra dữ liệu đúng kiểu, không thiếu trường bắt buộc và nằm trong giới hạn hợp lý. Pydantic giúp định nghĩa mô hình dữ liệu và tự động kiểm tra các ràng buộc này.

> **Giới hạn cần nhớ:** Pydantic không phải tường lửa. Validation không thay thế authentication, authorization, kiểm tra SSRF, escape output hay policy nghiệp vụ.

### 5.2 Ví dụ mô hình tìm kiếm

Tạo `app/schemas/search.py`:

```python
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=10, ge=1, le=50)

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""

class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]
```

### 5.3 Dùng trong FastAPI

```python
from fastapi import FastAPI
from app.schemas.search import SearchRequest, SearchResponse

app = FastAPI()

@app.post("/api/v1/search", response_model=SearchResponse)
def search(request: SearchRequest):
    return SearchResponse(
        query=request.query,
        total=0,
        results=[],
    )
```

Nếu client gửi `limit` là 1000 (vượt quá 50), FastAPI sẽ tự động trả lỗi 422 với thông báo rõ ràng. Bạn không cần viết code kiểm tra thủ công.

---

## 6. pydantic-settings — quản lý cấu hình

### 6.1 Tại sao không để cấu hình trong mã nguồn?

Mật khẩu, URL server, cổng kết nối, khóa API không nên viết trực tiếp trong tệp Python. Nếu bạn commit mã nguồn lên Git, mọi người đều thấy mật khẩu.

### 6.2 Dùng pydantic-settings

Tạo `app/core/config.py`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Mini Crawler"
    app_version: str = "0.1.0"
    debug: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Tạo `.env.example`:

```dotenv
APP_NAME=Mini Crawler
APP_VERSION=0.1.0
DEBUG=false
```

Trong code, bạn dùng `get_settings().app_name` thay vì viết cứng `"Mini Crawler"`.

**Quan trọng:** Không commit tệp `.env` chứa giá trị thật. Chỉ commit `.env.example`.

---

## 7. Docker Compose — chạy nhiều dịch vụ cùng lúc

### 7.1 Vấn đề

Mini crawler không chỉ có API. Nó cần PostgreSQL, Redis, SearXNG, MinIO… Nếu bạn cài từng dịch vụ một trên máy, rất dễ làm sai và khó chia sẻ cho đồng nghiệp.

### 7.2 Docker Compose là gì?

Docker Compose cho phép bạn khai báo tất cả dịch vụ trong một tệp `docker-compose.yml` và khởi chạy cùng lúc bằng một lệnh.

Ví dụ dưới đây chỉ dành cho local development. Production phải pin image version/digest và truyền password/secret bằng cơ chế quản lý secret phù hợp, không ghi giá trị thật vào Compose hoặc Git.

Ví dụ đơn giản (chỉ API):

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_NAME=Mini Crawler
    depends_on: []
```

Chạy:

```bash
docker compose up -d
```

Sau khi hiểu phần này, bạn sẽ thêm PostgreSQL, Redis, SearXNG vào cùng tệp này.

---

## 8. Kiểm thử (test) đầu tiên

### 8.1 Viết test cho API

Cài pytest:

```bash
uv add --group dev pytest pytest-asyncio httpx
```

Tạo `tests/test_main.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Chào mừng đến với Mini Crawler"}
```

Chạy test:

```bash
uv run pytest
```

### 8.2 Tại sao viết test trước?

Đây là quy tắc TDD (Test-Driven Development):

1. **Red:** Viết test, chạy thấy test thất bại (vì chưa có code).
2. **Green:** Viết code tối thiểu để test pass.
3. **Refactor:** Dọn dẹp code, giữ test vẫn pass.

---

## 9. Bảo mật ở giai đoạn foundation

- Không để secret trong mã nguồn.
- Không commit `.env` chứa giá trị thật.
- Chỉ cho phép `http`/`https` khi sau này gọi trang web khác.
- Health endpoint (`/health/live`, `/health/ready`) không trả về cấu hình hay secret.

---

## 10. Bài thực hành

### Bài 1: Khởi tạo dự án

1. Cài Python 3.12 và `uv`.
2. Chạy `uv init mini-crawler` trong thư mục học tập.
3. Thêm `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`.
4. Tạo `app/main.py` có endpoint `/` trả JSON chào mừng.
5. Chạy `uv run uvicorn app.main:app --reload` và mở trình duyệt xem kết quả.

### Bài 2: Thêm health check và cấu hình

1. Tạo `app/core/config.py` dùng `pydantic-settings`.
2. Tạo endpoint `GET /health/live` trả về `{"status": "ok"}`.
3. Tạo endpoint `GET /health/ready` trả về `{"status": "ready"}`.
4. Thêm `app_name` từ cấu hình vào phản hồi.
5. Viết test cho cả hai endpoint.

### Bài 3: Xác thực dữ liệu

1. Tạo `app/schemas/health.py` có mô hình `HealthResponse`.
2. Dùng `response_model=HealthResponse` trong endpoint.
3. Thử gửi yêu cầu không hợp lệ và quan sát FastAPI trả lỗi 422.

---

## 11. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Cài được Python, uv, FastAPI; chạy API local; mở Swagger UI được. |
| Intermediate | Viết được Pydantic schema, config từ `.env`, test đơn vị cho API, hiểu lỗi 422. |
| Advanced | Tách config ra module riêng, dùng `lifespan` quản lý tài nguyên, chạy qua Docker Compose. |
| Master | Thiết kế cấu hình multi-environment, tối ưu startup time, viết test tự động cho mọi endpoint foundation. |

---

## 12. Liên kết tài liệu chính thức

- [Python tutorial](https://docs.python.org/3/tutorial/)
- [uv documentation](https://docs.astral.sh/uv/)
- [uv + FastAPI guide](https://docs.astral.sh/uv/guides/integration/fastapi/)
- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/)
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [Pydantic documentation](https://docs.pydantic.dev/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Uvicorn documentation](https://www.uvicorn.org/)
- [Docker Compose documentation](https://docs.docker.com/compose/)
- [pytest documentation](https://docs.pytest.org/)

---

**Khi hoàn thành học phần 01, hãy chuyển sang [02-data-jobs-and-storage.md](02-data-jobs-and-storage.md) để hiểu dữ liệu, queue và object storage trước khi thiết kế workflow.**
