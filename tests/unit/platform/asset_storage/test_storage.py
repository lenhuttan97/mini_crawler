"""Tests for Storage adapter (P01 Item 6).

Kiểm tra adapter MinIO/S3 với boto3 client bị mock — không cần MinIO thật.
Object key do server tạo, không được trích từ tiêu đề do người dùng cung cấp.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.platform.asset_storage.storage import (
    StorageAdapter,
    StorageError,
    StorageMetadata,
)


def test_upload_object_returns_metadata() -> None:
    """Tải object lên và nhận metadata (key, size, etag)."""
    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"abc123"'}
    adapter = StorageAdapter(s3_client=s3)

    metadata = adapter.upload_object(
        bucket="my-bucket", key="obj/key-1", data=b"hello world", content_type="text/plain"
    )

    assert isinstance(metadata, StorageMetadata)
    assert metadata.bucket == "my-bucket"
    assert metadata.key == "obj/key-1"
    assert metadata.size == 11
    assert metadata.content_type == "text/plain"
    assert metadata.etag == "abc123"
    s3.put_object.assert_called_once()


def test_download_object_returns_data() -> None:
    """Tải object về nhận dữ liệu bytes."""
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"file content")}
    adapter = StorageAdapter(s3_client=s3)

    data = adapter.download_object(bucket="my-bucket", key="obj/key-1")

    assert data == b"file content"
    s3.get_object.assert_called_once_with(Bucket="my-bucket", Key="obj/key-1")


def test_delete_object() -> None:
    """Xóa object gọi delete_object."""
    s3 = MagicMock()
    adapter = StorageAdapter(s3_client=s3)
    adapter.delete_object(bucket="my-bucket", key="obj/key-1")
    s3.delete_object.assert_called_once_with(Bucket="my-bucket", Key="obj/key-1")


def test_generate_presigned_url_with_ttl() -> None:
    """Tạo URL truy cập tạm thời với TTL (object không public)."""
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://minio/bucket/key?sig=xxx"
    adapter = StorageAdapter(s3_client=s3)

    url = adapter.generate_presigned_url(bucket="my-bucket", key="obj/key-1", ttl_seconds=300)

    assert url == "https://minio/bucket/key?sig=xxx"
    s3.generate_presigned_url.assert_called_once()
    kwargs = s3.generate_presigned_url.call_args.kwargs
    assert kwargs["ExpiresIn"] == 300


def test_upload_error_raises_storage_error() -> None:
    """Lỗi upload nêu StorageError (không bị nuốt lẫn)."""
    s3 = MagicMock()
    s3.put_object.side_effect = Exception("access denied")
    adapter = StorageAdapter(s3_client=s3)

    with pytest.raises(StorageError, match="access denied"):
        adapter.upload_object(
            bucket="my-bucket", key="obj/key-1", data=b"x", content_type="text/plain"
        )


def test_server_generated_key_not_from_title() -> None:
    """Khởi tạo adapter không yêu cầu key từ tiêu đề người dùng; key do caller cung cấp rõ ràng."""
    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"x"'}
    adapter = StorageAdapter(s3_client=s3)
    # Caller phải truyền key rõ ràng (server-side ID/hash), không suy từ title.
    metadata = adapter.upload_object(
        bucket="b", key="srv-gen-uuid", data=b"d", content_type="application/octet-stream"
    )
    assert metadata.key == "srv-gen-uuid"
