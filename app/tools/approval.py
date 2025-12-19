"""
Tool approval system for AGI agent.

Manages approval requests for tools that require Master's permission before execution.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

from app.db import get_db
from app.telegram import send_message
from app.config import settings

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest:
    """Approval request for tool execution"""

    def __init__(
        self,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        reasoning: str,
        created_at: datetime,
        expires_at: datetime,
        status: ApprovalStatus = ApprovalStatus.PENDING,
        response: Optional[str] = None,
    ):
        self.request_id = request_id
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.reasoning = reasoning
        self.created_at = created_at
        self.expires_at = expires_at
        self.status = status
        self.response = response


async def create_approval_request(
    tool_name: str,
    tool_input: Dict[str, Any],
    reasoning: str,
    timeout_seconds: Optional[int] = None,
) -> str:
    """
    Create a new approval request and notify Master.

    Args:
        tool_name: Name of the tool requiring approval
        tool_input: Tool input arguments
        reasoning: Explanation of why this tool is being used
        timeout_seconds: Timeout for approval (default: from config)

    Returns:
        Request ID (UUID)
    """
    try:
        db = get_db()

        # Generate request ID
        import uuid
        request_id = str(uuid.uuid4())

        # Calculate expiration
        timeout = timeout_seconds or settings.APPROVAL_TIMEOUT_SECONDS
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)

        # Store in database
        await db.execute(
            """
            INSERT INTO tool_approvals (
                request_id,
                tool_name,
                tool_input,
                reasoning,
                created_at,
                expires_at,
                status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            request_id,
            tool_name,
            json.dumps(tool_input),
            reasoning,
            datetime.utcnow(),
            expires_at,
            ApprovalStatus.PENDING.value,
        )

        # Send Telegram notification to Master
        await _notify_approval_request(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            reasoning=reasoning,
        )

        logger.info(f"Created approval request {request_id} for tool: {tool_name}")
        return request_id

    except Exception as e:
        logger.error(f"Error creating approval request: {e}", exc_info=True)
        raise


async def get_approval_status(request_id: str) -> Optional[ApprovalRequest]:
    """
    Get approval request status.

    Args:
        request_id: Request ID

    Returns:
        ApprovalRequest or None if not found
    """
    try:
        db = get_db()

        row = await db.fetch_one(
            """
            SELECT
                request_id,
                tool_name,
                tool_input,
                reasoning,
                created_at,
                expires_at,
                status,
                response
            FROM tool_approvals
            WHERE request_id = $1
            """,
            request_id,
        )

        if not row:
            return None

        # Check if expired
        status = ApprovalStatus(row["status"])
        if status == ApprovalStatus.PENDING and datetime.utcnow() > row["expires_at"]:
            # Mark as expired
            await db.execute(
                "UPDATE tool_approvals SET status = $1 WHERE request_id = $2",
                ApprovalStatus.EXPIRED.value,
                request_id,
            )
            status = ApprovalStatus.EXPIRED

        return ApprovalRequest(
            request_id=row["request_id"],
            tool_name=row["tool_name"],
            tool_input=json.loads(row["tool_input"]),
            reasoning=row["reasoning"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            status=status,
            response=row["response"],
        )

    except Exception as e:
        logger.error(f"Error getting approval status: {e}", exc_info=True)
        return None


async def approve_request(request_id: str, response: Optional[str] = None) -> bool:
    """
    Approve a pending request.

    Args:
        request_id: Request ID
        response: Optional response message from Master

    Returns:
        True if approved successfully, False otherwise
    """
    try:
        db = get_db()

        # Update status
        result = await db.execute(
            """
            UPDATE tool_approvals
            SET status = $1, response = $2, responded_at = $3
            WHERE request_id = $4 AND status = $5
            """,
            ApprovalStatus.APPROVED.value,
            response,
            datetime.utcnow(),
            request_id,
            ApprovalStatus.PENDING.value,
        )

        if result:
            logger.info(f"Approved request: {request_id}")
            return True
        else:
            logger.warning(f"Failed to approve request: {request_id} (may already be resolved)")
            return False

    except Exception as e:
        logger.error(f"Error approving request: {e}", exc_info=True)
        return False


async def reject_request(request_id: str, response: Optional[str] = None) -> bool:
    """
    Reject a pending request.

    Args:
        request_id: Request ID
        response: Optional rejection reason from Master

    Returns:
        True if rejected successfully, False otherwise
    """
    try:
        db = get_db()

        # Update status
        result = await db.execute(
            """
            UPDATE tool_approvals
            SET status = $1, response = $2, responded_at = $3
            WHERE request_id = $4 AND status = $5
            """,
            ApprovalStatus.REJECTED.value,
            response,
            datetime.utcnow(),
            request_id,
            ApprovalStatus.PENDING.value,
        )

        if result:
            logger.info(f"Rejected request: {request_id}")
            return True
        else:
            logger.warning(f"Failed to reject request: {request_id} (may already be resolved)")
            return False

    except Exception as e:
        logger.error(f"Error rejecting request: {e}", exc_info=True)
        return False


async def get_pending_approvals() -> List[ApprovalRequest]:
    """
    Get all pending approval requests.

    Returns:
        List of pending ApprovalRequest objects
    """
    try:
        db = get_db()

        rows = await db.fetch_all(
            """
            SELECT
                request_id,
                tool_name,
                tool_input,
                reasoning,
                created_at,
                expires_at,
                status,
                response
            FROM tool_approvals
            WHERE status = $1
            ORDER BY created_at DESC
            """,
            ApprovalStatus.PENDING.value,
        )

        approvals = []
        for row in rows:
            # Check if expired
            if datetime.utcnow() > row["expires_at"]:
                # Mark as expired
                await db.execute(
                    "UPDATE tool_approvals SET status = $1 WHERE request_id = $2",
                    ApprovalStatus.EXPIRED.value,
                    row["request_id"],
                )
                continue

            approvals.append(
                ApprovalRequest(
                    request_id=row["request_id"],
                    tool_name=row["tool_name"],
                    tool_input=json.loads(row["tool_input"]),
                    reasoning=row["reasoning"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    status=ApprovalStatus(row["status"]),
                    response=row["response"],
                )
            )

        return approvals

    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}", exc_info=True)
        return []


async def _notify_approval_request(
    request_id: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    reasoning: str,
) -> None:
    """Send Telegram notification for approval request"""
    try:
        master_chat_ids = settings.master_chat_ids_list
        if not master_chat_ids:
            logger.warning("No master chat IDs configured for approval notification")
            return

        # Format tool input nicely
        tool_input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)

        # Truncate if too long
        if len(tool_input_str) > 500:
            tool_input_str = tool_input_str[:500] + "\n... (truncated)"

        message = f"""🔐 <b>Tool Approval Required</b>

<b>Tool:</b> <code>{tool_name}</code>
<b>Request ID:</b> <code>{request_id}</code>

<b>Reasoning:</b>
{reasoning}

<b>Tool Input:</b>
<pre>{tool_input_str}</pre>

<b>To approve:</b> /approve {request_id}
<b>To reject:</b> /reject {request_id}
"""

        await send_message(
            chat_id=str(master_chat_ids[0]),
            text=message
        )

        logger.info(f"Sent approval notification for request: {request_id}")

    except Exception as e:
        logger.error(f"Error sending approval notification: {e}", exc_info=True)


__all__ = [
    "ApprovalStatus",
    "ApprovalRequest",
    "create_approval_request",
    "get_approval_status",
    "approve_request",
    "reject_request",
    "get_pending_approvals",
]
