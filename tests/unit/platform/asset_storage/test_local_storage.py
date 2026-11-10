"""Tests for the local filesystem object-storage adapter."""

from __future__ import annotations

import pytest

from app.platform.asset_storage.local import LocalStorageAdapter
from app.platform.asset_storage.storage import StorageError


def test_local_storage_round_trips_server_generated_key(tmp_path) -> None:
    """Server-generated object keys round-trip without exposing absolute paths."""
    storage = LocalStorageAdapter(tmp_path)

    result = storage.upload_object(
        bucket="documents",
        key="documents/markdown/id",
        data=b"body",
        content_type="text/plain",
    )

    assert result.key == "documents/markdown/id"
    assert result.size == 4
    assert result.content_type == "text/plain"
    assert storage.download_object(bucket="documents", key=result.key) == b"body"


@pytest.mark.parametrize("key", ["../escape", "/tmp/escape", "a/../../escape"])
def test_local_storage_rejects_path_escape(tmp_path, key: str) -> None:
    """Caller-influenced keys cannot escape the configured storage root."""
    with pytest.raises(StorageError):
        LocalStorageAdapter(tmp_path).upload_object(
            bucket="documents",
            key=key,
            data=b"x",
            content_type="text/plain",
        )


def test_local_storage_rejects_symlink_escape(tmp_path) -> None:
    """An existing symlink cannot redirect writes outside the storage root."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "documents").symlink_to(outside, target_is_directory=True)

    with pytest.raises(StorageError):
        LocalStorageAdapter(root).upload_object(
            bucket="documents",
            key="escape",
            data=b"x",
            content_type="text/plain",
        )

    assert list(outside.iterdir()) == []


def test_local_storage_deletes_and_reports_missing_objects(tmp_path) -> None:
    """Delete is idempotent, while a missing read is a typed storage failure."""
    storage = LocalStorageAdapter(tmp_path)
    storage.upload_object(bucket="documents", key="one", data=b"x", content_type="text/plain")

    storage.delete_object(bucket="documents", key="one")
    storage.delete_object(bucket="documents", key="one")

    with pytest.raises(StorageError):
        storage.download_object(bucket="documents", key="one")
