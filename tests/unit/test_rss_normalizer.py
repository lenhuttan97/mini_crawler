"""Tests cho RSS normalizer và torrent quota (P04 Item 3).

RSS chỉ discovery item từ nguồn approved, không tự download. Torrent quota
phân loại lỗi quota. Không gọi mạng thật.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base
from app.services.rss_normalizer import (
    TorrentQuotaError,
    classify_torrent_quota,
    normalize_rss_items,
)


def test_normalize_rss_items_dedup_and_limit() -> None:
    """Chuẩn hóa RSS: loại trùng, giới hạn số item, chỉ giữ an toàn."""
    items = [
        {"title": "A", "link": "https://example.com/a", "published": "2026-11-08"},
        {"title": "A dup", "link": "https://example.com/a", "published": "2026-11-08"},
        {"title": "B", "link": "https://example.com/b", "published": "2026-11-07"},
    ]
    result = normalize_rss_items(items, max_items=5)
    links = [it["link"] for it in result]
    assert links == ["https://example.com/a", "https://example.com/b"]
    assert len(result) == 2


def test_normalize_rss_items_max_items() -> None:
    """Vượt max_items => cắt bớt."""
    items = [
        {"title": f"T{i}", "link": f"https://example.com/{i}", "published": "2026-11-08"}
        for i in range(5)
    ]
    result = normalize_rss_items(items, max_items=2)
    assert len(result) == 2


def test_normalize_rss_items_rejects_unsafe_link() -> None:
    """Loại item có link scheme không an toàn (file:, javascript:)."""
    items = [
        {"title": "A", "link": "https://example.com/a"},
        {"title": "B", "link": "file:///etc/passwd"},
        {"title": "C", "link": "javascript:alert(1)"},
    ]
    result = normalize_rss_items(items, max_items=5)
    links = [it["link"] for it in result]
    assert links == ["https://example.com/a"]


def test_classify_torrent_quota_ok() -> None:
    """Torrent trong quota => OK."""
    assert classify_torrent_quota(peers=10, disk_mb=2048, bandwidth_mbps=50) is None


def test_classify_torrent_quota_exceeded() -> None:
    """Vượt quota peers/disk/bandwidth => TorrentQuotaError."""
    with pytest.raises(TorrentQuotaError, match="peers"):
        classify_torrent_quota(peers=200, disk_mb=1000, bandwidth_mbps=50)
    with pytest.raises(TorrentQuotaError, match="disk"):
        classify_torrent_quota(peers=10, disk_mb=50, bandwidth_mbps=50)
    with pytest.raises(TorrentQuotaError, match="bandwidth"):
        classify_torrent_quota(peers=10, disk_mb=2048, bandwidth_mbps=5)


def test_rss_discovery_requires_persisted_approved_rss_feature(tmp_path) -> None:
    """RSS discovery normalizes approved feed items but never creates a download job."""
    from app.services.rss_discovery import discover_rss_items
    from app.services.source_registry_service import SourceRegistryService

    engine = create_engine(f"sqlite:///{tmp_path / 'rss.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    registry = SourceRegistryService(session)
    registry.upsert(
        domain="feeds.example",
        state=SourceStatus.APPROVED,
        owner="rights-team",
        distribution_evidence="license-1",
        feature_flags={"rss": True},
    )

    result = discover_rss_items(
        domain="feeds.example",
        raw_items=[{"title": "A", "link": "https://feeds.example/a"}],
        source_registry=registry,
    )

    assert result == [{"title": "A", "link": "https://feeds.example/a", "published": ""}]
