"""Cấu hình benchmark: skip khi Docker compose stack không chạy."""

from __future__ import annotations

import socket

import pytest


def _services_up() -> bool:
    """Kiểm tra xem API đang lắng nghe trên localhost:8000 hay không."""
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_docker() -> None:
    if not _services_up():
        pytest.skip("Docker compose stack không chạy: localhost:8000 không tiếp cận được")
