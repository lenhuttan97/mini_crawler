"""Benchmark fixtures và SLO baseline (P07-P08, §3).

Các chỉ số đo lường được so sánh với ngưỡng SLO trong `app/core/slo.py`.
Thực tế chỉ đo được khi Docker Compose stack đang chạy.
"""

from __future__ import annotations

import httpx

API_BASE = "http://127.0.0.1:8000"


def test_benchmark_job_creation_latency() -> None:
    """Đo độ trễ tạo crawl job (phải dưới SLO queue_delay_seconds = 60s)."""
    import time

    start = time.perf_counter()
    response = httpx.post(
        f"{API_BASE}/v1/crawl-jobs",
        headers={
            "X-Caller-ID": "bench-user-1",
            "Idempotency-Key": "bench-crawl-1",
        },
        json={"url": "https://example.com/bench"},
        timeout=10.0,
    )
    elapsed = time.perf_counter() - start

    assert response.status_code == 202
    # Ngưỡng SLO: queue_delay_seconds <= 60 giây
    assert elapsed < 60.0, f"tạo job quá chậm: {elapsed:.3f}s"


def test_benchmark_health_endpoint_latency() -> None:
    """Đo độ trễ health endpoint (phải dưới 1 giây)."""
    import time

    start = time.perf_counter()
    response = httpx.get(f"{API_BASE}/health/live", timeout=5.0)
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 1.0, f"health endpoint quá chậm: {elapsed:.3f}s"


def test_benchmark_search_latency() -> None:
    """Đo độ trễ tìm kiếm (phải dưới 5 giây)."""
    import time

    start = time.perf_counter()
    response = httpx.get(
        f"{API_BASE}/v1/search",
        params={"q": "benchmark", "page": 1, "limit": 10},
        timeout=10.0,
    )
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 5.0, f"tìm kiếm quá chậm: {elapsed:.3f}s"


def test_benchmark_media_job_creation_latency() -> None:
    """Đo độ trễ tạo media job (phải dưới 5 giây)."""
    import time

    start = time.perf_counter()
    response = httpx.post(
        f"{API_BASE}/v1/media-jobs",
        headers={
            "X-Caller-ID": "bench-user-1",
            "Idempotency-Key": "bench-media-1",
        },
        json={
            "input_type": "direct",
            "source_url": "https://example.com/bench.png",
        },
        timeout=10.0,
    )
    elapsed = time.perf_counter() - start

    assert response.status_code == 202
    assert elapsed < 5.0, f"tạo media job quá chậm: {elapsed:.3f}s"
