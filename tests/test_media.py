"""Tests for media processing module."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from app.media.utils import (
    get_file_extension,
    get_mime_type,
    validate_file_size,
    is_supported_format,
)
from app.media.processor import MediaProcessor


class TestMediaUtils:
    """Test media utility functions."""

    def test_get_file_extension(self):
        """Test file extension extraction."""
        assert get_file_extension("/path/to/file.txt") == ".txt"
        assert get_file_extension("file.pdf") == ".pdf"
        assert get_file_extension("archive.tar.gz") == ".gz"
        assert get_file_extension("no_extension") == ""

    def test_get_mime_type(self):
        """Test MIME type detection."""
        assert get_mime_type("file.pdf") == "application/pdf"
        assert get_mime_type("file.txt") == "text/plain"
        assert get_mime_type("file.jpg") == "image/jpeg"
        assert get_mime_type("file.unknown") == "application/octet-stream"

    def test_validate_file_size(self, tmp_path):
        """Test file size validation."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 1024)  # 1KB

        # Should pass with 10MB limit
        assert validate_file_size(str(test_file), 10)

        # Should fail with 0.5MB limit
        assert not validate_file_size(str(test_file), 0.0001)

    def test_validate_file_size_missing_file(self):
        """Test validation with missing file."""
        assert not validate_file_size("/nonexistent/file.txt", 10)

    def test_is_supported_format(self):
        """Test format support checking."""
        assert is_supported_format("file.ogg", "voice")
        assert is_supported_format("file.mp3", "voice")
        assert is_supported_format("file.jpg", "photo")
        assert is_supported_format("file.pdf", "document")
        assert not is_supported_format("file.exe", "voice")


class TestMediaProcessor:
    """Test media processor."""

    @pytest.mark.asyncio
    async def test_processor_init(self):
        """Test media processor initialization."""
        processor = MediaProcessor(poll_interval_ms=1000)

        assert processor.poll_interval_ms == 1000
        assert processor.poll_interval_s == 1.0
        assert not processor.running

    @pytest.mark.asyncio
    async def test_processor_start_stop(self):
        """Test processor start and stop."""
        processor = MediaProcessor(poll_interval_ms=100)

        # Start processor
        await processor.start()
        assert processor.running
        assert processor.task is not None

        # Stop processor
        await processor.stop()
        assert not processor.running

    @pytest.mark.asyncio
    async def test_processor_extract_file_path(self):
        """Test file path extraction from URI."""
        processor = MediaProcessor()

        # Test file:// URI
        path = processor._extract_file_path("file:///tmp/test.txt")
        assert path == "/tmp/test.txt"

        # Test invalid URI
        path = processor._extract_file_path("http://example.com/file.txt")
        assert path is None

    @pytest.mark.asyncio
    async def test_processor_start_already_running(self):
        """Test starting already running processor."""
        processor = MediaProcessor(poll_interval_ms=100)

        await processor.start()
        assert processor.running

        # Starting again should be no-op
        await processor.start()
        assert processor.running

        await processor.stop()

    @pytest.mark.asyncio
    async def test_processor_stop_not_running(self):
        """Test stopping processor that's not running."""
        processor = MediaProcessor()

        # Stopping when not running should be no-op
        await processor.stop()
        assert not processor.running


class TestMediaProcessorIntegration:
    """Integration tests for media processor."""

    @pytest.mark.asyncio
    async def test_processor_pending_artifacts_fetch(self):
        """Test fetching pending artifacts."""
        processor = MediaProcessor(poll_interval_ms=100)

        # Mock database
        with patch("app.media.processor.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetch_all = AsyncMock(return_value=[])
            mock_get_db.return_value = mock_db

            # Process pending media
            await processor.process_pending_media()

            # Verify database was queried
            mock_db.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_processor_invalid_uri_handling(self):
        """Test processor handles invalid URIs gracefully."""
        processor = MediaProcessor(poll_interval_ms=100)

        # Mock database with invalid URI
        with patch("app.media.processor.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetch_all = AsyncMock(
                return_value=[
                    {
                        "id": "test-id",
                        "kind": "voice_transcript",
                        "content_json": {"status": "pending", "attempt_count": 0},
                        "uri": "invalid://uri",
                    }
                ]
            )
            mock_db.fetch_one = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            # Process should handle gracefully
            await processor.process_pending_media()

            # Verify database was called
            assert mock_db.fetch_all.called


class TestMediaUtilsFileOperations:
    """Test file operation utilities."""

    @pytest.mark.asyncio
    async def test_cleanup_temp_file(self, tmp_path):
        """Test cleaning up temporary file."""
        from app.media.utils import cleanup_temp_file

        test_file = tmp_path / "temp.txt"
        test_file.write_text("test")

        # File should exist
        assert test_file.exists()

        # Clean up file
        result = await cleanup_temp_file(str(test_file))
        assert result

        # File should be deleted
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self):
        """Test cleaning up non-existent file."""
        from app.media.utils import cleanup_temp_file

        result = await cleanup_temp_file("/nonexistent/file.txt")
        assert not result

    @pytest.mark.asyncio
    async def test_cleanup_file_suppress_errors(self):
        """Test cleanup with error suppression."""
        from app.media.utils import cleanup_temp_file

        # Clean up with suppress_errors=True (default)
        result = await cleanup_temp_file("/nonexistent/readonly/file.txt")
        assert not result  # Returns False instead of raising

        # Clean up with suppress_errors=False should raise
        with pytest.raises((FileNotFoundError, OSError)):
            await cleanup_temp_file("/nonexistent/readonly/file.txt", suppress_errors=False)
