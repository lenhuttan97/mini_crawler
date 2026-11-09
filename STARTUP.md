# Local Development — Mini Crawler

> This Compose stack starts the current API-centric development baseline: `api`, PostgreSQL, Redis, MinIO and SearXNG. It does **not** by itself start or validate the target worker-first workflow architecture described in [docs/INDEX.md](docs/INDEX.md).

Prerequisites: `uv` (installed), Docker + Docker Compose.

## 1. Configure environment

```bash
cp .env.example .env
# Edit .env if you want different dev credentials. Never commit .env.
```

## 2. Start the current local stack

```bash
docker compose up --build
```

This builds the `api` image and starts `postgres`, `redis`, `minio`, `searxng`, and `api`. Docker images must be available locally or pullable from their registries.

## 3. Verify the current services are healthy

```bash
docker compose ps
```

Every service should report `healthy`. Individual checks:

| Service | Check |
|---------|-------|
| postgres | `docker compose exec postgres pg_isready -U minicrawler -d minicrawler` |
| redis | `docker compose exec redis redis-cli ping` |
| minio | `curl -f http://127.0.0.1:9000/minio/health/live` |
| searxng | `curl -f http://127.0.0.1:8080/` |
| api | `curl -f http://127.0.0.1:8000/health/live` → `{"status":"live"}` |

API health endpoints: `GET /health/live`, `GET /health/ready`.

Passing these checks confirms only the current Compose services. For target workflow contracts, queues, policy boundaries and runbooks, use [docs/INDEX.md](docs/INDEX.md).

## 4. Stop the stack

```bash
docker compose down
```

## 5. Run the quality gate (offline, no network)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
