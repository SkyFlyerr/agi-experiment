"""Goal management for persistent objectives.

Goals are high-level objectives from Master that persist until fully achieved.
Tasks are steps toward completing goals.

Flow:
1. Master sends goal → Create goal + initial tasks
2. Agent executes tasks one by one
3. When all tasks done → Check goal success_criteria
4. If criteria met → Notify Master for verification
5. Master confirms → Goal completed
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from . import get_db
from .tasks import create_task, TaskPriority, TaskStatus, AgentTask

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    """Goal status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentGoal(BaseModel):
    """Agent goal model."""
    id: UUID
    title: str
    description: str
    success_criteria: str
    source: str  # "master" or "self"
    priority: str
    status: GoalStatus
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    verified_by_master: bool = False
    master_feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    thread_id: Optional[UUID] = None


# SQL queries
CREATE_GOAL = """
INSERT INTO agent_goals (id, title, description, success_criteria, source, priority, status, thread_id, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, 'active', $7, NOW(), NOW())
RETURNING *
"""

GET_ACTIVE_GOALS = """
SELECT * FROM agent_goals
WHERE status = 'active'
ORDER BY
    CASE source WHEN 'master' THEN 0 ELSE 1 END,
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    created_at ASC
"""

# Goals where all tasks are done but goal is still active (needs attention)
GET_GOALS_NEEDING_ATTENTION = """
SELECT * FROM agent_goals
WHERE status = 'active'
  AND total_tasks > 0
  AND (completed_tasks + failed_tasks) >= total_tasks
ORDER BY
    CASE source WHEN 'master' THEN 0 ELSE 1 END,
    created_at ASC
"""

GET_GOAL_BY_ID = """
SELECT * FROM agent_goals WHERE id = $1
"""

UPDATE_GOAL_STATUS = """
UPDATE agent_goals
SET status = $2, updated_at = NOW(), completed_at = $3
WHERE id = $1
RETURNING *
"""

GET_GOAL_TASKS = """
SELECT * FROM agent_tasks
WHERE goal_id = $1
ORDER BY order_index, created_at
"""

GET_PENDING_GOAL_TASKS = """
SELECT * FROM agent_tasks
WHERE goal_id = $1 AND status = 'pending'
ORDER BY order_index, created_at
LIMIT 1
"""

MARK_GOAL_VERIFIED = """
UPDATE agent_goals
SET verified_by_master = TRUE, master_feedback = $2, updated_at = NOW()
WHERE id = $1
RETURNING *
"""


async def create_goal(
    title: str,
    description: str,
    success_criteria: str,
    source: str = "master",
    priority: str = "high",
    thread_id: Optional[UUID] = None,
    initial_tasks: Optional[List[Dict[str, Any]]] = None,
) -> AgentGoal:
    """
    Create a new goal with optional initial tasks.

    Args:
        title: Goal title
        description: Detailed description
        success_criteria: How to verify goal is achieved
        source: "master" or "self"
        priority: Goal priority
        thread_id: Optional conversation thread
        initial_tasks: Optional list of initial task definitions

    Returns:
        Created AgentGoal
    """
    db = get_db()
    goal_id = uuid4()

    try:
        row = await db.fetch_one(
            CREATE_GOAL,
            goal_id,
            title,
            description,
            success_criteria,
            source,
            priority,
            thread_id,
        )

        goal = AgentGoal(**row)
        logger.info(f"Created goal {goal_id}: {title} (source={source})")

        # Create initial tasks if provided
        if initial_tasks:
            for idx, task_data in enumerate(initial_tasks):
                await create_goal_task(
                    goal_id=goal_id,
                    title=task_data["title"],
                    description=task_data.get("description", task_data["title"]),
                    goal_criteria=task_data.get("goal_criteria"),
                    order_index=idx,
                )

        return goal

    except Exception as e:
        logger.error(f"Error creating goal: {e}")
        raise


async def create_goal_task(
    goal_id: UUID,
    title: str,
    description: str,
    goal_criteria: Optional[str] = None,
    order_index: int = 0,
) -> AgentTask:
    """Create a task linked to a goal."""
    goal = await get_goal_by_id(goal_id)
    if not goal:
        raise ValueError(f"Goal not found: {goal_id}")

    # Create task with goal_id
    db = get_db()
    task_id = uuid4()

    try:
        row = await db.fetch_one(
            """
            INSERT INTO agent_tasks (
                id, title, description, priority, status, source,
                goal_criteria, max_attempts, goal_id, order_index, depth, created_at
            )
            VALUES ($1, $2, $3, $4, 'pending', $5, $6, 3, $7, $8, 0, NOW())
            RETURNING *
            """,
            task_id,
            title,
            description,
            goal.priority,
            goal.source,
            goal_criteria,
            goal_id,
            order_index,
        )

        logger.info(f"Created task {task_id} for goal {goal_id}: {title}")
        return AgentTask(**row)

    except Exception as e:
        logger.error(f"Error creating goal task: {e}")
        raise


async def get_active_goals() -> List[AgentGoal]:
    """Get all active goals, Master goals first."""
    db = get_db()
    try:
        rows = await db.fetch_all(GET_ACTIVE_GOALS)
        return [AgentGoal(**row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching active goals: {e}")
        return []


async def get_goals_needing_attention() -> List[AgentGoal]:
    """
    Get goals where all tasks are done but goal is still active.

    These goals need either:
    - Verification from Master (if all tasks succeeded)
    - Decision on how to handle failures (if some tasks failed)
    """
    db = get_db()
    try:
        rows = await db.fetch_all(GET_GOALS_NEEDING_ATTENTION)
        return [AgentGoal(**row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching goals needing attention: {e}")
        return []


async def get_goal_by_id(goal_id: UUID) -> Optional[AgentGoal]:
    """Get goal by ID."""
    db = get_db()
    try:
        row = await db.fetch_one(GET_GOAL_BY_ID, goal_id)
        return AgentGoal(**row) if row else None
    except Exception as e:
        logger.error(f"Error fetching goal {goal_id}: {e}")
        return None


async def get_next_task_for_goal(goal_id: UUID) -> Optional[AgentTask]:
    """Get next pending task for a goal."""
    db = get_db()
    try:
        row = await db.fetch_one(GET_PENDING_GOAL_TASKS, goal_id)
        return AgentTask(**row) if row else None
    except Exception as e:
        logger.error(f"Error fetching next task for goal {goal_id}: {e}")
        return None


async def check_goal_completion(goal_id: UUID) -> Dict[str, Any]:
    """
    Check if a goal is ready for completion.

    Returns:
        Dict with:
        - all_tasks_done: bool
        - has_failures: bool
        - ready_for_verification: bool
        - progress: str (e.g., "5/7 tasks completed")
    """
    db = get_db()
    try:
        goal = await get_goal_by_id(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        return {
            "all_tasks_done": goal.completed_tasks + goal.failed_tasks >= goal.total_tasks and goal.total_tasks > 0,
            "has_failures": goal.failed_tasks > 0,
            "ready_for_verification": goal.completed_tasks == goal.total_tasks and goal.total_tasks > 0,
            "progress": f"{goal.completed_tasks}/{goal.total_tasks} tasks completed",
            "failed": goal.failed_tasks,
        }

    except Exception as e:
        logger.error(f"Error checking goal completion: {e}")
        return {"error": str(e)}


async def complete_goal(goal_id: UUID) -> AgentGoal:
    """Mark goal as completed (pending Master verification)."""
    db = get_db()
    try:
        row = await db.fetch_one(
            UPDATE_GOAL_STATUS,
            goal_id,
            GoalStatus.COMPLETED.value,
            datetime.utcnow(),
        )
        if not row:
            raise ValueError(f"Goal not found: {goal_id}")

        logger.info(f"Goal {goal_id} marked as completed")
        return AgentGoal(**row)

    except Exception as e:
        logger.error(f"Error completing goal {goal_id}: {e}")
        raise


async def verify_goal(goal_id: UUID, feedback: Optional[str] = None) -> AgentGoal:
    """Master verifies goal completion."""
    db = get_db()
    try:
        row = await db.fetch_one(MARK_GOAL_VERIFIED, goal_id, feedback)
        if not row:
            raise ValueError(f"Goal not found: {goal_id}")

        logger.info(f"Goal {goal_id} verified by Master")
        return AgentGoal(**row)

    except Exception as e:
        logger.error(f"Error verifying goal {goal_id}: {e}")
        raise


async def add_tasks_to_goal(goal_id: UUID, tasks: List[Dict[str, Any]]) -> List[AgentTask]:
    """Add more tasks to an existing goal."""
    goal = await get_goal_by_id(goal_id)
    if not goal:
        raise ValueError(f"Goal not found: {goal_id}")

    # Get current max order_index
    db = get_db()
    row = await db.fetch_one(
        "SELECT COALESCE(MAX(order_index), -1) + 1 as next_idx FROM agent_tasks WHERE goal_id = $1",
        goal_id
    )
    next_idx = row["next_idx"] if row else 0

    created = []
    for idx, task_data in enumerate(tasks):
        task = await create_goal_task(
            goal_id=goal_id,
            title=task_data["title"],
            description=task_data.get("description", task_data["title"]),
            goal_criteria=task_data.get("goal_criteria"),
            order_index=next_idx + idx,
        )
        created.append(task)

    logger.info(f"Added {len(created)} tasks to goal {goal_id}")
    return created


__all__ = [
    "GoalStatus",
    "AgentGoal",
    "create_goal",
    "create_goal_task",
    "get_active_goals",
    "get_goals_needing_attention",
    "get_goal_by_id",
    "get_next_task_for_goal",
    "check_goal_completion",
    "complete_goal",
    "verify_goal",
    "add_tasks_to_goal",
]
