"""Approved-source RSS discovery without automatic download (P04)."""

from __future__ import annotations

from typing import Any

from app.legacy.rss.normalizer import normalize_rss_items


class SourceFeatureDenied(Exception):
    """A source is not approved or has not enabled the requested feature."""


def discover_rss_items(*, domain: str, raw_items: list[dict], source_registry: Any) -> list[dict]:
    """Normalize supplied RSS entries only for an approved, RSS-enabled source."""
    if not source_registry.allows_network(domain=domain, feature="rss"):
        raise SourceFeatureDenied("rss source is not approved or feature-enabled")
    return normalize_rss_items(raw_items)
