"""RSS normalizer và torrent quota gate (P04 Item 3).

RSS chỉ discovery item từ nguồn đã approved, chuẩn hóa/dedupe, không tự
download. Torrent quota phân loại lỗi peers/disk/bandwidth.
"""

from __future__ import annotations

from dataclasses import dataclass

SAFE_SCHEMES = frozenset({"http", "https"})


def _is_safe_url(url: str | None) -> bool:
    if not url:
        return False
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    return scheme in SAFE_SCHEMES


def normalize_rss_items(items: list[dict], max_items: int = 10) -> list[dict]:
    """Chuẩn hóa RSS: loại trùng theo link, chỉ giữ link an toàn, giới hạn max_items."""
    seen: set[str] = set()
    results: list[dict] = []
    for item in items:
        link = item.get("link")
        if not _is_safe_url(link):
            continue
        if link in seen:
            continue
        seen.add(link)
        results.append(
            {
                "title": item.get("title") or "",
                "link": link,
                "published": item.get("published") or item.get("pubDate") or "",
            }
        )
        if len(results) >= max_items:
            break
    return results


@dataclass(frozen=True)
class TorrentQuotaLimits:
    max_peers: int = 50
    min_free_disk_mb: int = 1024
    min_bandwidth_mbps: int = 10


class TorrentQuotaError(Exception):
    """Vượt quota torrent (peers/disk/bandwidth)."""


def classify_torrent_quota(
    *,
    peers: int,
    disk_mb: int,
    bandwidth_mbps: int,
    limits: TorrentQuotaLimits | None = None,
) -> None:
    """Kiểm tra quota torrent; nêu TorrentQuotaError nếu vượt."""
    limits = limits or TorrentQuotaLimits()
    if peers > limits.max_peers:
        raise TorrentQuotaError(f"số peers {peers} vượt quá giới hạn {limits.max_peers}")
    if disk_mb < limits.min_free_disk_mb:
        raise TorrentQuotaError(
            f"dung lượng disk {disk_mb}MB thấp hơn giới hạn {limits.min_free_disk_mb}MB"
        )
    if bandwidth_mbps < limits.min_bandwidth_mbps:
        raise TorrentQuotaError(
            f"bandwidth {bandwidth_mbps}Mbps thấp hơn giới hạn {limits.min_bandwidth_mbps}Mbps"
        )
