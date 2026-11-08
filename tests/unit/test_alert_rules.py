"""Allure quy tắc cảnh báo và runbook (P07-P08, §4-5 Operations and recovery).

Mỗi quy tắc cảnh báo phải có owner, severity và runbook liên kết; tệp runbook
phải tồn tại trong docs/runbooks/.
"""

from __future__ import annotations

from pathlib import Path

from app.observability.alerts import ALERT_RULES

RUNBOOKS_DIR = Path(__file__).resolve().parents[2] / "docs" / "runbooks"


def test_alert_rules_defined_with_owner_and_runbook() -> None:
    """Phải có quy tắc cảnh báo, mỗi quy tắc có owner, severity, runbook."""
    assert ALERT_RULES, "phải định nghĩa ít nhất một quy tắc cảnh báo"
    required = {"name", "metric", "threshold", "severity", "owner", "runbook"}
    valid_severity = {"low", "medium", "high", "critical"}
    for rule in ALERT_RULES:
        assert required <= set(rule.keys()), f"thiếu trường trong {rule}"
        assert rule["severity"] in valid_severity, f"severity không hợp lệ: {rule['severity']}"
        assert isinstance(rule["owner"], str) and rule["owner"]
        assert isinstance(rule["runbook"], str) and rule["runbook"]
        runbook_path = RUNBOOKS_DIR / rule["runbook"]
        assert runbook_path.is_file(), f"runbook không tồn tại: {runbook_path}"


def test_alert_rules_covers_queue_lag_and_error_ratio() -> None:
    """Các cảnh báo then chốt (queue lag, tỉ lệ lỗi) phải được định nghĩa."""
    names = {rule["name"] for rule in ALERT_RULES}
    assert "queue_lag_high" in names
    assert "error_ratio_high" in names
