"""Media file handling for Telegram messages."""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import UUID
import aiofiles

from aiogram import Bot
from aiogram.types import File as TelegramFile

from app.telegram.bot import get_bot
from app.db.models import ArtifactKind

logger = logging.getLogger(__name__)

# Media storage directory
MEDIA_DIR = Path("/tmp/server-agent-media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class MediaMetadata:
    """Media file metadata."""

    def __init__(
        self,
        file_id: str,
        file_type: str,
        file_size: Optional[int],
        file_path: str,
        mime_type: Optional[str] = None,
        duration: Optional[int] = None,
    ):
        self.file_id = file_id
        self.file_type = file_type
        self.file_size = file_size
        self.file_path = file_path
        self.mime_type = mime_type
        self.duration = duration


async def download_media(file_id: str, file_type: str, message_id: UUID) -> Optional[MediaMetadata]:
    """
    Download media file from Telegram.

    Args:
        file_id: Telegram file_id
        file_type: Media type (voice, photo, document, video, audio, video_note)
        message_id: Message UUID for naming

    Returns:
        MediaMetadata if successful, None otherwise
    """
    try:
        bot = get_bot()

        # Get file info from Telegram
        file_info: TelegramFile = await bot.get_file(file_id)

        if not file_info.file_path:
            logger.error(f"No file_path in file_info for {file_id}")
            return None

        # Determine file extension
        extension = Path(file_info.file_path).suffix or f".{file_type}"

        # Create local file path
        local_filename = f"{message_id}_{file_type}{extension}"
        local_path = MEDIA_DIR / local_filename

        # Download file
        await bot.download_file(file_info.file_path, local_path)

        logger.info(f"Downloaded {file_type} to {local_path} (size: {file_info.file_size} bytes)")

        return MediaMetadata(
            file_id=file_id,
            file_type=file_type,
            file_size=file_info.file_size,
            file_path=str(local_path),
            mime_type=None,  # Telegram doesn't always provide mime_type
            duration=None,
        )

    except Exception as e:
        logger.error(f"Failed to download media {file_id}: {e}", exc_info=True)
        return None


def get_artifact_kind(media_type: str) -> ArtifactKind:
    """
    Map media type to artifact kind.

    Args:
        media_type: Media type string

    Returns:
        ArtifactKind enum value
    """
    if media_type == "voice":
        return ArtifactKind.VOICE_TRANSCRIPT  # Will be transcribed later
    elif media_type == "photo":
        return ArtifactKind.IMAGE_JSON  # Will be analyzed later
    elif media_type == "document":
        return ArtifactKind.FILE_META
    elif media_type in ["video", "audio", "video_note"]:
        return ArtifactKind.FILE_META
    else:
        return ArtifactKind.FILE_META


async def create_artifact_metadata(
    media_type: str,
    file_id: str,
    message_id: UUID,
) -> Dict[str, Any]:
    """
    Create artifact metadata for media file.

    This creates a placeholder artifact that will be processed later
    (e.g., voice transcription, image analysis) by the async MediaProcessor.

    Args:
        media_type: Type of media (voice, photo, document, video, audio)
        file_id: Telegram file_id
        message_id: Message UUID

    Returns:
        Dictionary with artifact data (content_json and uri)
    """
    # Download media
    media_metadata = await download_media(file_id, media_type, message_id)

    if media_metadata is None:
        logger.error(f"Failed to download media {file_id}")
        return {
            "content_json": {
                "file_id": file_id,
                "file_type": media_type,
                "error": "download_failed",
                "status": "failed",
            },
            "uri": None,
        }

    # Create content_json with metadata
    content_json = {
        "file_id": media_metadata.file_id,
        "file_type": media_metadata.file_type,
        "file_size": media_metadata.file_size,
        "mime_type": media_metadata.mime_type,
        "duration": media_metadata.duration,
        "status": "pending",  # Will be processed by async MediaProcessor
        "attempt_count": 0,
        "created_at": None,
    }

    return {
        "content_json": content_json,
        "uri": f"file://{media_metadata.file_path}",
    }


__all__ = ["MediaMetadata", "download_media", "get_artifact_kind", "create_artifact_metadata"]
