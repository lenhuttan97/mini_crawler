"""Integration tests against Docker Compose stack (P00/P07-P08).

Các test này yêu cầu Docker daemon và `docker compose up --build` đã chạy.
Nếu Docker không khả dụng, toàn bộ test bị skip — đây là blocker đã ghi trong
docs/plan/INDEX.md mục 4 (P07–P08).
"""

from __future__ import annotations

import subprocess

import pytest


def _services_up() -> bool:
    """Kiểm tra xem API đang lắng nghe trên localhost:8000 hay không."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module", autouse=True)
def require_docker() -> None:
    """Bỏ qua nếu Docker compose stack không chạy."""
    if not _services_up():
        pytest.skip("Docker compose stack không chạy: localhost:8000 không tiếp cận được")


def test_docker_compose_services_healthy() -> None:
    """Tất cả service trong docker-compose.yml phải healthy."""
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0


def test_api_health_endpoints() -> None:
    """GET /health/live và /health/ready phải trả 200 qua localhost:8000."""
    import httpx

    response = httpx.get("http://127.0.0.1:8000/health/live", timeout=5.0)
    assert response.status_code == 200
    response = httpx.get("http://127.0.0.1:8000/health/ready", timeout=5.0)
    assert response.status_code == 200


def test_postgres_ready() -> None:
    """Postgres phải sẵn sàng qua pg_isready."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "minicrawler",
            "-d",
            "minicrawler",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_redis_ready() -> None:
    """Redis phải trả PING."""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "ping"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PONG" in result.stdout


def test_minio_health() -> None:
    """MinIO healthcheck phải trả 200."""
    import httpx

    response = httpx.get("http://127.0.0.1:9000/minio/health/live", timeout=5.0)
    assert response.status_code == 200


def test_searxng_health() -> None:
    """SearXNG healthcheck phải trả 200."""
    import httpx

    response = httpx.get("http://127.0.0.1:8080/", timeout=5.0)
    assert response.status_code == 200
