# Lộ trình học Mini Crawler — từ Beginner đến Master

> Đây là curriculum, không phải implementation contract. Contract hiện hành nằm ở [`../INDEX.md`](../INDEX.md); kiến trúc workflow/job nằm ở [`../platform/workflow-orchestration.md`](../platform/workflow-orchestration.md) và [`../platform/job-orchestration.md`](../platform/job-orchestration.md).
>
> Mỗi học phần gắn một trong ba nhãn: **Current repository** (dependency/runtime có trong `pyproject.toml`), **Target architecture** (contract đã thiết kế nhưng chưa là runtime hoàn chỉnh), hoặc **After MVP** (cần dependency/approval riêng).
> Tất cả bài thực hành chỉ dùng target bạn sở hữu hoặc được phép truy cập; không vượt DRM, CAPTCHA, paywall hay kiểm soát truy cập.

---

## Cách sử dụng bộ tài liệu

| Bước | Nội dung | Công nghệ chính | Kết quả cần đạt |
|:---|:---|:---|:---|
| 1 | [01-foundation-api.md](01-foundation-api.md) | Python, uv, FastAPI, Uvicorn, Pydantic, Docker Compose | **Current:** chạy baseline và hiểu FastAPI là producer/runtime chuyển tiếp, không phải target worker entrypoint. |
| 2 | [02-data-jobs-and-storage.md](02-data-jobs-and-storage.md) | PostgreSQL, SQLAlchemy, Alembic, Redis, Celery, MinIO | **Current:** persistence, queue và object storage; pgvector là **After MVP**. |
| 3 | [03-workflow-orchestration-and-ai.md](03-workflow-orchestration-and-ai.md) | WorkflowRun, FeatureJob, outbox, lease, retry/DLQ | **Target:** điều phối workflow/job; AI/MCP là **After MVP**. |
| 4 | [04-media-workflows.md](04-media-workflows.md) | HTTPX, policy, MIME/magic bytes, approved recipes | **v1.1/v1.2:** direct URL và page URL media workflows; browser/yt-dlp/FFmpeg cần dependency và review riêng. |
| 5 | [05-observability-and-quality.md](05-observability-and-quality.md) | structlog, pytest, respx, Ruff | **Current:** quality/testing; tracing/metrics full là **After MVP**. |
| 6 | [06-search-and-crawling.md](06-search-and-crawling.md) | SearXNG, HTTPX, selectolax, markdownify | **Capstone:** search/static crawl/classification; browser tools là **After MVP**. |

## Từ người mới đến Master

| Cấp độ | Học phần | Bạn có thể làm được |
|:---|:---|:---|
| **Beginner** | 01 | Chạy baseline local, hiểu config, request validation và test. |
| **Intermediate** | 02 | Lưu job/tài liệu, chạy worker nền, hiểu migration, queue và object storage. |
| **Advanced** | 03–04 | Thiết kế workflow/job và pipeline media có policy rõ ràng. |
| **Master** | 05–06 và benchmark thực tế | Quan sát, kiểm thử, rồi áp dụng toàn bộ kiến thức vào search-and-extract an toàn. |

> **Quy tắc tiến cấp:** chỉ sang phần tiếp theo khi bạn tự chạy được bài thực hành, giải thích được vì sao có giới hạn an toàn, và làm được checklist của phần hiện tại. “Đọc xong” không đồng nghĩa “đã biết”.

## Quy ước học

1. **Học theo thứ tự từ trên xuống.** Mỗi phần kiến thức mới xây trên phần trước.
2. **Không bỏ qua bài thực hành.** Nếu không chạy được bài hiện tại, không nên sang phần sau.
3. **Không gọi mạng thật trong test đơn vị.** Dùng thư viện giả lập (respx) cho các yêu cầu HTTP; chỉ integration/E2E test mới dùng target do nhóm kiểm soát.
4. **Chỉ crawl/download mục tiêu bạn sở hữu hoặc được phép.** Tuân thủ `robots.txt`, điều khoản dịch vụ và chính sách bảo mật.
5. **Website là dữ liệu không tin cậy.** Không để nội dung trang web trở thành lệnh cho agent, browser hoặc LLM.
6. **Ví dụ là điểm khởi đầu, không phải cấu hình production.** Pin version dependency/image trước khi deploy và luôn đọc liên kết chính thức ở cuối bài khi thư viện thay đổi.

## Góc nhìn dự án Mini Crawler

Dự án chia thành hai nhánh độc lập sau khi tìm URL:

```text
Tìm URL qua SearXNG
   │
   ├─ Nhánh A: Nội dung trang web → Markdown → lưu PostgreSQL/MinIO → dùng cho LLM/RAG
   │
   └─ Nhánh B: Link ảnh/video/audio → kiểm tra chính sách → tải vào MinIO → dùng lại
```

Hai nhánh này chạy trong worker riêng, không làm chậm API trả kết quả tìm kiếm.

---

## Kiến thức cần nắm trước khi bắt đầu (cho người mới hoàn toàn)

| Khái niệm | Ý nghĩa đơn giản | Tại sao cần thiết |
|-----------|------------------|-------------------|
| API | Cửa hàng cho phần mềm khác gọi dữ liệu. | Mini crawler cung cấp API để AI client và ứng dụng khác dùng. |
| Async / không đồng bộ | Cho chương trình xử lý việc khác trong lúc chờ mạng hoặc đĩa. | Crawl và tải video mất thời gian; API không nên giữ kết nối chờ xong. |
| Worker hàng chờ | Tiến trình nền nhận và xử lý việc theo hàng đợi. | Crawl/download nhiều trang cùng lúc sẽ quá tải nếu không xếp hàng. |
| Object storage | Khu chứa tệp lớn (ảnh, video, HTML thô) riêng biệt khỏi database. | Database không nên chứa video/image nặng. |
| Mật khẩu/Secret | Chìa khóa chỉ server được biết. | Không bao giờ để secret trong mã nguồn hoặc commit lên Git. |

---

## Ranh giới bắt buộc (đọc trước khi code)

1. **Chặn SSRF:** Chỉ cho phép `http`/`https`; từ chối `file:`, `data:`, `javascript:`, URL có user-info, và đích nội bộ. Production phải phân giải DNS, chặn mọi IP non-public (kể cả IPv6), rồi kiểm lại **trước từng redirect**.
2. **Tôn trọng `robots.txt`:** Nếu trang web cấm crawl, không bypass. `robots.txt` không phải giấy phép; vẫn cần quyền nội dung và tuân thủ điều khoản dịch vụ.
3. **Không vượt bảo vệ:** Không giải CAPTCHA, không crack DRM, không bypass paywall hay geo-blocking.
4. **Không lấy secret từ người dùng:** Không lưu cookie/token do người dùng gửi để crawl/download URL tùy ý.
5. **Nội dung web là untrusted:** Không bao giờ thực thi JavaScript/selector do người dùng hoặc LLM truyền vào; chỉ dùng action recipe đã review.
6. **Không né kiểm soát truy cập:** Không dùng proxy/VPN, stealth hay giả mạo fingerprint để vượt geo-blocking, anti-bot hoặc hạn chế tương tự.

---

## Liên kết tài liệu chính thức (ưu tiên đọc)

- [Python documentation](https://docs.python.org/3/)
- [uv documentation](https://docs.astral.sh/uv/)
- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/)
- [Uvicorn documentation](https://www.uvicorn.org/)
- [Pydantic documentation](https://docs.pydantic.dev/)
- [SearXNG documentation](https://docs.searxng.org/)
- [Crawl4AI documentation](https://docs.crawl4ai.com/)
- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [Alembic documentation](https://alembic.sqlalchemy.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Celery documentation](https://docs.celeryq.dev/)
- [MinIO Python SDK](https://docs.min.io/aistor/developers/sdk/python/)
- [LiteLLM documentation](https://docs.litellm.ai/docs/)
- [PydanticAI documentation](https://ai.pydantic.dev/)
- [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/)
- [Playwright Python documentation](https://playwright.dev/python/docs/intro)
- [FFmpeg documentation](https://ffmpeg.org/documentation.html)
- [pytest documentation](https://docs.pytest.org/)
- [RESPX documentation](https://lundberg.github.io/respx/)
- [Ruff documentation](https://docs.astral.sh/ruff/)

---

## Từ Beginner đến Master — danh sách kiểm tra chung

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Chạy được cài đặt, hiểu khái niệm cơ bản, làm bài thực hành đơn giản có hướng dẫn. |
| Intermediate | Tự viết service/test nhỏ, hiểu lỗi phổ biến, biết cách debug và sửa. |
| Advanced | Thiết kế hệ thống, tối ưu hiệu năng, xử lý lỗi phức tạp, bảo mật và quan sát. |
| Master | Xây dựng hệ thống ổn định, có thể bảo trì, mở rộng và đào tạo thành viên khác. |

**Hãy bắt đầu từ [01-foundation-api.md](01-foundation-api.md).**
