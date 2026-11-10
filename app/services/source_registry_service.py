"""Durable approved-source registry and feature authorization (P04)."""

from __future__ import annotations

from typing import Any

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import SourceRegistryEntry


class SourceRegistryService:
    """Authorize video/torrent/RSS work from persisted rights-reviewed source records."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def upsert(
        self,
        *,
        domain: str,
        state: SourceStatus,
        owner: str,
        distribution_evidence: str,
        feature_flags: dict[str, bool],
    ) -> SourceRegistryEntry:
        """Create or update an owned source record without enabling unspecified features."""
        entry = self._session.get(SourceRegistryEntry, domain)
        if entry is None:
            entry = SourceRegistryEntry(
                domain=domain,
                state=state.value,
                owner=owner,
                distribution_evidence=distribution_evidence,
                feature_flags=feature_flags,
            )
            self._session.add(entry)
        else:
            entry.state = state.value
            entry.owner = owner
            entry.distribution_evidence = distribution_evidence
            entry.feature_flags = feature_flags
        self._session.flush()
        return entry

    def allows_network(self, *, domain: str, feature: str) -> bool:
        """Allow only approved sources with the requested feature explicitly enabled."""
        entry = self._session.get(SourceRegistryEntry, domain)
        return bool(
            entry
            and entry.state == SourceStatus.APPROVED.value
            and entry.feature_flags.get(feature, False)
        )
