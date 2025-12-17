"""Format and send responses via Telegram."""

import logging
from typing import Optional, List
from uuid import UUID

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from app.telegram.bot import get_bot
from app.db import get_db
from app.db.queries import INSERT_MESSAGE
from app.db.models import MessageRole

logger = logging.getLogger(__name__)

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


def escape_html(text: str) -> str:
    """
    Escape HTML special characters for Telegram HTML parse mode.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Split long message into chunks that fit Telegram's limit.

    Args:
        text: Message text
        max_length: Maximum length per chunk

    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.rstrip())
            current_chunk = line + "\n"

    if current_chunk:
        chunks.append(current_chunk.rstrip())

    return chunks


def create_approval_keyboard(approval_id: UUID) -> InlineKeyboardMarkup:
    """
    Create inline keyboard with OK button for approval.

    Args:
        approval_id: Approval UUID

    Returns:
        InlineKeyboardMarkup with OK button
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ OK",
                    callback_data=f"approval:{approval_id}"
                )
            ]
        ]
    )
    return keyboard


async def send_message(
    chat_id: str,
    text: str,
    thread_id: Optional[UUID] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Optional[str]:
    """
    Send message via Telegram and persist to database.

    Args:
        chat_id: Telegram chat ID
        text: Message text (HTML formatted)
        thread_id: Optional thread ID for database persistence
        reply_markup: Optional inline keyboard

    Returns:
        Sent message ID (platform_message_id) or None if failed
    """
    try:
        bot = get_bot()

        # Split message if too long
        chunks = split_long_message(text)

        sent_message_ids = []

        for chunk in chunks:
            # Send only the last chunk with reply_markup
            markup = reply_markup if chunk == chunks[-1] else None

            sent_message = await bot.send_message(
                chat_id=int(chat_id),
                text=chunk,
                parse_mode="HTML",
                reply_markup=markup
            )

            platform_message_id = str(sent_message.message_id)
            sent_message_ids.append(platform_message_id)

            logger.info(f"Sent message {platform_message_id} to chat {chat_id}")

            # Persist to database if thread_id provided
            if thread_id:
                db = get_db()
                await db.fetch_one(
                    INSERT_MESSAGE,
                    thread_id,
                    platform_message_id,
                    MessageRole.ASSISTANT.value,
                    None,  # author_user_id (bot has no user_id)
                    chunk,
                    {"sent_at": sent_message.date.isoformat()}
                )

        # Return last message ID (for reply reference)
        return sent_message_ids[-1] if sent_message_ids else None

    except TelegramBadRequest as e:
        logger.error(f"Telegram API error sending message: {e}")
        return None
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        return None


async def send_approval_request(
    chat_id: str,
    thread_id: UUID,
    approval_id: UUID,
    proposal_text: str,
) -> Optional[str]:
    """
    Send approval request with OK button.

    Args:
        chat_id: Telegram chat ID
        thread_id: Thread UUID
        approval_id: Approval UUID
        proposal_text: Text describing what needs approval

    Returns:
        Sent message ID or None if failed
    """
    try:
        # Format proposal text
        formatted_text = f"<b>🤔 Approval Required</b>\n\n{proposal_text}\n\n<i>Press OK to approve</i>"

        # Create keyboard with OK button
        keyboard = create_approval_keyboard(approval_id)

        # Send message
        return await send_message(
            chat_id=chat_id,
            text=formatted_text,
            thread_id=thread_id,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error sending approval request: {e}", exc_info=True)
        return None


async def send_error_message(chat_id: str, error_text: str) -> None:
    """
    Send error message to user.

    Args:
        chat_id: Telegram chat ID
        error_text: Error description
    """
    try:
        formatted_text = f"<b>⚠️ Error</b>\n\n{escape_html(error_text)}"
        await send_message(chat_id=chat_id, text=formatted_text)
    except Exception as e:
        logger.error(f"Error sending error message: {e}", exc_info=True)


__all__ = [
    "escape_html",
    "split_long_message",
    "create_approval_keyboard",
    "send_message",
    "send_approval_request",
    "send_error_message",
]
