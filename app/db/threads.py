"""Thread operations."""

import logging
from typing import Optional
from uuid import UUID

from .models import ChatThread
from .queries import GET_THREAD_BY_CHAT_ID, GET_THREAD_BY_ID, CREATE_THREAD, UPDATE_THREAD_TIMESTAMP
from . import get_db

logger = logging.getLogger(__name__)


async def get_or_create_thread(platform: str, chat_id: str) -> ChatThread:
    """
    Get existing thread or create new one.

    Args:
        platform: Platform name (e.g., "telegram")
        chat_id: Chat ID on the platform

    Returns:
        ChatThread instance
    """
    db = get_db()

    try:
        # Try to get existing thread
        row = await db.fetch_one(GET_THREAD_BY_CHAT_ID, platform, chat_id)

        if row:
            logger.debug(f"Found existing thread: {row['id']} for {platform}:{chat_id}")
            return ChatThread(**row)

        # Create new thread if not found
        row = await db.fetch_one(CREATE_THREAD, platform, chat_id)
        logger.info(f"Created new thread: {row['id']} for {platform}:{chat_id}")
        return ChatThread(**row)

    except Exception as e:
        logger.error(f"Error in get_or_create_thread for {platform}:{chat_id}: {e}")
        raise


async def update_thread(thread_id: UUID) -> ChatThread:
    """
    Update thread's updated_at timestamp.

    Args:
        thread_id: Thread UUID

    Returns:
        Updated ChatThread instance
    """
    db = get_db()

    try:
        row = await db.fetch_one(UPDATE_THREAD_TIMESTAMP, thread_id)

        if not row:
            raise ValueError(f"Thread not found: {thread_id}")

        logger.debug(f"Updated thread: {thread_id}")
        return ChatThread(**row)

    except Exception as e:
        logger.error(f"Error updating thread {thread_id}: {e}")
        raise


async def get_thread_by_chat_id(platform: str, chat_id: str) -> Optional[ChatThread]:
    """
    Get thread by platform and chat_id.

    Args:
        platform: Platform name (e.g., "telegram")
        chat_id: Chat ID on the platform

    Returns:
        ChatThread instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_THREAD_BY_CHAT_ID, platform, chat_id)

        if row:
            logger.debug(f"Found thread: {row['id']} for {platform}:{chat_id}")
            return ChatThread(**row)

        logger.debug(f"No thread found for {platform}:{chat_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching thread for {platform}:{chat_id}: {e}")
        raise


async def get_thread_by_id(thread_id: UUID) -> Optional[ChatThread]:
    """
    Get thread by ID.

    Args:
        thread_id: Thread UUID

    Returns:
        ChatThread instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_THREAD_BY_ID, thread_id)

        if row:
            logger.debug(f"Found thread: {thread_id}")
            return ChatThread(**row)

        logger.debug(f"Thread not found: {thread_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching thread {thread_id}: {e}")
        raise


__all__ = [
    "get_or_create_thread",
    "update_thread",
    "get_thread_by_chat_id",
    "get_thread_by_id",
]
