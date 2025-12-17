"""Message operations."""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from .models import ChatMessage, MessageRole
from .queries import (
    INSERT_MESSAGE,
    GET_RECENT_MESSAGES,
    GET_MESSAGE_BY_ID,
    GET_MESSAGE_BY_PLATFORM_ID,
)
from . import get_db

logger = logging.getLogger(__name__)


async def insert_message(
    thread_id: UUID,
    role: MessageRole,
    text: Optional[str] = None,
    author_user_id: Optional[str] = None,
    platform_message_id: Optional[str] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
) -> ChatMessage:
    """
    Insert a new message into the chat thread.

    Args:
        thread_id: Thread UUID
        role: Message role (user/assistant/system)
        text: Message text content
        author_user_id: Platform-specific user ID
        platform_message_id: Platform-specific message ID
        raw_payload: Raw platform message payload (JSON)

    Returns:
        Created ChatMessage instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        role_value = role.value if isinstance(role, MessageRole) else role

        row = await db.fetch_one(
            INSERT_MESSAGE,
            thread_id,
            platform_message_id,
            role_value,
            author_user_id,
            text,
            raw_payload,
        )

        logger.info(
            f"Inserted message {row['id']} in thread {thread_id} (role={role_value})"
        )
        return ChatMessage(**row)

    except Exception as e:
        logger.error(
            f"Error inserting message in thread {thread_id} (role={role}): {e}"
        )
        raise


async def fetch_recent_messages(
    thread_id: UUID, limit: int = 30
) -> List[ChatMessage]:
    """
    Fetch recent messages from a thread.

    Args:
        thread_id: Thread UUID
        limit: Maximum number of messages to fetch (default: 30)

    Returns:
        List of ChatMessage instances, ordered by created_at DESC
    """
    db = get_db()

    try:
        rows = await db.fetch_all(GET_RECENT_MESSAGES, thread_id, limit)

        messages = [ChatMessage(**row) for row in rows]
        logger.debug(f"Fetched {len(messages)} messages from thread {thread_id}")
        return messages

    except Exception as e:
        logger.error(f"Error fetching messages from thread {thread_id}: {e}")
        raise


async def get_message_by_id(message_id: UUID) -> Optional[ChatMessage]:
    """
    Get message by ID.

    Args:
        message_id: Message UUID

    Returns:
        ChatMessage instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_MESSAGE_BY_ID, message_id)

        if row:
            logger.debug(f"Found message: {message_id}")
            return ChatMessage(**row)

        logger.debug(f"Message not found: {message_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching message {message_id}: {e}")
        raise


async def get_message_by_platform_id(
    thread_id: UUID, platform_message_id: str
) -> Optional[ChatMessage]:
    """
    Get message by platform message ID.

    Args:
        thread_id: Thread UUID
        platform_message_id: Platform-specific message ID

    Returns:
        ChatMessage instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_MESSAGE_BY_PLATFORM_ID, thread_id, platform_message_id)

        if row:
            logger.debug(
                f"Found message by platform_id {platform_message_id} in thread {thread_id}"
            )
            return ChatMessage(**row)

        logger.debug(
            f"Message not found by platform_id {platform_message_id} in thread {thread_id}"
        )
        return None

    except Exception as e:
        logger.error(
            f"Error fetching message by platform_id {platform_message_id} in thread {thread_id}: {e}"
        )
        raise


__all__ = [
    "insert_message",
    "fetch_recent_messages",
    "get_message_by_id",
    "get_message_by_platform_id",
]
