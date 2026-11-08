"""Source registry và DRM gate (P04 Item 1).

Nguồn `approved` mới được phép network; `pending_review`/`blocked` từ chối
(deny-by-default). Phát hiện DRM/EME/ContentProtection => blocked_drm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import SourceStatus

# Tên gọi thân thi hơn cho registry (P04 §1).
SourceState = SourceStatus


@dataclass(frozen=True)
class SourceRecord:
    """Bản ghi nguồn trong registry."""

    domain: str
    state: SourceStatus = SourceStatus.PENDING_REVIEW
    quota: int = 0
    max_actions: int | None = None


@dataclass
class SourceRegistry:
    """Registry nguồn phân phối; deny-by-default."""

    _sources: dict[str, SourceRecord] = field(default_factory=dict)

    def add(self, record: SourceRecord) -> None:
        self._sources[record.domain] = record

    def is_allowed(self, domain: str) -> bool:
        """Chỉ nguồn approved mới được phép."""
        record = self._sources.get(domain)
        return record is not None and record.state is SourceStatus.APPROVED

    def allows_network(self, domain: str) -> bool:
        """Hành động mạng chỉ được phép cho nguồn approved."""
        return self.is_allowed(domain)

    def validate_recipe_actions(self, action_count: int, domain: str | None = None) -> bool:
        """Số action recipe phải <= max_actions của domain (nếu có)."""
        if (
            domain is not None
            and (record := self._sources.get(domain)) is not None
            and record.max_actions is not None
            and action_count > record.max_actions
        ):
            raise ValueError(f"vượt quá max_actions {record.max_actions} cho {domain}")
        return True


def drm_decision(*, has_drm: bool) -> str | None:
    """Trả 'blocked_drm' nếu phát hiện DRM/EME/ContentProtection, ngược lại None."""
    if has_drm:
        return "blocked_drm"
    return None
