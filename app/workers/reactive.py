"""Reactive worker - polls and processes reactive jobs."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.db.models import JobStatus, JobMode
from app.db.jobs import poll_pending_jobs, update_job_status
from .handlers import handle_classify_job, handle_execute_job, handle_answer_job

logger = logging.getLogger(__name__)


class ReactiveWorker:
    """
    Reactive worker that polls for pending jobs and processes them.

    Processing flow:
    1. Poll for pending jobs (every 100ms)
    2. Pick first job and mark as RUNNING
    3. Route to appropriate handler based on mode
    4. Update job status to DONE or FAILED
    5. Repeat

    The worker runs continuously until stopped.
    """

    def __init__(self, poll_interval_ms: int = 100):
        """
        Initialize reactive worker.

        Args:
            poll_interval_ms: Polling interval in milliseconds (default: 100)
        """
        self.poll_interval = poll_interval_ms / 1000.0  # Convert to seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the reactive worker loop."""
        if self._running:
            logger.warning("Reactive worker already running")
            return

        self._running = True
        logger.info("Starting reactive worker")

        # Start background task
        self._task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop the reactive worker loop gracefully."""
        if not self._running:
            logger.warning("Reactive worker not running")
            return

        logger.info("Stopping reactive worker")
        self._running = False

        # Wait for current task to complete
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Reactive worker task did not complete within timeout")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        logger.info("Reactive worker stopped")

    async def _worker_loop(self) -> None:
        """
        Main worker loop - polls and processes jobs continuously.

        This loop is resilient and will not crash on errors.
        """
        logger.info("Reactive worker loop started")

        while self._running:
            try:
                # Poll for pending jobs
                jobs = await poll_pending_jobs(limit=1)

                if jobs:
                    # Process first job
                    job = jobs[0]
                    await self._process_job(job)
                else:
                    # No jobs, wait before next poll
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                # Sleep before retry to avoid tight error loop
                await asyncio.sleep(1.0)

        logger.info("Reactive worker loop exited")

    async def _process_job(self, job) -> None:
        """
        Process a single job.

        Args:
            job: ReactiveJob instance
        """
        try:
            logger.info(f"Processing job {job.id} (mode={job.mode.value})")

            # Update job status to RUNNING
            await update_job_status(
                job_id=job.id,
                status=JobStatus.RUNNING,
                started_at=datetime.utcnow(),
            )

            # Route to appropriate handler
            if job.mode == JobMode.CLASSIFY:
                result = await handle_classify_job(job)
            elif job.mode == JobMode.EXECUTE:
                result = await handle_execute_job(job)
            elif job.mode == JobMode.ANSWER:
                result = await handle_answer_job(job)
            else:
                raise ValueError(f"Unknown job mode: {job.mode}")

            # Update job status to DONE
            await update_job_status(
                job_id=job.id,
                status=JobStatus.DONE,
                finished_at=datetime.utcnow(),
            )

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}", exc_info=True)

            # Update job status to FAILED
            try:
                await update_job_status(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    finished_at=datetime.utcnow(),
                )
            except Exception as update_error:
                logger.error(
                    f"Failed to update job {job.id} status to FAILED: {update_error}"
                )

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running


__all__ = [
    "ReactiveWorker",
]
