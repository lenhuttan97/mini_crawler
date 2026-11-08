# 03 — Cơ sở dữ liệu, tác vụ nền và lưu trữ tệp

> Học phần này dạy bạn cách lưu trữ dữ liệu crawl, quản lý tác vụ nền (crawl, tải video) và lưu tệp lớn (HTML, Markdown, ảnh, video). Sau khi hoàn thành, bạn có thể xây dựng hệ thống lưu dữ liệu không bị trùng lặp và chạy tác vụ bên ngoài API.

---

## Mục tiêu của học phần

- Hiểu PostgreSQL là cơ sở dữ liệu chính của dự án.
- Dùng SQLAlchemy để thao tác database bằng Python.
- Dùng Alembic để quản lý thay đổi cấu trúc database (migration).
- Dùng pgvector để lưu và tìm kiếm vector (embedding) trong PostgreSQL.
- Dùng Redis và Celery để chạy tác vụ nền mà không làm chậm API.
- Dùng MinIO để lưu trữ tệp lớn (ảnh, video, HTML thô).
- Viết test cho database và tác vụ nền mà không gây tác dụng phụ.

---

## Lộ trình năng lực trong bài này

| Mức | Bạn tập trung vào | Khi nào nên đi tiếp? |
|-----|-------------------|----------------------|
| Beginner | Kết nối PostgreSQL, Redis và MinIO local; hiểu mỗi loại dữ liệu nằm ở đâu. | Bạn không đưa mật khẩu mẫu vào mã nguồn hay Git. |
| Intermediate | Tạo model, migration đã review, Celery task đơn giản và object MinIO. | Bạn hiểu task có thể chạy lại và migration cần kiểm tra trước khi áp dụng. |
| Advanced | Thiết kế schema, retry có chọn lọc, truy vấn vector và job idempotent. | Bạn đo được lỗi, retry và dung lượng lưu trữ. |
| Master | Lập kế hoạch backup/restore, rollout migration và quan sát hệ thống lưu trữ. | Bạn có thể vận hành production mà không dựa vào ví dụ local trong bài. |

Các Compose và credential bên dưới chỉ dành cho local. Dùng secret manager/biến môi trường, pin image version hoặc digest đã review, và không public các cổng dịch vụ khi triển khai.

---

## 1. Tổng quan về lưu dữ liệu trong dự án

Mini crawler có hai loại dữ liệu cần lưu:

| Loại dữ liệu | Nơi lưu | Lý do |
|--------------|---------|-------|
| Thông tin tài liệu, trạng thái job, metadata | PostgreSQL | Cần truy vấn, liên kết và bảo toàn tính nhất quán. |
| Vector nhúng (embedding) của nội dung | PostgreSQL (pgvector) | Tìm kiếm ngữ nghĩa cùng với dữ liệu đã có. |
| Tệp nhị phân (HTML thô, Markdown, ảnh, video) | MinIO (S3-compatible) | Database không nên chứa tệp lớn. |
| Hàng chờ tác vụ và trạng thái ngắn hạn | Redis | Nhanh, tạm thời, phù hợp cho broker Celery. |

Luồng xử lý dữ liệu:

```
Crawl/download thành công
     │
     ▼
Lưu metadata vào PostgreSQL
     │
     ▼
Lưu tệp nhị phân vào MinIO, lưu object key vào PostgreSQL
     │
     ▼
Tạo chunk và embedding (nếu là tài liệu văn bản)
     │
     ▼
Lưu chunk vào PostgreSQL (có pgvector)
```

---

## 2. PostgreSQL — cơ sở dữ liệu chính

### 2.1 PostgreSQL là gì?

PostgreSQL là hệ quản trị cơ sở dữ liệu quan hệ (RDBMS) mã nguồn mở, ổn định, mạnh mẽ và được sử dụng rộng rãi trong doanh nghiệp. Nó lưu dữ liệu dưới dạng bảng có các cột và hàng, tương quan qua khóa chính và khóa ngoại.

### 2.2 Tại sao dự án chọn PostgreSQL?

- Hỗ trợ đầy đủ truy vấn SQL phức tạp.
- Có extension pgvector để lưu vector tìm kiếm ngữ nghĩa.
- ổn định, dễ sao lưu và khôi phục.
- Dễ tích hợp với SQLAlchemy và Alembic.

### 2.3 Chạy PostgreSQL bằng Docker

Trong `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: crawler
      POSTGRES_PASSWORD: mat-khau-de-thay-the
      POSTGRES_DB: crawler_db
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Chạy:

```bash
docker compose up -d postgres
```

### 2.4 Kết nối PostgreSQL bằng Python

Cài driver và SQLAlchemy:

```bash
uv add sqlalchemy psycopg2-binary
```

Ví dụ kết nối đơn giản:

```python
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://crawler:mat-khau-de-thay-the@localhost:5432/crawler_db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT 1"))
    print(result.scalar())  # In ra 1 nếu kết nối thành công
```

**Quan trọng:** Không để mật khẩu trực tiếp trong mã nguồn. Hãy dùng `pydantic-settings` đọc từ biến môi trường (như đã học ở phần 01).

---

## 3. SQLAlchemy — thao tác database bằng Python

### 3.1 SQLAlchemy là gì?

SQLAlchemy là thư viện Python cho phép bạn thao tác database bằng mã Python thay vì viết câu lệnh SQL thô. Nó hỗ trợ cả công-style (Core) và đối tượng-style (ORM).

### 3.2 Định nghĩa bảng dữ liệu

Ví dụ bảng `CrawlJob`:

```python
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase
import enum
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.pending, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
```

### 3.3 Tạo bảng trong database

```python
from sqlalchemy import create_engine
from app.models.base import Base

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
```

Trong production, bạn không dùng `create_all` trực tiếp; hãy dùng Alembic để migration (xem phần sau).

---

## 4. Alembic — quản lý migration database

### 4.1 Vấn đề Alembic giải quyết

Khi bạn thay đổi cấu trúc bảng (thêm cột, đổi kiểu dữ liệu), bạn không thể xóa database và tạo lại vì sẽ mất dữ liệu. Alembic giúp ghi lại từng thay đổi dưới dạng file migration, có thể áp dụng lên database đã có dữ liệu.

### 4.2 Cài Alembic

```bash
uv add alembic
uv run alembic init alembic
```

### 4.3 Tạo migration đầu tiên

Sau khi định nghĩa model SQLAlchemy, chạy:

```bash
uv run alembic revision --autogenerate -m "create crawl_jobs table"
```

Lệnh này sinh file migration trong thư mục `alembic/versions/`. Autogenerate chỉ là bản nháp: bạn phải kiểm tra thủ công constraint, index, dữ liệu cũ và thao tác destructive trước khi áp dụng. Sau đó mới chạy:

```bash
uv run alembic upgrade head
```

### 4.4 Quy tắc quan trọng

- Không chỉnh sửa database production bằng tay.
- Mọi thay đổi cấu trúc phải có file migration và được review code.
- Luôn kiểm tra migration có thể rollback (hoặc ít nhất là không làm hỏng dữ liệu).

---

## 5. pgvector — tìm kiếm vector trong PostgreSQL

### 5.1 pgvector là gì?

pgvector là extension của PostgreSQL cho phép lưu trữ và tìm kiếm vector (danh sách số biểu diễn ý nghĩa của văn bản). Nó giúp bạn tìm các đoạn văn bản có ý nghĩa gần nhau, không chỉ khớp từ khóa.

### 5.2 Tại sao cần pgvector trong mini crawler?

Sau khi crawl trang web, bạn chia nội dung thành các đoạn nhỏ (chunk) và biến mỗi đoạn thành vector bằng mô hình nhúng (embedding). Khi người dùng hỏi câu hỏi, bạn biến câu hỏi thành vector và tìm các đoạn vector gần nhất trong PostgreSQL.

### 5.3 Cài pgvector

Trong Docker, dùng image PostgreSQL đã có pgvector hoặc cài extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Trong SQLAlchemy, bạn có thể dùng thư viện `pgvector` cho Python:

```bash
uv add pgvector
```

Ví dụ lưu vector:

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=True)  # 384 là kích thước vector mẫu
```

---

## 6. Redis — bộ nhớ đệm và broker

### 6.1 Redis là gì?

Redis là hệ thống lưu trữ dữ liệu dạng key-value trong bộ nhớ, chạy rất nhanh. Dự án dùng Redis làm:

- Broker cho Celery (gửi nhận tin nhắn tác vụ).
- Bộ nhớ đệm ngắn hạn (cache kết quả tìm kiếm).
- Trạng thái giới hạn tần suất yêu cầu (rate limiting).

### 6.2 Chạy Redis bằng Docker

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "127.0.0.1:6379:6379"
```

### 6.3 Kết nối Redis bằng Python

```bash
uv add redis
```

```python
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
r.set("my_key", "hello")
print(r.get("my_key"))  # In ra hello
```

---

## 7. Celery — chạy tác vụ nền

### 7.1 Vấn đề Celery giải quyết

API không nên đợi việc crawl trang web hoặc tải video xong mới trả lời khách hàng, vì việc đó có thể mất nhiều giây đến vài phút. Celery giúp đẩy tác vụ này vào hàng chờ, API trả lời ngay, và worker nền xử lý sau.

### 7.2 Cài Celery

```bash
uv add celery
```

### 7.3 Cấu hình Celery

Tạo `app/workers/celery_app.py`:

```python
from celery import Celery

celery_app = Celery(
    "mini_crawler",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

celery_app.conf.task_routes = {
    "app.workers.crawl_tasks.crawl_page": {"queue": "crawl"},
    "app.workers.media_tasks.download_media": {"queue": "media"},
}
```

### 7.4 Ví dụ tác vụ crawl nền

```python
from app.workers.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def crawl_page(self, job_id: int, url: str):
    try:
        # Logic crawl ở đây
        return {"status": "completed", "job_id": job_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### 7.5 Chạy Celery worker

```bash
uv run celery -A app.workers.celery_app worker --loglevel=info
```

### 7.6 Giới hạn quan trọng

- Không chạy crawl/download trực tiếp trong API request handler.
- Mỗi tác vụ nên có trạng thái rõ ràng: `pending → running → completed|failed|blocked_*`.
- Không retry vô hạn; chỉ retry lỗi tạm thời (mạng, timeout), không retry lỗi chính sách (403, từ chối truy cập).

---

## 8. MinIO — lưu trữ đối tượng

### 8.1 MinIO là gì?

MinIO là hệ thống lưu trữ đối tượng tương thích với API S3 của Amazon. Nó dùng để lưu tệp lớn (ảnh, video, HTML thô, Markdown) riêng biệt khỏi database.

### 8.2 Tại sao không lưu tệp trong database?

Database được tối ưu hóa cho truy vấn dữ liệu có cấu trúc, không cho tệp nhị phân lớn. Lưu video vào database sẽ làm chậm sao lưu, sao chép và truy vấn.

### 8.3 Chạy MinIO bằng Docker

```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: mat-khau-de-thay-the
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
    volumes:
      - minio_data:/data

volumes:
  minio_data:
```

### 8.4 Dùng MinIO Python SDK

```bash
uv add minio
```

```python
from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="mat-khau-de-thay-the",
    secure=False,
)

# Tạo bucket một cách idempotent: task có thể chạy lại.
bucket_name = "crawler-assets"
if not client.bucket_exists(bucket_name):
    client.make_bucket(bucket_name)

# Tải tệp lên
client.fput_object(bucket_name, "doc1.md", "/tmp/doc1.md")
```

---

## 9. Mô hình dữ liệu tối thiểu trong dự án

| Bảng | Cột chính | Ý nghĩa |
|------|-----------|---------|
| `crawl_jobs` | id, url, status, attempts, created_at | Theo dõi việc crawl từng URL. |
| `documents` | id, canonical_url, title, content_hash, storage_key | Lưu tài liệu đã chuẩn hóa. |
| `document_chunks` | id, document_id, chunk_index, content, embedding | Đoạn văn bản và vector nhúng. |
| `media_links` | id, document_id, url, media_type, policy_status | Link ảnh/video được phát hiện. |
| `media_download_jobs` | id, media_link_id, media_type, status, progress | Tác vụ tải media. |
| `media_assets` | id, job_id, title, mime_type, byte_size, storage_key | Tệp media đã tải về. |

Ràng buộc quan trọng: `canonical_url` và `content_hash` cần index để tránh crawl/trải nghiệm dữ liệu trùng lặp.

---

## 10. Bảo mật khi lưu dữ liệu

- Không lưu mật khẩu, token, cookie trong database dưới dạng văn bản rõ ràng.
- Không log nội dung nhạy cảm (cookie, authorization header, query ký).
- MinIO bucket nên được bảo vệ, không để công khai nếu chứa dữ liệu nội bộ.
- Chỉ phát presigned URL ngắn hạn cho client được phép tải tệp.

---

## 11. Bài thực hành

### Bài 1: Chạy PostgreSQL và kết nối

1. Khởi động PostgreSQL bằng Docker Compose.
2. Viết script Python kết nối PostgreSQL và chạy `SELECT 1`.
3. Thử sai mật khẩu và quan sát lỗi kết nối.

### Bài 2: Tạo bảng và migration

1. Định nghĩa model `CrawlJob` bằng SQLAlchemy.
2. Chạy `alembic revision --autogenerate` và kiểm tra file migration sinh ra.
3. Chạy `alembic upgrade head` để áp dụng vào database.
4. Kiểm tra bảng `crawl_jobs` đã có trong PostgreSQL.

### Bài 3: Lưu và truy vấn dữ liệu

1. Thêm một bản ghi `CrawlJob` qua SQLAlchemy session.
2. Truy vấn lại và in ra trạng thái job.
3. Cập nhật trạng thái sang `completed` và lưu thời điểm kết thúc.

### Bài 4: Tác vụ nền với Celery

1. Cấu hình Celery dùng Redis làm broker.
2. Viết tác vụ giả lập crawl (in ra log, không gọi mạng thật).
3. Enqueue tác vụ từ Python và chạy Celery worker để xem tác vụ được xử lý.

### Bài 5: Lưu tệp vào MinIO

1. Khởi động MinIO bằng Docker.
2. Viết script tạo bucket và tải một tệp thử nghiệm lên MinIO.
3. Lấy lại thông tin tệp và xác minh tồn tại.

---

## 12. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Chạy được PostgreSQL, Redis, MinIO bằng Docker; kết nối PostgreSQL bằng Python. |
| Intermediate | Viết model SQLAlchemy, migration Alembic, tác vụ Celery đơn giản, lưu tệp MinIO. |
| Advanced | Thiết kế schema đa bảng, xử lý lỗi tác vụ nền, tối ưu truy vấn vector pgvector, idempotent job. |
| Master | Thiết kế hệ thống lưu trữ đa vùng, tối ưu chi phí MinIO, quản lý migration production, giám sát database. |

---

## 13. Liên kết tài liệu chính thức

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [PostgreSQL full-text search](https://www.postgresql.org/docs/current/textsearch.html)
- [SQLAlchemy 2 documentation](https://docs.sqlalchemy.org/)
- [SQLAlchemy PostgreSQL dialect](https://docs.sqlalchemy.org/en/latest/dialects/postgresql.html)
- [Alembic documentation](https://alembic.sqlalchemy.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [pgvector Python](https://github.com/pgvector/pgvector-python)
- [Redis documentation](https://redis.io/docs/latest/)
- [Celery documentation](https://docs.celeryq.dev/)
- [Celery with Redis](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)
- [MinIO Python SDK](https://docs.min.io/aistor/developers/sdk/python/)

---

**Khi hoàn thành học phần 03, hãy chuyển sang [04-llm-agent-and-mcp.md](04-llm-agent-and-mcp.md) để học về trí tuệ nhân tạo và kết nối AI client.**
