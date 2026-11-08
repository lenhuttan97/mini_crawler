"""Quy tắc cảnh báo và liên kết runbook (P07-P08, §4-5 Operations and recovery).

Mỗi quy tắc có owner, severity và runbook liên kết. Không gọi mạng thật.
"""

from __future__ import annotations

from typing import Any

ALERT_RULES: list[dict[str, Any]] = [
    {
        "name": "queue_lag_high",
        "metric": "crawler_queue_delay_seconds",
        "threshold": 60.0,
        "severity": "high",
        "owner": "platform-team",
        "runbook": "queue_lag.md",
    },
    {
        "name": "error_ratio_high",
        "metric": "crawler_job_failure_ratio",
        "threshold": 0.05,
        "severity": "high",
        "owner": "platform-team",
        "runbook": "error_ratio.md",
    },
    {
        "name": "browser_memory_high",
        "metric": "crawler_browser_memory_mb",
        "threshold": 2048.0,
        "severity": "medium",
        "owner": "infra-team",
        "runbook": "browser_memory.md",
    },
]
