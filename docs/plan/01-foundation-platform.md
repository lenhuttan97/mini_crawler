# P00 — Foundation Platform

> **Mục tiêu:** dựng nền kỹ thuật có thể chạy local, kiểm thử và quan sát được trước khi tạo bất kỳ crawler/downloader nào.  
> **Dependency:** không có.  
> **Đầu ra:** API skeleton, config an toàn, local stack, CI và telemetry tối thiểu.

## 1. Yêu cầu

- Python 3.12 và `uv`; dependency được lock trong `uv.lock`.
- FastAPI có `/health/live` và `/health/ready` không lộ secret/upstream detail.
- Config đọc từ environment; chỉ commit `.env.example`, không commit `.env`.
- Docker Compose local cho API, PostgreSQL, Redis, MinIO, SearXNG; cổng bind local và credential mẫu chỉ dùng development.
- Có pytest, pytest-asyncio, respx, Ruff và CI chạy test/lint/format check.
- Structured log có correlation ID và redaction mặc định.

## 2. Work breakdown

| # | Hạng mục | Chi tiết | Done khi |
|---|---|---|---|
| 1 | Bootstrap | Khởi tạo `pyproject.toml`, package layout, `uv.lock`, `.gitignore`. | Cài đặt tái lập được. |
| 2 | Settings | `Settings` typed, profile local/test/prod, validation required secret. | Production fail-fast khi thiếu config. |
| 3 | API skeleton | App factory, router health, exception envelope/OpenAPI metadata. | Health test pass. |
| 4 | Local infra | Compose, volume, mạng nội bộ, `.env.example`, startup notes. | Các service local có health check. |
| 5 | Quality | pytest/respx/ruff/pre-commit hoặc CI workflow. | CI chạy độc lập, không gọi Internet. |
| 6 | Telemetry base | Correlation ID middleware, JSON log, redaction processor, trace bootstrap. | Request log không chứa secret/query token. |

## 3. Test plan

- Unit: settings precedence, missing production setting, redaction processor.
- API: live/ready response và error envelope.
- Integration local: PostgreSQL/Redis/MinIO health readiness bằng fixture do team kiểm soát.
- CI: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.

## 4. Rủi ro và quyết định

| Rủi ro | Mitigation |
|---|---|
| Secret bị commit | `.env` ignore, secret scan và `.env.example` không có giá trị thật. |
| Compose local bị dùng cho production | Gắn cảnh báo, pin image/digest và dùng secret manager khi deploy. |
| Log lộ token | Redaction allowlist/denylist, test log output. |

## 5. Definition of Done

- [x] Local stack start/stop được bằng tài liệu tái lập (`docker-compose.yml`, `.env.example`, `STARTUP.md`, `Dockerfile.local`).
- [x] Health API, config và redaction có test pass (`tests/unit/test_health.py`, `tests/unit/test_settings.py`, `tests/unit/test_telemetry.py`).
- [x] CI/lint/format chạy (`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` đều pass); tests không gọi mạng thật.
- [x] Không có credential thật trong repo/log/mẫu config (`.env.example` chỉ có giá trị mẫu, `.env` được git-ignore).
