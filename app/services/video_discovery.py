"""Video discovery service (P04 F02.2).

Chỉ discover video từ nguồn approved và đã bật feature video.
Không gọi mạng thật, không download video.
"""

from __future__ import annotations

from typing import Any

from app.services.source_registry_service import SourceRegistryService


class VideoDiscoveryError(Exception):
    """Nguồn không được phép discover video (chưa approved hoặc chưa bật feature video)."""


class VideoDiscoveryService:
    """Discover danh sách video candidates từ nguồn đã được phê duyệt."""

    def __init__(self, source_registry: SourceRegistryService) -> None:
        self._source_registry = source_registry

    def discover_videos(
        self,
        domain: str,
        raw_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Trả danh sách video đã chuẩn hóa chỉ khi nguồn approved và bật feature video."""
        if not self._source_registry.allows_network(domain=domain, feature="video"):
            raise VideoDiscoveryError(
                f"nguồn {domain} không được phép discover video (chưa approved hoặc chưa bật feature video)"
            )

        discovered: list[dict[str, Any]] = []
        for item in raw_items:
            url = item.get("url")
            if not url:
                continue
            discovered.append(
                {
                    "url": url,
                    "title": item.get("title", ""),
                    "source": domain,
                }
            )
        return discovered
