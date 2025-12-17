"""MinIO storage implementation for S3-compatible object storage."""

import logging
from io import BytesIO
from typing import Optional

try:
    from minio import Minio
    from minio.api import MinioAdminClient
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    Minio = None
    S3Error = None

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO S3-compatible object storage client."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = "server-agent",
        use_ssl: bool = True,
    ):
        """
        Initialize MinIO storage client.

        Args:
            endpoint: MinIO endpoint (e.g., "minio.example.com:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Default bucket name
            use_ssl: Use HTTPS/SSL
        """
        if not MINIO_AVAILABLE:
            raise ImportError(
                "minio package is not installed. "
                "Install with: pip install minio"
            )

        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.use_ssl = use_ssl
        self.client: Optional[Minio] = None

    async def connect(self) -> None:
        """Initialize MinIO connection."""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.use_ssl,
            )

            # Test connection by checking bucket exists
            exists = self.client.bucket_exists(self.bucket)
            if not exists:
                logger.info(f"Creating bucket: {self.bucket}")
                self.client.make_bucket(self.bucket)

            logger.info(f"MinIO connected to {self.endpoint} (bucket={self.bucket})")

        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            raise

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to MinIO.

        Args:
            bucket: Bucket name
            key: Object key
            file_data: File content
            content_type: MIME type

        Returns:
            MinIO URI (minio://bucket/key)

        Raises:
            RuntimeError: If not connected or upload fails
        """
        if not self.client:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        try:
            # Create BytesIO stream from file data
            stream = BytesIO(file_data)
            stream_length = len(file_data)

            # Upload to MinIO
            self.client.put_object(
                bucket,
                key,
                stream,
                stream_length,
                content_type=content_type,
            )

            uri = f"minio://{bucket}/{key}"
            logger.debug(f"Uploaded {key} to MinIO ({stream_length} bytes)")
            return uri

        except S3Error as e:
            logger.error(f"Failed to upload {key} to MinIO: {e}")
            raise RuntimeError(f"MinIO upload failed: {e}")

    async def download_file(self, bucket: str, key: str) -> bytes:
        """
        Download file from MinIO.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            File content

        Raises:
            RuntimeError: If not connected or download fails
        """
        if not self.client:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        try:
            response = self.client.get_object(bucket, key)
            file_data = response.read()
            response.close()

            logger.debug(f"Downloaded {key} from MinIO ({len(file_data)} bytes)")
            return file_data

        except S3Error as e:
            logger.error(f"Failed to download {key} from MinIO: {e}")
            raise RuntimeError(f"MinIO download failed: {e}")

    async def delete_file(self, bucket: str, key: str) -> None:
        """
        Delete file from MinIO.

        Args:
            bucket: Bucket name
            key: Object key

        Raises:
            RuntimeError: If not connected or delete fails
        """
        if not self.client:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        try:
            self.client.remove_object(bucket, key)
            logger.debug(f"Deleted {key} from MinIO")

        except S3Error as e:
            logger.error(f"Failed to delete {key} from MinIO: {e}")
            raise RuntimeError(f"MinIO delete failed: {e}")

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
            expires: Expiration time in seconds (default 1 hour)

        Returns:
            Presigned URL (HTTPS)

        Raises:
            RuntimeError: If not connected or URL generation fails
        """
        if not self.client:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        try:
            from datetime import timedelta

            url = self.client.get_presigned_download_url(
                bucket,
                key,
                expires=timedelta(seconds=expires),
            )

            logger.debug(f"Generated presigned URL for {key} (expires={expires}s)")
            return url

        except S3Error as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise RuntimeError(f"MinIO presigned URL generation failed: {e}")


__all__ = ["MinIOStorage"]
