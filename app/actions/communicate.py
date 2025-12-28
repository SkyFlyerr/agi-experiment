"""Communication action handlers.

This module handles sending messages to Master and others via Telegram.
"""

import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.telegram import send_message

logger = logging.getLogger(__name__)


async def send_to_master(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send message to Master via Telegram.

    Args:
        details: Action details containing:
            - recipient: "master" or specific chat_id
            - message: Message to send
            - priority: Optional priority (low, medium, high)

    Returns:
        Result dictionary with message status
    """
    message = details.get("message", "")
    priority = details.get("priority", "medium")
    recipient = details.get("recipient", "master")

    if not message:
        logger.error("No message provided")
        raise ValueError("message is required")

    # Resolve recipient
    if recipient == "master":
        # Use first master chat ID from settings
        chat_ids = settings.master_chat_ids_list
        if not chat_ids:
            logger.error("No master chat IDs configured")
            raise ValueError("No master chat IDs configured")
        chat_id = str(chat_ids[0])
    else:
        chat_id = recipient

    logger.info(f"Sending message to {recipient} (priority: {priority})")

    try:
        # Format message with priority indicator if not low
        if priority == "high":
            formatted_message = f"⚠️ HIGH PRIORITY ⚠️\n\n{message}"
        elif priority == "medium":
            formatted_message = f"📌 {message}"
        else:
            formatted_message = message

        # Send message via Telegram
        message_id = await send_message(
            chat_id=chat_id,
            text=formatted_message,
        )

        result = {
            "recipient": recipient,
            "chat_id": chat_id,
            "message_id": message_id,
            "priority": priority,
            "status": "sent",
        }

        logger.info(f"Message sent successfully (message_id: {message_id})")
        return result

    except Exception as e:
        logger.error(f"Error sending message to {recipient}: {e}")
        raise


async def proactive_outreach(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send proactive message to someone (requires high certainty).

    Args:
        details: Action details containing:
            - chat_id: Target chat ID
            - message: Message to send
            - purpose: Why initiating contact

    Returns:
        Result dictionary with message status
    """
    chat_id = details.get("chat_id")
    message = details.get("message", "")
    purpose = details.get("purpose", "unspecified purpose")

    if not chat_id:
        logger.error("No chat_id provided")
        raise ValueError("chat_id is required")

    if not message:
        logger.error("No message provided")
        raise ValueError("message is required")

    logger.info(f"Proactive outreach to {chat_id} (purpose: {purpose})")

    try:
        # Send message via Telegram
        message_id = await send_message(
            chat_id=str(chat_id),
            text=message,
        )

        result = {
            "chat_id": chat_id,
            "message_id": message_id,
            "purpose": purpose,
            "status": "sent",
        }

        logger.info(f"Proactive message sent (message_id: {message_id})")
        return result

    except Exception as e:
        logger.error(f"Error in proactive outreach to {chat_id}: {e}")
        raise


__all__ = ["send_to_master", "proactive_outreach"]
