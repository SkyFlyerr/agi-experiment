"""Ask Master action handler.

This module handles requesting guidance from Master when agent is uncertain.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.telegram import send_message
from app.db import get_db
from app.db.approvals import create_approval, get_approval
from app.db.models import ApprovalStatus
from uuid import uuid4

logger = logging.getLogger(__name__)


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ask Master for guidance.

    Args:
        details: Action details containing:
            - question: Clear, concise question
            - context: Why guidance is needed

    Returns:
        Result dictionary with Master's response (or timeout)
    """
    question = details.get("question", "")
    context = details.get("context", "")

    if not question:
        logger.error("No question provided")
        raise ValueError("question is required")

    logger.info(f"Asking Master for guidance: {question}")

    try:
        # Get Master's chat ID
        chat_ids = settings.master_chat_ids_list
        if not chat_ids:
            logger.error("No master chat IDs configured")
            raise ValueError("No master chat IDs configured")

        master_chat_id = str(chat_ids[0])

        # Format message with question and context
        message = f"🤔 <b>Guidance Needed</b>\n\n"
        message += f"<b>Question:</b>\n{question}\n\n"
        if context:
            message += f"<b>Context:</b>\n{context}\n\n"
        message += f"<i>Awaiting your guidance...</i>"

        # Send message to Master
        message_id = await send_message(
            chat_id=master_chat_id,
            text=message,
            parse_mode="HTML",
        )

        # Create approval record in database
        # (We'll use approval system for tracking responses)
        db = get_db()

        # We need a dummy thread_id and job_id - for proactive actions,
        # we can use a special placeholder or create a proactive_actions table
        # For now, use a special UUID pattern
        dummy_thread_id = uuid4()
        dummy_job_id = uuid4()

        approval = await create_approval(
            thread_id=dummy_thread_id,
            job_id=dummy_job_id,
            proposal_text=question,
        )

        # Wait for response (with timeout)
        timeout = settings.APPROVAL_TIMEOUT_SECONDS
        logger.info(f"Waiting for Master's response (timeout: {timeout}s)")

        start_time = datetime.utcnow()
        elapsed = 0
        check_interval = 5  # Check every 5 seconds

        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            # Check if approval was resolved
            updated_approval = await get_approval(approval.id)

            if updated_approval and updated_approval.status != ApprovalStatus.PENDING:
                logger.info(
                    f"Master responded: {updated_approval.status.value} "
                    f"(after {elapsed:.1f}s)"
                )

                return {
                    "question": question,
                    "context": context,
                    "response_status": updated_approval.status.value,
                    "wait_time": elapsed,
                    "message_id": message_id,
                    "status": "answered",
                }

        # Timeout reached
        logger.warning(f"Master response timeout after {timeout}s")

        return {
            "question": question,
            "context": context,
            "response_status": "timeout",
            "wait_time": timeout,
            "message_id": message_id,
            "status": "timeout",
            "note": "Proceeding with default behavior after timeout",
        }

    except Exception as e:
        logger.error(f"Error asking Master: {e}")
        raise


__all__ = ["execute"]
