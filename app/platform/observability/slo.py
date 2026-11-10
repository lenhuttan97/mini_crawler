"""Ngưỡng SLO (Service Level Objective) cho benchmark và monitoring (P07-P08, §3).

Các ngưỡng này là baseline được phê duyệt cho việc giám sát độ trễ hàng đợi,
thời lượng công việc, tỉ lệ thất bại, bộ nhớ trình duyệt và dung lượng tải
tải về. Không gọi mạng thật.
"""

from __future__ import annotations

from typing import Any

SLO_THRESHOLDS: list[dict[str, Any]] = [
    {
        "name": "queue_delay_seconds",
        "metric": "crawler_queue_delay_seconds",
        "threshold": 60.0,
        "unit": "seconds",
        "severity": "high",
    },
    {
        "name": "job_duration_seconds",
        "metric": "crawler_job_duration_seconds",
        "threshold": 3600.0,
        "unit": "seconds",
        "severity": "medium",
    },
    {
        "name": "failure_ratio",
        "metric": "crawler_job_failure_ratio",
        "threshold": 0.05,
        "unit": "ratio",
        "severity": "high",
    },
    {
        "name": "browser_memory_mb",
        "metric": "crawler_browser_memory_mb",
        "threshold": 2048.0,
        "unit": "MB",
        "severity": "medium",
    },
    {
        "name": "download_bytes_per_job",
        "metric": "crawler_download_bytes_per_job",
        "threshold": 5_000_000.0,
        "unit": "bytes",
        "severity": "low",
    },
]
