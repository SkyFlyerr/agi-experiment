"""Approval operations."""

import logging
from typing import Optional
from uuid import UUID

from .models import Approval, ApprovalStatus
from .queries import (
    CREATE_APPROVAL,
    GET_APPROVAL_BY_ID,
    RESOLVE_APPROVAL,
    SUPERSEDE_PENDING_APPROVALS,
    GET_PENDING_APPROVAL_FOR_JOB,
)
from . import get_db

logger = logging.getLogger(__name__)


async def create_approval(
    thread_id: UUID,
    job_id: UUID,
    proposal_text: str,
) -> Approval:
    """
    Create a new approval request.

    Args:
        thread_id: Thread UUID
        job_id: Job UUID requiring approval
        proposal_text: Text describing what is being proposed for approval

    Returns:
        Created Approval instance
    """
    db = get_db()

    try:
        row = await db.fetch_one(
            CREATE_APPROVAL,
            thread_id,
            job_id,
            proposal_text,
        )

        logger.info(
            f"Created approval {row['id']} for job {job_id} in thread {thread_id}"
        )
        return Approval(**row)

    except Exception as e:
        logger.error(
            f"Error creating approval for job {job_id} in thread {thread_id}: {e}"
        )
        raise


async def check_approval_status(approval_id: UUID) -> Optional[Approval]:
    """
    Check the current status of an approval.

    Args:
        approval_id: Approval UUID

    Returns:
        Approval instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_APPROVAL_BY_ID, approval_id)

        if row:
            logger.debug(f"Found approval {approval_id} with status {row['status']}")
            return Approval(**row)

        logger.debug(f"Approval not found: {approval_id}")
        return None

    except Exception as e:
        logger.error(f"Error checking approval status {approval_id}: {e}")
        raise


async def resolve_approval(
    approval_id: UUID,
    status: ApprovalStatus,
) -> Approval:
    """
    Resolve an approval (approve/reject).

    Args:
        approval_id: Approval UUID
        status: New approval status (approved/rejected)

    Returns:
        Updated Approval instance

    Raises:
        ValueError: If status is not 'approved' or 'rejected'
    """
    if status not in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
        raise ValueError(
            f"Invalid approval status: {status}. Must be 'approved' or 'rejected'."
        )

    db = get_db()

    try:
        # Convert enum to string value
        status_value = status.value if isinstance(status, ApprovalStatus) else status

        row = await db.fetch_one(
            RESOLVE_APPROVAL,
            approval_id,
            status_value,
        )

        if not row:
            raise ValueError(f"Approval not found: {approval_id}")

        logger.info(f"Resolved approval {approval_id} as {status_value}")
        return Approval(**row)

    except Exception as e:
        logger.error(f"Error resolving approval {approval_id}: {e}")
        raise


async def supersede_pending_approvals(thread_id: UUID) -> None:
    """
    Mark all pending approvals in a thread as superseded.

    This is useful when new input arrives that makes previous pending
    approvals irrelevant.

    Args:
        thread_id: Thread UUID
    """
    db = get_db()

    try:
        result = await db.execute(SUPERSEDE_PENDING_APPROVALS, thread_id)
        logger.info(f"Superseded pending approvals for thread {thread_id}: {result}")

    except Exception as e:
        logger.error(f"Error superseding pending approvals for thread {thread_id}: {e}")
        raise


async def get_pending_approval_for_job(job_id: UUID) -> Optional[Approval]:
    """
    Get pending approval for a specific job.

    Args:
        job_id: Job UUID

    Returns:
        Approval instance or None if no pending approval found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_PENDING_APPROVAL_FOR_JOB, job_id)

        if row:
            logger.debug(f"Found pending approval for job {job_id}")
            return Approval(**row)

        logger.debug(f"No pending approval found for job {job_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching pending approval for job {job_id}: {e}")
        raise


__all__ = [
    "create_approval",
    "check_approval_status",
    "resolve_approval",
    "supersede_pending_approvals",
    "get_pending_approval_for_job",
]
