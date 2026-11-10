"""Domain enums shared by F01/F02/F03 (P01 Item 1).

Single source of truth for job type/status, policy decision/reason, and
source registry status. All values are stable string identifiers safe to
persist, log, and expose in API responses.
"""

from __future__ import annotations

from enum import Enum


class JobType(str, Enum):
    """Kiểu tác vụ nền (phân loại queue)."""

    CRAWL = "crawl"
    MEDIA_DOWNLOAD = "media_download"
    TORRENT = "torrent"
    SEARCH_RESULT = "search_result"


class JobStatus(str, Enum):
    """Trạng thái chung của mọi job (P01 §5.2)."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED_POLICY = "blocked_policy"
    BLOCKED_DRM = "blocked_drm"
    BLOCKED_PERMISSION = "blocked_permission"
    EXPIRED = "expired"

    @classmethod
    def can_transition(cls, source: JobStatus, target: JobStatus) -> bool:
        """Trả True nếu chuyển tiếp từ source sang target là hợp lệ."""
        if source in _TERMINAL_STATES:
            return False
        return (source, target) in _ALLOWED_TRANSITIONS

    def is_blocked(self) -> bool:
        """Trả True nếu trạng thái là bị chặn (không bao giờ retry)."""
        return self in _BLOCKED_STATES

    def is_terminal(self) -> bool:
        """Trả True nếu trạng thái là cuối cùng (không chuyển tiếp nữa)."""
        return self in _TERMINAL_STATES


# Các trạng thái cuối cùng không chuyển tiếp nữa.
_TERMINAL_STATES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.CANCELLED,
        JobStatus.EXPIRED,
        JobStatus.BLOCKED_POLICY,
        JobStatus.BLOCKED_DRM,
        JobStatus.BLOCKED_PERMISSION,
    }
)

# Các trạng thái bị chặn không bao giờ được retry.
_BLOCKED_STATES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.BLOCKED_POLICY,
        JobStatus.BLOCKED_DRM,
        JobStatus.BLOCKED_PERMISSION,
    }
)

# Các bước chuyển tiếp hợp lệ (from → to).
_ALLOWED_TRANSITIONS: frozenset[tuple[JobStatus, JobStatus]] = frozenset(
    {
        (JobStatus.PENDING, JobStatus.QUEUED),
        (JobStatus.QUEUED, JobStatus.RUNNING),
        (JobStatus.RUNNING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.FAILED),
        (JobStatus.RUNNING, JobStatus.CANCELLED),
        (JobStatus.FAILED, JobStatus.QUEUED),  # retry chỉ cho lỗi tạm thời
    }
)


class PolicyDecision(str, Enum):
    """Quyết định của Policy Gate: cho phép hay chặn."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class PolicyReason(str, Enum):
    """Mã lý do chính sách (đã redaction, an toàn để log/expose)."""

    SCHEME_NOT_ALLOWED = "scheme_not_allowed"
    SSRF_PRIVATE_IP = "ssrf_private_ip"
    SSRF_REDIRECT_PRIVATE_IP = "ssrf_redirect_private_ip"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"
    QUOTA_EXCEEDED = "quota_exceeded"
    DRM_DETECTED = "drm_detected"
    PERMISSION_DENIED = "permission_denied"


class SourceStatus(str, Enum):
    """Trạng thái nguồn trong source registry (P04 §1)."""

    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"

    def allows_network(self) -> bool:
        """Chỉ nguồn approved mới được phép thực hiện hành động mạng."""
        return self is SourceStatus.APPROVED
