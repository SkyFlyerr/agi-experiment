"""Storage module for media files and artifacts.

Provides abstraction layer for file storage with support for:
- MinIO (S3-compatible object storage)
- Local filesystem storage (fallback)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Storage instance (lazy initialized)
_storage_instance: Optional['BaseStorage'] = None


async def get_storage() -> 'BaseStorage':
    """
    Get or initialize storage instance.

    Returns:
        BaseStorage instance (MinIO or LocalStorage based on config)
    """
    global _storage_instance

    if _storage_instance is None:
        from app.config import settings

        if settings.MINIO_ENABLED and settings.MINIO_ENDPOINT:
            from .minio import MinIOStorage
            _storage_instance = MinIOStorage(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                bucket=settings.MINIO_BUCKET,
            )
            try:
                await _storage_instance.connect()
                logger.info("MinIO storage initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MinIO, falling back to local storage: {e}")
                from .local import LocalStorage
                _storage_instance = LocalStorage()
        else:
            from .local import LocalStorage
            _storage_instance = LocalStorage()
            logger.info("Local storage initialized")

    return _storage_instance


# Type hints for storage interface
from typing import Protocol


class BaseStorage(Protocol):
    """Base storage interface."""

    async def connect(self) -> None:
        """Initialize storage connection."""
        ...

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to storage.

        Args:
            bucket: Bucket name
            key: Object key
            file_data: File content
            content_type: MIME type

        Returns:
            Storage URI
        """
        ...

    async def download_file(self, bucket: str, key: str) -> bytes:
        """
        Download file from storage.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            File content
        """
        ...

    async def delete_file(self, bucket: str, key: str) -> None:
        """
        Delete file from storage.

        Args:
            bucket: Bucket name
            key: Object key
        """
        ...

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires: int = 3600,
    ) -> str:
        """
        Generate presigned download URL.

        Args:
            bucket: Bucket name
            key: Object key
            expires: Expiration time in seconds

        Returns:
            Presigned URL
        """
        ...


__all__ = [
    "get_storage",
    "BaseStorage",
]
