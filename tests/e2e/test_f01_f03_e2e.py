"""E2E tests cho F01/F03 happy path (P02/P05).

Các test này yêu cầu Docker Compose stack đã chạy (api, postgres, redis,
minio, searxng). Nếu Docker không khả dụng, bỏ qua toàn bộ test.
"""

from __future__ import annotations

import httpx
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


API_BASE = "http://127.0.0.1:8000"


def test_f01_create_crawl_job_e2e() -> None:
    """POST /v1/crawl-jobs trả 202 và tạo job ID ngay (không crawl inline)."""
    response = httpx.post(
        f"{API_BASE}/v1/crawl-jobs",
        headers={
            "X-Caller-ID": "e2e-user-1",
            "Idempotency-Key": "e2e-crawl-1",
        },
        json={"url": "https://example.com/page"},
        timeout=10.0,
    )
    assert response.status_code == 202
    body = response.json()
    assert "crawl_job_id" in body
    assert body["status"] == "pending"


def test_f01_get_crawl_job_ownership_e2e() -> None:
    """Chủ sở hữu đọc được job; caller khác nhận 404."""
    # Tạo job
    create = httpx.post(
        f"{API_BASE}/v1/crawl-jobs",
        headers={
            "X-Caller-ID": "e2e-user-A",
            "Idempotency-Key": "e2e-crawl-owner",
        },
        json={"url": "https://example.com/owner"},
        timeout=10.0,
    )
    assert create.status_code == 202
    job_id = create.json()["crawl_job_id"]

    # Chủ sở hữu đọc được
    owner_resp = httpx.get(
        f"{API_BASE}/v1/crawl-jobs/{job_id}",
        headers={"X-Caller-ID": "e2e-user-A"},
        timeout=5.0,
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["id"] == job_id

    # Caller khác bị từ chối
    other_resp = httpx.get(
        f"{API_BASE}/v1/crawl-jobs/{job_id}",
        headers={"X-Caller-ID": "e2e-user-B"},
        timeout=5.0,
    )
    assert other_resp.status_code == 404


def test_f01_cancel_crawl_job_e2e() -> None:
    """Chủ sở hữu hủy được job và nhận trạng thái cancelled."""
    create = httpx.post(
        f"{API_BASE}/v1/crawl-jobs",
        headers={
            "X-Caller-ID": "e2e-user-C",
            "Idempotency-Key": "e2e-crawl-cancel",
        },
        json={"url": "https://example.com/cancel"},
        timeout=10.0,
    )
    assert create.status_code == 202
    job_id = create.json()["crawl_job_id"]

    cancel = httpx.post(
        f"{API_BASE}/v1/crawl-jobs/{job_id}/cancel",
        headers={"X-Caller-ID": "e2e-user-C"},
        timeout=5.0,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_f03_search_and_crawl_selected_e2e() -> None:
    """Tìm kiếm trả kết quả đã chuẩn hóa; chọn kết quả tạo F01 CrawlJob."""
    search_resp = httpx.get(
        f"{API_BASE}/v1/search",
        params={"q": "từ khóa e2e", "page": 1, "limit": 10},
        timeout=10.0,
    )
    assert search_resp.status_code == 200
    body = search_resp.json()
    assert "results" in body
    assert "total" in body

    # Chọn kết quả (giả sử có ít nhất một kết quả hoặc URL mẫu)
    crawl_resp = httpx.post(
        f"{API_BASE}/v1/search/crawl-selected",
        headers={
            "X-Caller-ID": "e2e-user-1",
            "Idempotency-Key": "e2e-search-sel-1",
        },
        json={"result_url": "https://example.com/search-result"},
        timeout=10.0,
    )
    assert crawl_resp.status_code == 202
    crawl_body = crawl_resp.json()
    assert "crawl_job_id" in crawl_body
    assert crawl_body["status"] == "pending"


def test_f02_create_media_job_e2e() -> None:
    """POST /v1/media-jobs trả 202 và tạo media job ID ngay."""
    response = httpx.post(
        f"{API_BASE}/v1/media-jobs",
        headers={
            "X-Caller-ID": "e2e-user-1",
            "Idempotency-Key": "e2e-media-1",
        },
        json={
            "input_type": "direct",
            "source_url": "https://example.com/image.png",
        },
        timeout=10.0,
    )
    assert response.status_code == 202
    body = response.json()
    assert "media_job_id" in body
    assert body["status"] == "pending"


def test_documents_list_pagination_e2e() -> None:
    """GET /v1/documents phân trang và lọc theo loại."""
    response = httpx.get(
        f"{API_BASE}/v1/documents",
        headers={"X-Caller-ID": "e2e-user-1"},
        params={"page": 1, "page_size": 20},
        timeout=10.0,
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "total_pages" in body
