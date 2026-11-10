"""Explicit SQLite schema bootstrap for local runtime modes."""

from __future__ import annotations

from app.bootstrap.database import initialize_local_schema
from app.bootstrap.settings import Settings


def main() -> None:
    """Create local tables without starting any external service."""
    initialize_local_schema(Settings())


if __name__ == "__main__":
    main()
