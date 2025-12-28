"""Job operations."""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from .models import ReactiveJob, JobStatus, JobMode
from .queries import (
    ENQUEUE_JOB,
    POLL_PENDING_JOBS,
    UPDATE_JOB_STATUS,
    GET_JOB_BY_ID,
    CANCEL_PENDING_JOBS_FOR_THREAD,
)
from . import get_db

logger = logging.getLogger(__name__)


async def enqueue_job(
    thread_id: UUID,
    trigger_message_id: UUID,
    mode: JobMode,
    payload_json: Optional[Dict[str, Any]] = None,
) -> ReactiveJob:
    """
    Enqueue a new reactive job.

    Args:
        thread_id: Thread UUID
        trigger_message_id: Message UUID that triggered the job
        mode: Job mode (classify, plan, execute, answer)
        payload_json: Optional job payload (JSON dict)

    Returns:
        Created ReactiveJob instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        mode_value = mode.value if isinstance(mode, JobMode) else mode

        row = await db.fetch_one(
            ENQUEUE_JOB,
            thread_id,
            trigger_message_id,
            mode_value,
            payload_json,
        )

        logger.info(
            f"Enqueued job {row['id']} in thread {thread_id} (mode={mode_value})"
        )
        return ReactiveJob(**row)

    except Exception as e:
        logger.error(
            f"Error enqueuing job in thread {thread_id} (mode={mode}): {e}"
        )
        raise


async def poll_pending_jobs(limit: int = 10) -> List[ReactiveJob]:
    """
    Poll for pending jobs to process.

    Args:
        limit: Maximum number of jobs to fetch (default: 10)

    Returns:
        List of ReactiveJob instances with status='queued', ordered by created_at ASC
    """
    db = get_db()

    try:
        rows = await db.fetch_all(POLL_PENDING_JOBS, limit)

        jobs = [ReactiveJob(**row) for row in rows]
        logger.debug(f"Polled {len(jobs)} pending jobs")
        return jobs

    except Exception as e:
        logger.error(f"Error polling pending jobs: {e}")
        raise


async def update_job_status(
    job_id: UUID,
    status: JobStatus,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> ReactiveJob:
    """
    Update job status and timestamps.

    Args:
        job_id: Job UUID
        status: New job status
        started_at: Optional start timestamp
        finished_at: Optional finish timestamp

    Returns:
        Updated ReactiveJob instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        status_value = status.value if isinstance(status, JobStatus) else status

        row = await db.fetch_one(
            UPDATE_JOB_STATUS,
            job_id,
            status_value,
            started_at,
            finished_at,
        )

        if not row:
            raise ValueError(f"Job not found: {job_id}")

        logger.info(f"Updated job {job_id} status to {status_value}")
        return ReactiveJob(**row)

    except Exception as e:
        logger.error(f"Error updating job {job_id} status: {e}")
        raise


async def get_job_by_id(job_id: UUID) -> Optional[ReactiveJob]:
    """
    Get job by ID.

    Args:
        job_id: Job UUID

    Returns:
        ReactiveJob instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_JOB_BY_ID, job_id)

        if row:
            logger.debug(f"Found job: {job_id}")
            return ReactiveJob(**row)

        logger.debug(f"Job not found: {job_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise


async def cancel_pending_jobs_for_thread(thread_id: UUID) -> None:
    """
    Cancel all pending jobs for a thread.

    This is useful when a new message arrives and previous pending jobs
    should be superseded.

    Args:
        thread_id: Thread UUID
    """
    db = get_db()

    try:
        result = await db.execute(CANCEL_PENDING_JOBS_FOR_THREAD, thread_id)
        logger.info(f"Canceled pending jobs for thread {thread_id}: {result}")

    except Exception as e:
        logger.error(f"Error canceling pending jobs for thread {thread_id}: {e}")
        raise


__all__ = [
    "enqueue_job",
    "poll_pending_jobs",
    "update_job_status",
    "get_job_by_id",
    "cancel_pending_jobs_for_thread",
]
