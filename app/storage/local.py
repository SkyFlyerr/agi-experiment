"""Local filesystem storage implementation."""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local filesystem storage backend."""

    def __init__(self, base_path: str = "/tmp/server-agent-media"):
        """
        Initialize local storage.

        Args:
            base_path: Base directory for media storage (default: /tmp/server-agent-media)
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at {self.base_path}")

    async def connect(self) -> None:
        """Initialize storage (no-op for local storage)."""
        logger.debug("Local storage connected")

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to local filesystem.

        Files are organized by date: YYYY/MM/DD/

        Args:
            bucket: Bucket name (becomes subdirectory)
            key: Object key (filename with possible subdirectories)
            file_data: File content
            content_type: MIME type (for metadata)

        Returns:
            Local file URI (file:///absolute/path)
        """
        try:
            # Create date-based directory structure
            now = datetime.now()
            date_path = now.strftime("%Y/%m/%d")

            # Create full directory path
            full_dir = self.base_path / bucket / date_path
            full_dir.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path = full_dir / key
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_data)

            # Return file:// URI with absolute path
            uri = f"file://{file_path.absolute()}"
            logger.debug(f"Uploaded {key} to local storage ({len(file_data)} bytes)")
            return uri

        except Exception as e:
            logger.error(f"Failed to upload {key} to local storage: {e}")
            raise RuntimeError(f"Local storage upload failed: {e}")

    async def download_file(self, bucket: str, key: str) -> bytes:
        """
        Download file from local filesystem.

        Args:
            bucket: Bucket name (subdirectory)
            key: Object key (filename with possible subdirectories)

        Returns:
            File content

        Raises:
            RuntimeError: If file not found or read fails
        """
        try:
            # Try to find file in recent dates first (today, yesterday, etc.)
            file_path = await self._find_file(bucket, key)

            if not file_path:
                raise FileNotFoundError(f"File not found: {bucket}/{key}")

            async with aiofiles.open(file_path, "rb") as f:
                file_data = await f.read()

            logger.debug(f"Downloaded {key} from local storage ({len(file_data)} bytes)")
            return file_data

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise RuntimeError(f"Local storage download failed: {e}")
        except Exception as e:
            logger.error(f"Failed to download {key} from local storage: {e}")
            raise RuntimeError(f"Local storage download failed: {e}")

    async def delete_file(self, bucket: str, key: str) -> None:
        """
        Delete file from local filesystem.

        Args:
            bucket: Bucket name (subdirectory)
            key: Object key (filename)

        Raises:
            RuntimeError: If file not found or deletion fails
        """
        try:
            file_path = await self._find_file(bucket, key)

            if not file_path:
                logger.warning(f"File not found for deletion: {bucket}/{key}")
                return

            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted {key} from local storage")

        except Exception as e:
            logger.error(f"Failed to delete {key} from local storage: {e}")
            raise RuntimeError(f"Local storage delete failed: {e}")

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires: int = 3600,
    ) -> str:
        """
        Generate presigned URL (returns file:// URI for local storage).

        For local storage, this simply returns the file path.
        This is useful for development but not for production use.

        Args:
            bucket: Bucket name
            key: Object key
            expires: Expiration time in seconds (ignored for local storage)

        Returns:
            file:// URI
        """
        try:
            file_path = await self._find_file(bucket, key)

            if not file_path:
                raise FileNotFoundError(f"File not found: {bucket}/{key}")

            uri = f"file://{file_path.absolute()}"
            logger.debug(f"Generated presigned URL for {key}: {uri}")
            return uri

        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise RuntimeError(f"Local storage presigned URL generation failed: {e}")

    async def cleanup_old_files(self, days: int = 7) -> int:
        """
        Clean up files older than specified days.

        Args:
            days: Delete files older than this many days (default: 7)

        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0

            for bucket_dir in self.base_path.iterdir():
                if not bucket_dir.is_dir():
                    continue

                for year_dir in bucket_dir.iterdir():
                    if not year_dir.is_dir():
                        continue

                    for month_dir in year_dir.iterdir():
                        if not month_dir.is_dir():
                            continue

                        for day_dir in month_dir.iterdir():
                            if not day_dir.is_dir():
                                continue

                            # Parse date from directory structure
                            try:
                                date_str = f"{year_dir.name}/{month_dir.name}/{day_dir.name}"
                                dir_date = datetime.strptime(date_str, "%Y/%m/%d")

                                if dir_date < cutoff_date:
                                    # Delete all files in this directory
                                    for file_path in day_dir.iterdir():
                                        if file_path.is_file():
                                            file_path.unlink()
                                            deleted_count += 1

                                    # Try to remove empty directories
                                    try:
                                        day_dir.rmdir()
                                        month_dir.rmdir()
                                        year_dir.rmdir()
                                    except OSError:
                                        # Directories not empty, that's ok
                                        pass

                            except ValueError:
                                # Invalid date format, skip
                                continue

            logger.info(f"Cleaned up {deleted_count} old files (older than {days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0

    async def _find_file(self, bucket: str, key: str) -> Optional[Path]:
        """
        Find file in local storage.

        Since files are organized by date, we search for the file
        starting from today and going back.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Path to file if found, None otherwise
        """
        bucket_dir = self.base_path / bucket

        if not bucket_dir.exists():
            return None

        # Search from today going back (most files are recent)
        for days_back in range(30):  # Search last 30 days
            check_date = datetime.now() - timedelta(days=days_back)
            date_path = check_date.strftime("%Y/%m/%d")
            file_path = bucket_dir / date_path / key

            if file_path.exists():
                return file_path

        return None


__all__ = ["LocalStorage"]
