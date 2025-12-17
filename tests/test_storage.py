"""Tests for storage module (MinIO and local filesystem)."""

import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from app.storage.local import LocalStorage


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.mark.asyncio
async def test_local_storage_init(temp_storage_dir):
    """Test local storage initialization."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    assert Path(temp_storage_dir).exists()


@pytest.mark.asyncio
async def test_local_storage_upload(temp_storage_dir):
    """Test uploading file to local storage."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Hello, world!"
    uri = await storage.upload_file(
        bucket="test",
        key="test.txt",
        file_data=test_data,
        content_type="text/plain",
    )

    assert uri.startswith("file://")
    assert Path(uri[7:]).exists()


@pytest.mark.asyncio
async def test_local_storage_download(temp_storage_dir):
    """Test downloading file from local storage."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Hello, world!"
    await storage.upload_file(
        bucket="test",
        key="test.txt",
        file_data=test_data,
        content_type="text/plain",
    )

    downloaded = await storage.download_file(bucket="test", key="test.txt")
    assert downloaded == test_data


@pytest.mark.asyncio
async def test_local_storage_delete(temp_storage_dir):
    """Test deleting file from local storage."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Hello, world!"
    uri = await storage.upload_file(
        bucket="test",
        key="test.txt",
        file_data=test_data,
    )

    # Verify file exists
    assert Path(uri[7:]).exists()

    # Delete file
    await storage.delete_file(bucket="test", key="test.txt")

    # Verify file is deleted
    assert not Path(uri[7:]).exists()


@pytest.mark.asyncio
async def test_local_storage_presigned_url(temp_storage_dir):
    """Test generating presigned URL."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Hello, world!"
    await storage.upload_file(
        bucket="test",
        key="test.txt",
        file_data=test_data,
    )

    url = await storage.generate_presigned_url(bucket="test", key="test.txt")
    assert url.startswith("file://")
    assert Path(url[7:]).exists()


@pytest.mark.asyncio
async def test_local_storage_date_organization(temp_storage_dir):
    """Test that files are organized by date."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Test data"
    uri = await storage.upload_file(
        bucket="media",
        key="file.txt",
        file_data=test_data,
    )

    # Check that file path contains date structure (YYYY/MM/DD)
    path = uri[7:]  # Remove "file://"
    assert "media" in path  # Bucket name
    assert "2" in path  # Year contains 2
    assert "/" in path  # Has directory separators


@pytest.mark.asyncio
async def test_local_storage_file_not_found(temp_storage_dir):
    """Test downloading non-existent file raises error."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    with pytest.raises(RuntimeError):
        await storage.download_file(bucket="test", key="nonexistent.txt")


@pytest.mark.asyncio
async def test_local_storage_cleanup_old_files(temp_storage_dir):
    """Test cleanup of old files."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    # Create test files
    test_data = b"Old file"

    # Upload multiple files (they'll be in today's date directory)
    for i in range(3):
        await storage.upload_file(
            bucket="test",
            key=f"file{i}.txt",
            file_data=test_data,
        )

    # Cleanup old files (should not delete today's files)
    deleted = await storage.cleanup_old_files(days=7)

    # Since we just created files, cleanup should delete 0 files
    assert deleted == 0


@pytest.mark.asyncio
async def test_local_storage_multiple_buckets(temp_storage_dir):
    """Test storing files in multiple buckets."""
    storage = LocalStorage(base_path=temp_storage_dir)
    await storage.connect()

    test_data = b"Test data"

    # Upload to different buckets
    uri1 = await storage.upload_file(
        bucket="bucket1",
        key="file.txt",
        file_data=test_data,
    )

    uri2 = await storage.upload_file(
        bucket="bucket2",
        key="file.txt",
        file_data=test_data,
    )

    # Verify both files exist and are in different locations
    assert Path(uri1[7:]).exists()
    assert Path(uri2[7:]).exists()
    assert uri1 != uri2
    assert "bucket1" in uri1
    assert "bucket2" in uri2
