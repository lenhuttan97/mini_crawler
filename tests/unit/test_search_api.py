"""Public search API contracts (P05)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import create_app


class _FakeSearchService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search(self, *, query: str, page: int, limit: int) -> list[dict]:
        self.calls.append({"query": query, "page": page, "limit": limit})
        return [
            {"title": "A", "url": "https://example.com/a", "snippet": "snippet"},
        ]

    async def crawl_selected(
        self,
        *,
        result_url: str,
        caller_id: str,
        idempotency_key: str,
    ) -> dict:
        self.calls.append(
            {
                "action": "crawl_selected",
                "result_url": result_url,
                "caller_id": caller_id,
                "idempotency_key": idempotency_key,
            }
        )
        return {"crawl_job_id": "crawl-job-1", "status": "pending"}


def test_search_returns_normalized_results_without_auto_crawl() -> None:
    """Tìm kiếm trả danh sách đã chuẩn hóa và không tự tạo CrawlJob."""
    service = _FakeSearchService()
    app = create_app(search_service=service)
    with TestClient(app) as client:
        response = client.get(
            "/v1/search",
            headers={"X-Caller-ID": "caller-1"},
            params={"q": "từ khóa", "page": 1, "limit": 10},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["url"] == "https://example.com/a"
    assert service.calls == [{"query": "từ khóa", "page": 1, "limit": 10}]


def test_search_crawl_selected_returns_f01_job_id() -> None:
    """Chọn kết quả search => gọi F01 create job và trả crawl_job_id."""
    service = _FakeSearchService()
    app = create_app(search_service=service)
    with TestClient(app) as client:
        response = client.post(
            "/v1/search/crawl-selected",
            headers={"X-Caller-ID": "caller-1", "Idempotency-Key": "sel-1"},
            json={"result_url": "https://example.com/a"},
        )

    assert response.status_code == 202
    assert response.json() == {"crawl_job_id": "crawl-job-1", "status": "pending"}
    assert service.calls[-1] == {
        "action": "crawl_selected",
        "result_url": "https://example.com/a",
        "caller_id": "caller-1",
        "idempotency_key": "sel-1",
    }
