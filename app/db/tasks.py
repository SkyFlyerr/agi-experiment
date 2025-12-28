"""Task queue operations with priority and hierarchy support.

Tasks from Master have highest priority.
Tasks can have subtasks (parent_id) for complex multi-step work.

Priority enforcement:
1. Master tasks ALWAYS come before self-tasks
2. Within same source, priority determines order
3. Subtasks must complete before parent can complete
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from . import get_db

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"  # From Master, urgent
    HIGH = "high"          # From Master, normal
    MEDIUM = "medium"      # Self-determined important
    LOW = "low"            # Self-determined nice-to-have


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTask(BaseModel):
    """Agent task model with hierarchy support."""
    id: UUID
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    source: str  # "master" or "self"
    goal_criteria: Optional[str] = None  # How to verify task completion
    attempts: int = 0
    max_attempts: int = 3
    last_result: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    thread_id: Optional[UUID] = None  # Link to conversation thread
    # Hierarchy fields
    parent_id: Optional[UUID] = None  # Parent task for subtasks
    order_index: int = 0  # Order within parent
    depth: int = 0  # Nesting level (0 = root)
    # Goal link
    goal_id: Optional[UUID] = None  # Parent goal this task belongs to


# SQL queries
CREATE_TASK = """
INSERT INTO agent_tasks (
    id, title, description, priority, status, source,
    goal_criteria, max_attempts, thread_id, parent_id, order_index, depth, created_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
RETURNING *
"""

# CRITICAL: Master tasks (source='master') ALWAYS come before self-tasks
# Within same source, priority and creation time determine order
# Root tasks (depth=0) before subtasks - subtasks handled separately
GET_PENDING_TASKS = """
SELECT * FROM agent_tasks
WHERE status = 'pending'
  AND depth = 0  -- Only root tasks, subtasks fetched via parent
ORDER BY
    CASE source
        WHEN 'master' THEN 0
        ELSE 1
    END,
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    created_at ASC
LIMIT $1
"""

# Get subtasks of a parent task in order
GET_SUBTASKS = """
SELECT * FROM agent_tasks
WHERE parent_id = $1
ORDER BY order_index ASC, created_at ASC
"""

# Get next pending subtask for a parent
GET_NEXT_PENDING_SUBTASK = """
SELECT * FROM agent_tasks
WHERE parent_id = $1 AND status = 'pending'
ORDER BY order_index ASC, created_at ASC
LIMIT 1
"""

# Count pending subtasks for a parent
COUNT_PENDING_SUBTASKS = """
SELECT COUNT(*) as count FROM agent_tasks
WHERE parent_id = $1 AND status = 'pending'
"""

GET_TASK_BY_ID = """
SELECT * FROM agent_tasks WHERE id = $1
"""

UPDATE_TASK_STATUS = """
UPDATE agent_tasks
SET status = $2,
    started_at = COALESCE($3, started_at),
    completed_at = $4,
    attempts = COALESCE($5, attempts),
    last_result = COALESCE($6, last_result)
WHERE id = $1
RETURNING *
"""

GET_RUNNING_TASK = """
SELECT * FROM agent_tasks WHERE status = 'running' LIMIT 1
"""

COUNT_PENDING_BY_SOURCE = """
SELECT source, COUNT(*) as count FROM agent_tasks
WHERE status = 'pending'
GROUP BY source
"""


async def create_task(
    title: str,
    description: str,
    priority: TaskPriority = TaskPriority.MEDIUM,
    source: str = "self",
    goal_criteria: Optional[str] = None,
    max_attempts: int = 3,
    thread_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
    order_index: int = 0,
) -> AgentTask:
    """
    Create a new task in the queue.

    Args:
        title: Short task title
        description: Detailed task description
        priority: Task priority level
        source: "master" or "self"
        goal_criteria: How to verify completion
        max_attempts: Maximum execution attempts
        thread_id: Optional link to conversation
        parent_id: Optional parent task ID for subtasks
        order_index: Order within parent (0-based)

    Returns:
        Created AgentTask
    """
    db = get_db()
    task_id = uuid4()

    # Calculate depth based on parent
    depth = 0
    if parent_id:
        parent = await get_task_by_id(parent_id)
        if parent:
            depth = parent.depth + 1
            # Inherit source from parent (Master's subtasks are also Master's)
            source = parent.source
        else:
            logger.warning(f"Parent task {parent_id} not found, creating as root task")
            parent_id = None

    try:
        row = await db.fetch_one(
            CREATE_TASK,
            task_id,
            title,
            description,
            priority.value,
            TaskStatus.PENDING.value,
            source,
            goal_criteria,
            max_attempts,
            thread_id,
            parent_id,
            order_index,
            depth,
        )

        parent_info = f", parent={parent_id}" if parent_id else ""
        logger.info(f"Created task {task_id}: {title} (priority={priority.value}, source={source}{parent_info})")
        return AgentTask(**row)

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise


async def create_subtasks(
    parent_id: UUID,
    subtasks: List[Dict[str, Any]],
) -> List[AgentTask]:
    """
    Create multiple subtasks for a parent task.

    Args:
        parent_id: Parent task ID
        subtasks: List of dicts with title, description, goal_criteria (optional)

    Returns:
        List of created AgentTask objects
    """
    parent = await get_task_by_id(parent_id)
    if not parent:
        raise ValueError(f"Parent task not found: {parent_id}")

    created = []
    for idx, subtask_data in enumerate(subtasks):
        task = await create_task(
            title=subtask_data["title"],
            description=subtask_data.get("description", subtask_data["title"]),
            priority=parent.priority,  # Inherit priority from parent
            source=parent.source,  # Inherit source from parent
            goal_criteria=subtask_data.get("goal_criteria"),
            max_attempts=subtask_data.get("max_attempts", 3),
            thread_id=parent.thread_id,
            parent_id=parent_id,
            order_index=idx,
        )
        created.append(task)

    logger.info(f"Created {len(created)} subtasks for parent {parent_id}")
    return created


async def get_subtasks(parent_id: UUID) -> List[AgentTask]:
    """Get all subtasks of a parent task."""
    db = get_db()
    try:
        rows = await db.fetch_all(GET_SUBTASKS, parent_id)
        return [AgentTask(**row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching subtasks for {parent_id}: {e}")
        raise


async def get_next_pending_subtask(parent_id: UUID) -> Optional[AgentTask]:
    """Get next pending subtask for a parent."""
    db = get_db()
    try:
        row = await db.fetch_one(GET_NEXT_PENDING_SUBTASK, parent_id)
        return AgentTask(**row) if row else None
    except Exception as e:
        logger.error(f"Error fetching next subtask for {parent_id}: {e}")
        raise


async def count_pending_subtasks(parent_id: UUID) -> int:
    """Count pending subtasks for a parent."""
    db = get_db()
    try:
        row = await db.fetch_one(COUNT_PENDING_SUBTASKS, parent_id)
        return row["count"] if row else 0
    except Exception as e:
        logger.error(f"Error counting subtasks for {parent_id}: {e}")
        return 0


async def get_next_pending_task() -> Optional[AgentTask]:
    """
    Get the highest priority pending task.

    Priority order:
    1. Master tasks before self-tasks (ALWAYS)
    2. Critical > High > Medium > Low
    3. Older tasks first
    4. For tasks with subtasks, get next pending subtask

    Returns:
        AgentTask or None if no pending tasks
    """
    db = get_db()

    try:
        # Get next root-level pending task
        rows = await db.fetch_all(GET_PENDING_TASKS, 1)

        if not rows:
            logger.debug("No pending tasks in queue")
            return None

        task = AgentTask(**rows[0])

        # Check if this task has pending subtasks
        pending_subtask = await get_next_pending_subtask(task.id)
        if pending_subtask:
            # Return subtask instead of parent
            logger.debug(f"Next pending subtask: {pending_subtask.id} ({pending_subtask.title}) of parent {task.id}")
            return pending_subtask

        logger.debug(f"Next pending task: {task.id} ({task.title})")
        return task

    except Exception as e:
        logger.error(f"Error fetching pending task: {e}")
        raise


async def get_pending_tasks(limit: int = 10) -> List[AgentTask]:
    """
    Get pending tasks ordered by priority.

    Args:
        limit: Maximum number of tasks to return

    Returns:
        List of AgentTask objects
    """
    db = get_db()

    try:
        rows = await db.fetch_all(GET_PENDING_TASKS, limit)
        tasks = [AgentTask(**row) for row in rows]
        logger.debug(f"Found {len(tasks)} pending tasks")
        return tasks

    except Exception as e:
        logger.error(f"Error fetching pending tasks: {e}")
        raise


async def get_task_by_id(task_id: UUID) -> Optional[AgentTask]:
    """Get task by ID."""
    db = get_db()

    try:
        row = await db.fetch_one(GET_TASK_BY_ID, task_id)
        return AgentTask(**row) if row else None

    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {e}")
        raise


async def start_task(task_id: UUID) -> AgentTask:
    """Mark task as running."""
    db = get_db()

    try:
        row = await db.fetch_one(
            UPDATE_TASK_STATUS,
            task_id,
            TaskStatus.RUNNING.value,
            datetime.utcnow(),
            None,
            None,
            None,
        )

        if not row:
            raise ValueError(f"Task not found: {task_id}")

        logger.info(f"Started task {task_id}")
        return AgentTask(**row)

    except Exception as e:
        logger.error(f"Error starting task {task_id}: {e}")
        raise


async def complete_task(task_id: UUID, result: str) -> AgentTask:
    """
    Mark task as completed.

    If this is a subtask and all sibling subtasks are completed,
    also completes the parent task.
    """
    db = get_db()

    try:
        # Get current task
        task = await get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        row = await db.fetch_one(
            UPDATE_TASK_STATUS,
            task_id,
            TaskStatus.COMPLETED.value,
            None,
            datetime.utcnow(),
            task.attempts + 1,
            result[:5000] if result else None,  # Limit result size
        )

        completed_task = AgentTask(**row)
        logger.info(f"Completed task {task_id}: {task.title}")

        # Check if parent should be auto-completed
        if task.parent_id:
            pending_siblings = await count_pending_subtasks(task.parent_id)
            if pending_siblings == 0:
                # All subtasks done - complete parent
                logger.info(f"All subtasks completed, completing parent {task.parent_id}")
                await complete_task(
                    task.parent_id,
                    f"All {await _count_total_subtasks(task.parent_id)} subtasks completed. Last: {result[:500] if result else 'OK'}"
                )

        return completed_task

    except Exception as e:
        logger.error(f"Error completing task {task_id}: {e}")
        raise


async def _count_total_subtasks(parent_id: UUID) -> int:
    """Count total subtasks (all statuses) for a parent."""
    db = get_db()
    try:
        row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM agent_tasks WHERE parent_id = $1",
            parent_id
        )
        return row["count"] if row else 0
    except Exception:
        return 0


async def fail_task(task_id: UUID, error: str) -> AgentTask:
    """
    Mark task attempt as failed.

    If max attempts reached, marks task as failed.
    Otherwise, returns to pending for retry.
    """
    db = get_db()

    try:
        task = await get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        new_attempts = task.attempts + 1

        if new_attempts >= task.max_attempts:
            # Max attempts reached - mark as failed
            new_status = TaskStatus.FAILED.value
            logger.warning(f"Task {task_id} failed after {new_attempts} attempts")
        else:
            # Return to pending for retry
            new_status = TaskStatus.PENDING.value
            logger.info(f"Task {task_id} attempt {new_attempts} failed, will retry")

        row = await db.fetch_one(
            UPDATE_TASK_STATUS,
            task_id,
            new_status,
            None,
            datetime.utcnow() if new_status == TaskStatus.FAILED.value else None,
            new_attempts,
            error[:5000] if error else None,
        )

        return AgentTask(**row)

    except Exception as e:
        logger.error(f"Error failing task {task_id}: {e}")
        raise


async def get_running_task() -> Optional[AgentTask]:
    """Get currently running task if any."""
    db = get_db()

    try:
        row = await db.fetch_one(GET_RUNNING_TASK)
        return AgentTask(**row) if row else None

    except Exception as e:
        logger.error(f"Error fetching running task: {e}")
        raise


async def get_task_queue_summary() -> Dict[str, Any]:
    """Get summary of task queue status."""
    db = get_db()

    try:
        rows = await db.fetch_all(COUNT_PENDING_BY_SOURCE)

        summary = {
            "master_tasks": 0,
            "self_tasks": 0,
            "total_pending": 0,
        }

        for row in rows:
            if row["source"] == "master":
                summary["master_tasks"] = row["count"]
            else:
                summary["self_tasks"] = row["count"]
            summary["total_pending"] += row["count"]

        # Check for running task
        running = await get_running_task()
        summary["has_running_task"] = running is not None
        summary["running_task_id"] = str(running.id) if running else None

        return summary

    except Exception as e:
        logger.error(f"Error getting task queue summary: {e}")
        return {"master_tasks": 0, "self_tasks": 0, "total_pending": 0}


__all__ = [
    # Enums and models
    "TaskPriority",
    "TaskStatus",
    "AgentTask",
    # Task creation
    "create_task",
    "create_subtasks",
    # Task retrieval
    "get_next_pending_task",
    "get_pending_tasks",
    "get_task_by_id",
    "get_subtasks",
    "get_next_pending_subtask",
    "count_pending_subtasks",
    # Task status updates
    "start_task",
    "complete_task",
    "fail_task",
    "get_running_task",
    # Queue summary
    "get_task_queue_summary",
]
