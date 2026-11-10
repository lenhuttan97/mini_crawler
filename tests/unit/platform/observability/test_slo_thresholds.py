"""Định nghĩa ngưỡng SLO (P07-P08, §3 Benchmark và reliability)."""

from __future__ import annotations

from app.platform.observability.slo import SLO_THRESHOLDS


def test_slo_thresholds_defined_and_valid() -> None:
    """Phải có ngưỡng SLO cho các chỉ số chính, mỗi ngưỡng có đầy đủ trường hợp lệ."""
    assert SLO_THRESHOLDS, "phải định nghĩa ít nhất một ngưỡng SLO"
    required = {"name", "metric", "threshold", "unit", "severity"}
    valid_severity = {"low", "medium", "high", "critical"}
    for entry in SLO_THRESHOLDS:
        assert required <= set(entry.keys()), f"thiếu trường trong {entry}"
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["metric"], str) and entry["metric"]
        assert isinstance(entry["threshold"], (int, float)) and entry["threshold"] > 0
        assert isinstance(entry["unit"], str) and entry["unit"]
        assert entry["severity"] in valid_severity, f"severity không hợp lệ: {entry['severity']}"


def test_slo_covers_queue_delay_and_failure_ratio() -> None:
    """Các chỉ số then chốt (queue delay, tỉ lệ thất bại) phải có ngưỡng SLO."""
    names = {entry["name"] for entry in SLO_THRESHOLDS}
    assert "queue_delay_seconds" in names
    assert "failure_ratio" in names
