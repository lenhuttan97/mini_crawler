# Local Development — Mini Crawler

> This Compose stack starts the current API-centric development baseline: `api`, PostgreSQL, Redis, MinIO and SearXNG. It does **not** by itself start or validate the target worker-first workflow architecture described in [docs/INDEX.md](docs/INDEX.md).

Prerequisites: `uv` (installed). Docker + Docker Compose are required only for the Compose stack below.

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

## Run without Docker (local modes)

These modes run FastAPI with SQLite and a local object directory. They need no Redis/Celery, MinIO or SearXNG. Create the SQLite schema explicitly before the first run; API startup never creates tables.

Prepared env files are provided (git-ignored): `.env.inline` and `.env.db-worker`. Copy one to `.env`, or `export` its variables directly.

### Mode inline — API executes crawl/image work in the request (HTTP 200)

```bash
mkdir -p .runtime .runtime/objects
cp .env.inline .env

uv run python -m app.entrypoints.local_bootstrap
uv run uvicorn app.legacy_api.main:create_app --factory --reload
```

Or without copying:

```bash
mkdir -p .runtime .runtime/objects
set -a; . .env.inline; set +a
uv run python -m app.entrypoints.local_bootstrap
uv run uvicorn app.legacy_api.main:create_app --factory --reload
```

`inline` waits for crawl/image work to finish before responding, so it returns `200` with the persisted terminal status and can hit HTTP timeouts on slow remote work.

### Mode db-worker — API persists jobs (HTTP 202); a separate worker executes them

Terminal 1 — API:

```bash
mkdir -p .runtime .runtime/objects
cp .env.db-worker .env

uv run python -m app.entrypoints.local_bootstrap
uv run uvicorn app.legacy_api.main:create_app --factory --reload
```

Terminal 2 — exactly one worker process (same database + storage path as the API):

```bash
mkdir -p .runtime .runtime/objects
cp .env.db-worker .env

uv run python -m app.entrypoints.database_worker
```

Or without copying:

```bash
# Terminal 1: API
mkdir -p .runtime .runtime/objects
set -a; . .env.db-worker; set +a
uv run python -m app.entrypoints.local_bootstrap
uv run uvicorn app.legacy_api.main:create_app --factory --reload

# Terminal 2: worker
mkdir -p .runtime .runtime/objects
set -a; . .env.db-worker; set +a
uv run python -m app.entrypoints.database_worker
```

`db-worker` returns `202` with a pending job. Run exactly one worker process: it has no lease, outbox, retry or DLQ guarantee, and concurrent workers are unsupported. Use `APP_LOCAL_WORKER_POLL_SECONDS` to change its idle poll interval (default `1.0`).

Local modes disable Search by default. To enable it, set `APP_SEARCH_ENABLED=true` and point `SEARXNG_URL` at a reachable provider; otherwise `/v1/search` and `/v1/search/crawl-selected` return `503`. Direct crawl and media submission still work. `broker` mode remains the Docker/production path and uses the existing PostgreSQL, Redis/Celery and MinIO services.

## 5. Run the quality gate (offline, no network)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
