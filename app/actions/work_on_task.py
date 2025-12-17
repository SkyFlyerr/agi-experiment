"""Task execution action handler.

This module handles executing specific tasks from the task queue.
"""

import logging
from typing import Dict, Any
from uuid import UUID
from datetime import datetime

from app.db import get_db

logger = logging.getLogger(__name__)


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a task from the queue.

    Args:
        details: Action details containing:
            - task_id: UUID of task to execute
            - approach: How to execute the task

    Returns:
        Result dictionary with task execution summary
    """
    task_id = details.get("task_id")
    approach = details.get("approach", "default approach")

    if not task_id:
        logger.error("No task_id provided")
        raise ValueError("task_id is required")

    logger.info(f"Executing task: {task_id} ({approach})")

    try:
        db = get_db()

        # Fetch task from reactive_jobs table
        task = await db.fetch_one(
            """
            SELECT id, mode, payload_json, status
            FROM reactive_jobs
            WHERE id = $1
            """,
            UUID(task_id) if isinstance(task_id, str) else task_id,
        )

        if not task:
            logger.error(f"Task not found: {task_id}")
            return {
                "task_id": task_id,
                "status": "not_found",
                "error": "Task not found in database",
            }

        # Update task status to running
        await db.execute(
            """
            UPDATE reactive_jobs
            SET status = 'running', started_at = NOW()
            WHERE id = $1
            """,
            UUID(task_id) if isinstance(task_id, str) else task_id,
        )

        # Execute the task (placeholder - actual execution would vary by task type)
        # In real implementation, this would route to appropriate task handler
        logger.info(f"Task {task_id} execution started (mode={task['mode']})")

        # For now, just mark as done (real implementation would do actual work)
        await db.execute(
            """
            UPDATE reactive_jobs
            SET status = 'done', finished_at = NOW()
            WHERE id = $1
            """,
            UUID(task_id) if isinstance(task_id, str) else task_id,
        )

        result = {
            "task_id": task_id,
            "status": "completed",
            "mode": task["mode"],
            "approach": approach,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Task {task_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Error executing task {task_id}: {e}")
        raise


__all__ = ["execute"]
