"""Normalize Telegram Update objects to internal message format."""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from aiogram.types import Update, Message, CallbackQuery

from app.db.models import MessageRole

logger = logging.getLogger(__name__)


class NormalizedMessage:
    """Normalized message structure from Telegram Update."""

    def __init__(
        self,
        text: Optional[str],
        user_id: str,
        chat_id: str,
        message_id: str,
        timestamp: datetime,
        raw_payload: Dict[str, Any],
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None,
    ):
        self.text = text
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_id = message_id
        self.timestamp = timestamp
        self.raw_payload = raw_payload
        self.media_type = media_type
        self.media_file_id = media_file_id
        self.role = MessageRole.USER  # Always user for incoming messages


class NormalizedCallback:
    """Normalized callback query structure."""

    def __init__(
        self,
        callback_id: str,
        callback_data: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        timestamp: datetime,
        raw_payload: Dict[str, Any],
    ):
        self.callback_id = callback_id
        self.callback_data = callback_data
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_id = message_id
        self.timestamp = timestamp
        self.raw_payload = raw_payload


def normalize_update(update: Update) -> Tuple[Optional[NormalizedMessage], Optional[NormalizedCallback]]:
    """
    Convert Telegram Update to normalized internal format.

    Args:
        update: Telegram Update object

    Returns:
        Tuple of (NormalizedMessage, NormalizedCallback)
        One or both may be None depending on update type
    """
    try:
        # Handle regular message
        if update.message:
            return (normalize_message(update.message), None)

        # Handle callback query (button press)
        if update.callback_query:
            return (None, normalize_callback(update.callback_query))

        # Handle edited message (treat as new message)
        if update.edited_message:
            return (normalize_message(update.edited_message), None)

        logger.warning(f"Unhandled update type: {update.model_dump()}")
        return (None, None)

    except Exception as e:
        logger.error(f"Error normalizing update: {e}", exc_info=True)
        return (None, None)


def normalize_message(message: Message) -> NormalizedMessage:
    """
    Normalize a Telegram Message object.

    Args:
        message: Telegram Message object

    Returns:
        NormalizedMessage
    """
    # Extract basic fields
    user_id = str(message.from_user.id) if message.from_user else "unknown"
    chat_id = str(message.chat.id)
    message_id = str(message.message_id)
    timestamp = message.date if message.date else datetime.now()

    # Extract text
    text = message.text or message.caption

    # Detect media type and file_id
    media_type = None
    media_file_id = None

    if message.voice:
        media_type = "voice"
        media_file_id = message.voice.file_id
    elif message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id  # Largest photo
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.audio:
        media_type = "audio"
        media_file_id = message.audio.file_id
    elif message.video_note:
        media_type = "video_note"
        media_file_id = message.video_note.file_id

    # Store raw payload for debugging
    raw_payload = message.model_dump(mode='json')

    return NormalizedMessage(
        text=text,
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        timestamp=timestamp,
        raw_payload=raw_payload,
        media_type=media_type,
        media_file_id=media_file_id,
    )


def normalize_callback(callback_query: CallbackQuery) -> NormalizedCallback:
    """
    Normalize a Telegram CallbackQuery object (inline button press).

    Args:
        callback_query: Telegram CallbackQuery object

    Returns:
        NormalizedCallback
    """
    callback_id = callback_query.id
    callback_data = callback_query.data or ""
    user_id = str(callback_query.from_user.id)
    chat_id = str(callback_query.message.chat.id) if callback_query.message else "unknown"
    message_id = str(callback_query.message.message_id) if callback_query.message else "unknown"
    timestamp = datetime.now()  # Callback queries don't have built-in timestamp

    raw_payload = callback_query.model_dump(mode='json')

    return NormalizedCallback(
        callback_id=callback_id,
        callback_data=callback_data,
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        timestamp=timestamp,
        raw_payload=raw_payload,
    )


__all__ = ["NormalizedMessage", "NormalizedCallback", "normalize_update", "normalize_message", "normalize_callback"]
