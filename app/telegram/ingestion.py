"""Message ingestion pipeline for Telegram updates."""

import logging
from typing import Optional
from uuid import UUID
import asyncio

from aiogram.types import Update

from app.telegram.normalizer import normalize_update, NormalizedMessage, NormalizedCallback
from app.telegram.callbacks import handle_callback_query
from app.telegram.media import create_artifact_metadata, get_artifact_kind
from app.db import get_db
from app.db.queries import (
    CREATE_THREAD,
    INSERT_MESSAGE,
    INSERT_ARTIFACT,
    ENQUEUE_JOB,
)
from app.db.models import JobMode

logger = logging.getLogger(__name__)


async def ingest_telegram_update(update: Update) -> None:
    """
    Main ingestion pipeline for Telegram updates.

    This function:
    1. Normalizes the update
    2. Persists messages to database
    3. Downloads and stores media artifacts
    4. Enqueues reactive jobs
    5. Handles callback queries

    Args:
        update: Telegram Update object
    """
    try:
        # Normalize update
        normalized_message, normalized_callback = normalize_update(update)

        # Handle callback query (button press)
        if normalized_callback:
            await handle_callback_query(normalized_callback)
            return

        # Handle regular message
        if normalized_message:
            await ingest_message(normalized_message)

    except Exception as e:
        logger.error(f"Error ingesting Telegram update: {e}", exc_info=True)


async def ingest_message(message: NormalizedMessage) -> Optional[UUID]:
    """
    Ingest a normalized message into the database.

    Steps:
    1. Get or create thread
    2. Insert message
    3. Handle media artifacts
    4. Enqueue reactive job
    5. Wake reactive worker

    Args:
        message: NormalizedMessage object

    Returns:
        Message UUID if successful, None otherwise
    """
    try:
        db = get_db()

        # Step 1: Get or create thread
        thread = await db.fetch_one(
            CREATE_THREAD,
            "telegram",  # platform
            message.chat_id
        )

        if not thread:
            logger.error(f"Failed to create thread for chat {message.chat_id}")
            return None

        thread_id = thread['id']
        logger.info(f"Thread {thread_id} for chat {message.chat_id}")

        # Step 2: Insert message
        stored_message = await db.fetch_one(
            INSERT_MESSAGE,
            thread_id,
            message.message_id,  # platform_message_id
            message.role.value,
            message.user_id,  # author_user_id
            message.text,
            message.raw_payload
        )

        if not stored_message:
            logger.error(f"Failed to insert message {message.message_id}")
            return None

        message_id = stored_message['id']
        logger.info(f"Message {message_id} inserted (platform_id: {message.message_id})")

        # Step 3: Handle media artifacts
        if message.media_type and message.media_file_id:
            await ingest_media_artifact(message_id, message.media_type, message.media_file_id)

        # Step 4: Enqueue reactive job
        job = await db.fetch_one(
            ENQUEUE_JOB,
            thread_id,
            message_id,  # trigger_message_id
            JobMode.CLASSIFY.value,  # Start with classify mode
            None  # payload_json
        )

        if job:
            logger.info(f"Reactive job {job['id']} enqueued for message {message_id}")
        else:
            logger.error(f"Failed to enqueue job for message {message_id}")

        # Step 5: Wake reactive worker (async, non-blocking)
        asyncio.create_task(wake_reactive_worker())

        return message_id

    except Exception as e:
        logger.error(f"Error ingesting message: {e}", exc_info=True)
        return None


async def ingest_media_artifact(
    message_id: UUID,
    media_type: str,
    file_id: str
) -> Optional[UUID]:
    """
    Download media and create artifact entry.

    Args:
        message_id: Message UUID
        media_type: Type of media (voice, photo, document, video, audio)
        file_id: Telegram file_id

    Returns:
        Artifact UUID if successful, None otherwise
    """
    try:
        db = get_db()

        # Create artifact metadata (downloads file)
        artifact_data = await create_artifact_metadata(media_type, file_id, message_id)

        # Determine artifact kind
        artifact_kind = get_artifact_kind(media_type)

        # Insert artifact
        artifact = await db.fetch_one(
            INSERT_ARTIFACT,
            message_id,
            artifact_kind.value,
            artifact_data['content_json'],
            artifact_data['uri']
        )

        if artifact:
            logger.info(
                f"Artifact {artifact['id']} created for message {message_id} "
                f"(type: {media_type}, kind: {artifact_kind.value})"
            )
            return artifact['id']
        else:
            logger.error(f"Failed to insert artifact for message {message_id}")
            return None

    except Exception as e:
        logger.error(f"Error ingesting media artifact: {e}", exc_info=True)
        return None


async def wake_reactive_worker() -> None:
    """
    Wake reactive worker to process pending jobs.

    This is a non-blocking signal to the worker.
    The actual waking mechanism depends on the worker implementation
    (could be asyncio.Event, queue, or periodic polling).
    """
    try:
        # TODO: Implement actual wake mechanism
        # For now, worker polls database periodically
        logger.debug("Reactive worker wake signal sent")
    except Exception as e:
        logger.error(f"Error waking reactive worker: {e}", exc_info=True)


__all__ = ["ingest_telegram_update", "ingest_message", "ingest_media_artifact"]
