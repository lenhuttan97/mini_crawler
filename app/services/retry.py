"""S02 Retry/cancel (P06).

Phân loại lỗi: tạm thời (retry), vĩnh viễn (không retry), blocked_* (không retry).
Tính toán backoff delay theo attempts.
"""

from __future__ import annotations

BLOCKED_PREFIXES = ("blocked_policy", "blocked_drm", "blocked_permission")
TRANSIENT_KEYWORDS = ("timeout", "upstream", "temporary", "transient", "429", "503")


class RetryDecision:
    """Kết quả phân loại retry."""

    def __init__(self, retry: bool, reason: str) -> None:
        self.retry = retry
        self.reason = reason


class RetryService:
    """Phân loại xem lỗi có được retry không và tính backoff."""

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay

    def should_retry(self, exc: BaseException) -> bool:
        """Trả True nếu lỗi nên retry (chỉ lỗi tạm thời, không phải blocked_*)."""
        message = str(exc).lower()
        if any(message.startswith(prefix) or prefix in message for prefix in BLOCKED_PREFIXES):
            return False
        # Lỗi validation (ValueError, TypeError) là vĩnh viễn => không retry.
        if isinstance(exc, (ValueError, TypeError)):
            return False
        # Lỗi tạm thời (timeout, upstream, 429, 503) => retry; mặc định không.
        return any(keyword in message for keyword in TRANSIENT_KEYWORDS)

    def backoff_delay(self, *, attempt: int) -> float:
        """Tính độ trễ backoff (exponential, giới hạn max_delay)."""
        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)
