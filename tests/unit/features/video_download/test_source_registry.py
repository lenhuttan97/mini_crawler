"""Tests cho source registry và DRM gate (P04 Item 1).

Nguồn approved mới được phép network; pending_review/blocked từ chối.
DRM/EME phát hiện => blocked_drm. Không gọi mạng thật.
"""

from __future__ import annotations

import pytest

from app.features.video_download.application.source_registry import (
    SourceRecord,
    SourceRegistry,
    SourceState,
    drm_decision,
)


def test_approved_source_allows_network() -> None:
    """Nguồn approved được phép thực hiện hành động mạng."""
    registry = SourceRegistry()
    registry.add(
        SourceRecord(
            domain="example.com",
            state=SourceState.APPROVED,
            quota=10,
        )
    )
    assert registry.is_allowed("example.com") is True
    assert registry.allows_network("example.com") is True


def test_pending_review_blocked_network() -> None:
    """pending_review lưu đề nghị, không cho network action."""
    registry = SourceRegistry()
    registry.add(SourceRecord(domain="pending.example.com", state=SourceState.PENDING_REVIEW))
    assert registry.is_allowed("pending.example.com") is False
    assert registry.allows_network("pending.example.com") is False


def test_blocked_source_denied() -> None:
    """blocked từ chối với reason code, không retry."""
    registry = SourceRegistry()
    registry.add(SourceRecord(domain="bad.example.com", state=SourceState.BLOCKED))
    assert registry.is_allowed("bad.example.com") is False
    assert registry.allows_network("bad.example.com") is False


def test_unknown_source_denied_by_default() -> None:
    """Nguồn không đăng ký => deny-by-default."""
    registry = SourceRegistry()
    assert registry.is_allowed("unknown.example.com") is False
    assert registry.allows_network("unknown.example.com") is False


def test_drm_detected_blocked_drm() -> None:
    """Phát hiện DRM/EME/ContentProtection => blocked_drm, dừng ngay."""
    assert drm_decision(has_drm=True) == "blocked_drm"
    assert drm_decision(has_drm=False) is None


def test_recipe_max_actions_enforced() -> None:
    """Recipe action phải <= max_actions, không cho vòng lặp vô hạn."""
    registry = SourceRegistry()
    registry.add(
        SourceRecord(
            domain="recipe.example.com",
            state=SourceState.APPROVED,
            max_actions=5,
        )
    )
    assert registry.validate_recipe_actions(3) is True
    with pytest.raises(ValueError, match="max_actions"):
        registry.validate_recipe_actions(10, domain="recipe.example.com")
