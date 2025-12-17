"""Handle Telegram callback queries (inline button presses)."""

import logging
from uuid import UUID

from app.telegram.bot import get_bot
from app.telegram.normalizer import NormalizedCallback
from app.db import get_db
from app.db.queries import RESOLVE_APPROVAL, GET_JOB_BY_ID, UPDATE_JOB_STATUS
from app.db.models import ApprovalStatus, JobMode

logger = logging.getLogger(__name__)


async def handle_callback_query(callback: NormalizedCallback) -> None:
    """
    Handle callback query from inline button press.

    Expected callback_data format:
    - "approval:{approval_id}" - User clicked OK button to approve action

    Args:
        callback: NormalizedCallback object
    """
    try:
        bot = get_bot()

        # Parse callback data
        if callback.callback_data.startswith("approval:"):
            await handle_approval_callback(callback)
        else:
            logger.warning(f"Unknown callback_data format: {callback.callback_data}")

        # Answer callback query to remove loading state
        await bot.answer_callback_query(callback.callback_id)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}", exc_info=True)
        # Still try to answer callback to prevent loading state
        try:
            bot = get_bot()
            await bot.answer_callback_query(
                callback.callback_id,
                text="Error processing request. Please try again.",
                show_alert=True
            )
        except Exception:
            pass


async def handle_approval_callback(callback: NormalizedCallback) -> None:
    """
    Handle approval callback (OK button press).

    Updates approval status to 'approved' and transitions job mode from
    classify → execute.

    Args:
        callback: NormalizedCallback object
    """
    try:
        # Extract approval_id from callback_data
        approval_id_str = callback.callback_data.replace("approval:", "")
        approval_id = UUID(approval_id_str)

        db = get_db()

        # Resolve approval as approved
        approval = await db.fetch_one(
            RESOLVE_APPROVAL,
            approval_id,
            ApprovalStatus.APPROVED.value
        )

        if not approval:
            logger.error(f"Approval {approval_id} not found")
            return

        logger.info(f"Approval {approval_id} marked as approved by user {callback.user_id}")

        # Get associated job
        job = await db.fetch_one(GET_JOB_BY_ID, approval['job_id'])

        if not job:
            logger.error(f"Job {approval['job_id']} not found for approval {approval_id}")
            return

        # Transition job mode: classify → execute
        if job['mode'] == JobMode.CLASSIFY.value:
            # Update job mode to execute
            await db.execute(
                """
                UPDATE reactive_jobs
                SET mode = $2
                WHERE id = $1
                """,
                job['id'],
                JobMode.EXECUTE.value
            )

            logger.info(f"Job {job['id']} transitioned from classify → execute")

            # Enqueue new execute job (triggers reactive worker)
            # The reactive worker will pick this up automatically

        # Update button text to show approval
        bot = get_bot()
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.chat_id,
                message_id=int(callback.message_id),
                reply_markup=None  # Remove buttons
            )

            # Optionally add checkmark to message text
            await bot.edit_message_text(
                chat_id=callback.chat_id,
                message_id=int(callback.message_id),
                text=f"{approval['proposal_text']}\n\n✅ <b>Approved</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not update message after approval: {e}")

    except ValueError as e:
        logger.error(f"Invalid approval_id format: {e}")
    except Exception as e:
        logger.error(f"Error handling approval callback: {e}", exc_info=True)


__all__ = ["handle_callback_query", "handle_approval_callback"]
