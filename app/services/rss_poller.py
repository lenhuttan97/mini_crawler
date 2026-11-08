"""RSS poller (P04 F02.6).

Chỉ poll RSS từ nguồn approved và đã bật feature rss.
Chỉ discovery item, không tự download.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.services.source_registry_service import SourceRegistryService


class RssPollError(Exception):
    """Nguồn không được phép poll RSS (chưa approved hoặc chưa bật feature rss)."""


class RssPoller:
    """Poll danh sách item RSS từ nguồn đã được phê duyệt."""

    def __init__(
        self,
        source_registry: SourceRegistryService,
        *,
        http_client: Any = None,
    ) -> None:
        self._source_registry = source_registry
        self._http_client = http_client

    def poll(self, domain: str, feed_url: str) -> list[dict[str, Any]]:
        """Trả danh sách item RSS đã chuẩn hóa chỉ khi nguồn approved và bật feature rss."""
        if not self._source_registry.allows_network(domain=domain, feature="rss"):
            raise RssPollError(
                f"nguồn {domain} không được phép poll RSS (chưa approved hoặc chưa bật feature rss)"
            )

        if self._http_client is None:
            raise RssPollError("chưa cấu hình http_client")

        response = self._http_client.get(feed_url)
        root = ET.fromstring(response.text)

        items: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            items.append(
                {
                    "title": (title_el.text or "").strip() if title_el is not None else "",
                    "link": (link_el.text or "").strip() if link_el is not None else "",
                    "published": (pub_date_el.text or "").strip()
                    if pub_date_el is not None
                    else "",
                    "source": domain,
                }
            )
        return items
