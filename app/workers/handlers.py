"""Job handlers for reactive worker."""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from app.db.models import ReactiveJob, JobMode, ApprovalStatus
from app.db.threads import get_thread_by_id
from app.db.messages import get_message_by_id
from app.db.approvals import create_approval, check_approval_status
from app.telegram.responses import send_message, send_approval_request
from app.ai.context import build_conversation_context
from app.ai.haiku import classify_intent
from app.ai.claude import execute_task
from app.config import settings

logger = logging.getLogger(__name__)


async def handle_classify_job(job: ReactiveJob) -> dict:
    """
    Handle CLASSIFY job - Use Haiku to classify intent.

    Args:
        job: ReactiveJob instance

    Returns:
        dict with classification results
    """
    try:
        logger.info(f"Handling CLASSIFY job {job.id}")

        # Get thread and trigger message
        thread = await get_thread_by_id(job.thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {job.thread_id}")

        trigger_message = await get_message_by_id(job.trigger_message_id)
        if not trigger_message:
            raise ValueError(f"Trigger message not found: {job.trigger_message_id}")

        # Build conversation context
        messages = await build_conversation_context(
            job.thread_id,
            limit=settings.MESSAGE_HISTORY_LIMIT
        )

        # Classify intent
        classification = await classify_intent(
            messages=messages,
            trigger_message=trigger_message,
            job_id=job.id,
        )

        logger.info(
            f"Job {job.id} classified: intent={classification.intent}, "
            f"confidence={classification.confidence:.2f}"
        )

        # Return classification result
        return {
            "classification": classification.to_dict(),
            "needs_execution": classification.intent in ["question", "command"],
        }

    except Exception as e:
        logger.error(f"Error handling CLASSIFY job {job.id}: {e}", exc_info=True)
        raise


async def handle_execute_job(job: ReactiveJob) -> dict:
    """
    Handle EXECUTE job - Use Claude to execute task.

    Args:
        job: ReactiveJob instance with classification in payload_json

    Returns:
        dict with execution results
    """
    try:
        logger.info(f"Handling EXECUTE job {job.id}")

        # Get thread
        thread = await get_thread_by_id(job.thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {job.thread_id}")

        # Extract classification from payload
        payload = job.payload_json or {}
        classification = payload.get("classification", {})
        intent = classification.get("intent", "other")
        summary = classification.get("summary", "")
        plan = classification.get("plan", "")
        needs_confirmation = classification.get("needs_confirmation", False)

        # Build conversation context
        messages = await build_conversation_context(
            job.thread_id,
            limit=settings.MESSAGE_HISTORY_LIMIT
        )

        # If needs confirmation, create approval request
        if needs_confirmation:
            logger.info(f"Job {job.id} needs confirmation before execution")

            # Create approval record
            proposal_text = f"**Summary:** {summary}\n\n**Plan:** {plan}"
            approval = await create_approval(
                thread_id=job.thread_id,
                job_id=job.id,
                proposal_text=proposal_text,
            )

            # Send approval request via Telegram
            await send_acknowledgement(
                thread=thread,
                summary=summary,
                plan=plan,
                approval_id=approval.id,
            )

            # Wait for approval
            approved = await wait_for_approval(
                approval_id=approval.id,
                timeout=settings.APPROVAL_TIMEOUT_SECONDS,
            )

            if not approved:
                logger.warning(f"Job {job.id} approval timeout or rejected")
                return {
                    "approved": False,
                    "response": "Approval timeout or rejected",
                }

        # Execute task with Claude
        execution = await execute_task(
            messages=messages,
            intent=intent,
            summary=summary,
            plan=plan,
            job_id=job.id,
        )

        # Send response to user
        await send_response(
            thread=thread,
            text=execution.response_text,
        )

        logger.info(f"Job {job.id} executed successfully")

        return {
            "approved": True if needs_confirmation else None,
            "response": execution.response_text,
            "tool_calls": len(execution.tool_calls),
        }

    except Exception as e:
        logger.error(f"Error handling EXECUTE job {job.id}: {e}", exc_info=True)
        raise


async def handle_answer_job(job: ReactiveJob) -> dict:
    """
    Handle ANSWER job - Direct answer without Claude execution.

    Used for simple responses that don't require full AI processing.

    Args:
        job: ReactiveJob instance with answer in payload_json

    Returns:
        dict with execution results
    """
    try:
        logger.info(f"Handling ANSWER job {job.id}")

        # Get thread
        thread = await get_thread_by_id(job.thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {job.thread_id}")

        # Extract answer from payload
        payload = job.payload_json or {}
        answer_text = payload.get("answer", "")

        if not answer_text:
            raise ValueError("No answer text in payload")

        # Send response
        await send_response(thread=thread, text=answer_text)

        logger.info(f"Job {job.id} answered successfully")

        return {
            "response": answer_text,
        }

    except Exception as e:
        logger.error(f"Error handling ANSWER job {job.id}: {e}", exc_info=True)
        raise


async def send_acknowledgement(
    thread,
    summary: str,
    plan: str,
    approval_id: UUID,
) -> None:
    """
    Send acknowledgement message with OK button.

    Args:
        thread: ChatThread instance
        summary: Summary of request
        plan: Plan for execution
        approval_id: Approval UUID
    """
    try:
        proposal_text = f"**Summary:** {summary}\n\n**Plan:** {plan}"

        await send_approval_request(
            chat_id=thread.chat_id,
            thread_id=thread.id,
            approval_id=approval_id,
            proposal_text=proposal_text,
        )

        logger.info(f"Sent acknowledgement for approval {approval_id}")

    except Exception as e:
        logger.error(f"Error sending acknowledgement: {e}", exc_info=True)
        raise


async def send_response(thread, text: str) -> None:
    """
    Send response message to user.

    Args:
        thread: ChatThread instance
        text: Response text
    """
    try:
        await send_message(
            chat_id=thread.chat_id,
            text=text,
            thread_id=thread.id,
        )

        logger.info(f"Sent response to thread {thread.id}")

    except Exception as e:
        logger.error(f"Error sending response: {e}", exc_info=True)
        raise


async def wait_for_approval(approval_id: UUID, timeout: int = 3600) -> bool:
    """
    Wait for user to approve or reject.

    Polls approval status every 2 seconds until approved, rejected, or timeout.

    Args:
        approval_id: Approval UUID
        timeout: Timeout in seconds (default: 3600 = 1 hour)

    Returns:
        True if approved, False if rejected or timeout
    """
    try:
        start_time = datetime.utcnow()
        poll_interval = 2  # seconds

        while True:
            # Check if timeout exceeded
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= timeout:
                logger.warning(f"Approval {approval_id} timeout after {timeout}s")
                return False

            # Check approval status
            approval = await check_approval_status(approval_id)
            if not approval:
                logger.error(f"Approval {approval_id} not found during wait")
                return False

            if approval.status == ApprovalStatus.APPROVED:
                logger.info(f"Approval {approval_id} approved")
                return True

            if approval.status == ApprovalStatus.REJECTED:
                logger.info(f"Approval {approval_id} rejected")
                return False

            if approval.status == ApprovalStatus.SUPERSEDED:
                logger.info(f"Approval {approval_id} superseded")
                return False

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    except Exception as e:
        logger.error(f"Error waiting for approval {approval_id}: {e}", exc_info=True)
        return False


__all__ = [
    "handle_classify_job",
    "handle_execute_job",
    "handle_answer_job",
    "send_acknowledgement",
    "send_response",
    "wait_for_approval",
]
