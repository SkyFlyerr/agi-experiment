"""Media processing utilities."""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# File extension to MIME type mapping
MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Supported formats by media type
SUPPORTED_FORMATS = {
    "voice": {".ogg", ".mp3", ".wav", ".m4a"},
    "photo": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "document": {".pdf", ".docx", ".txt"},
}


def get_file_extension(file_path: str) -> str:
    """
    Extract file extension from file path.

    Args:
        file_path: Path to file

    Returns:
        File extension (lowercase, with dot, e.g., ".txt")
    """
    ext = Path(file_path).suffix.lower()
    return ext if ext else ""


def get_mime_type(file_path: str) -> str:
    """
    Detect MIME type from file extension.

    Args:
        file_path: Path to file

    Returns:
        MIME type string, or "application/octet-stream" if unknown
    """
    ext = get_file_extension(file_path)
    return MIME_TYPE_MAP.get(ext, "application/octet-stream")


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes.

    Args:
        file_path: Path to file

    Returns:
        File size in bytes

    Raises:
        OSError: If file doesn't exist or can't be read
    """
    return os.path.getsize(file_path)


def validate_file_size(file_path: str, max_mb: int) -> bool:
    """
    Validate that file size doesn't exceed maximum.

    Args:
        file_path: Path to file
        max_mb: Maximum size in megabytes

    Returns:
        True if file is within size limit, False otherwise
    """
    try:
        file_size = get_file_size(file_path)
        max_bytes = max_mb * 1024 * 1024
        return file_size <= max_bytes
    except OSError as e:
        logger.error(f"Error validating file size: {e}")
        return False


def is_supported_format(file_path: str, media_type: str) -> bool:
    """
    Check if file format is supported for given media type.

    Args:
        file_path: Path to file
        media_type: Media type (voice, photo, document)

    Returns:
        True if format is supported, False otherwise
    """
    ext = get_file_extension(file_path)
    supported = SUPPORTED_FORMATS.get(media_type, set())
    return ext in supported


def resize_image_if_needed(
    input_path: str,
    output_path: str,
    max_size: int = 1024,
) -> bool:
    """
    Resize image if larger than max_size.

    Args:
        input_path: Input image path
        output_path: Output image path
        max_size: Maximum dimension in pixels

    Returns:
        True if resized or original size ok, False on error
    """
    try:
        from PIL import Image

        with Image.open(input_path) as img:
            # Check if resize is needed
            if img.width > max_size or img.height > max_size:
                # Calculate new size maintaining aspect ratio
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {img.width}x{img.height}")

            # Save to output path
            img.save(output_path, quality=85, optimize=True)
            logger.debug(f"Saved resized image to {output_path}")
            return True

    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return False


def get_image_dimensions(file_path: str) -> Optional[Tuple[int, int]]:
    """
    Get image dimensions (width, height).

    Args:
        file_path: Path to image file

    Returns:
        Tuple of (width, height) or None if error
    """
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            return img.width, img.height

    except Exception as e:
        logger.error(f"Error getting image dimensions: {e}")
        return None


async def cleanup_temp_file(file_path: str, suppress_errors: bool = True) -> bool:
    """
    Clean up a temporary file.

    Args:
        file_path: Path to file to delete
        suppress_errors: If True, don't raise exceptions

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.debug(f"Cleaned up temp file: {file_path}")
            return True
        return False

    except Exception as e:
        if suppress_errors:
            logger.warning(f"Error cleaning up temp file {file_path}: {e}")
            return False
        raise


__all__ = [
    "get_file_extension",
    "get_mime_type",
    "get_file_size",
    "validate_file_size",
    "is_supported_format",
    "resize_image_if_needed",
    "get_image_dimensions",
    "cleanup_temp_file",
]
