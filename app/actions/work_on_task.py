"""Task execution action handler.

This module handles executing specific tasks from the task queue
using ClaudeToolsClient for real tool execution.
"""

import logging
import json
from typing import Dict, Any
from uuid import UUID
from datetime import datetime

from app.db import get_db
from app.ai.claude_tools import get_claude_tools_client

logger = logging.getLogger(__name__)

# System prompt for task execution with tools
TASK_EXECUTION_PROMPT = """You are an autonomous AGI agent executing a task on a server.

You have access to real tools to complete this task:
- read_file: Read file contents
- write_file: Create or overwrite files
- list_directory: List directory contents
- run_bash: Execute shell commands
- search_code: Search for patterns in code
- send_telegram_message: Send messages to Master
- http_request: Make HTTP API calls
- remember: Store information in long-term memory
- recall: Retrieve information from memory

IMPORTANT GUIDELINES:
1. Actually USE the tools to complete the task - don't just describe what you would do
2. Start by understanding the current state (read files, list directories)
3. Make incremental changes and verify each step
4. If you create files, verify they were created correctly
5. Report progress and results to Master via Telegram if significant
6. Store important learnings in memory for future reference

Be methodical, careful, and thorough. You are operating on a real system."""


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a task from the queue using real tools.

    Uses ClaudeToolsClient to process and execute tasks with actual tool calls.

    Args:
        details: Action details containing:
            - task_id: UUID of task to execute
            - approach: How to execute the task

    Returns:
        Result dictionary with task execution outcomes
    """
    task_id = details.get("task_id")
    approach = details.get("approach", "default approach")

    if not task_id:
        logger.error("No task_id provided")
        raise ValueError("task_id is required")

    logger.info(f"Executing task with real tools: {task_id} ({approach})")

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

        # Extract task details from payload
        payload = task["payload_json"] or {}
        task_description = payload.get("description", approach)
        task_context = payload.get("context", "")

        # Get Claude Tools client (with real tool execution)
        client = get_claude_tools_client()

        # Build task execution prompt
        user_prompt = f"""Execute the following task:

TASK ID: {task_id}
MODE: {task["mode"]}
DESCRIPTION: {task_description}
APPROACH: {approach}

{f"CONTEXT: {task_context}" if task_context else ""}

Use the available tools to actually complete this task. Don't just describe what you would do - actually do it.

When done, summarize what you accomplished and any important findings."""

        # Call Claude with tools enabled
        response = await client.send_message_with_tools(
            messages=[{"role": "user", "content": user_prompt}],
            system=TASK_EXECUTION_PROMPT,
            max_tokens=4096,
            scope="proactive",
            meta={
                "action": "work_on_task",
                "task_id": task_id,
                "mode": task["mode"],
            },
            max_tool_iterations=10,  # Allow multiple tool uses
            enable_tools=True,
            auto_approve_safe_tools=True,  # Auto-approve read operations
        )

        response_text = response.get("text", "").strip()
        usage = response.get("usage", {})
        tool_executions = response.get("tool_executions", [])
        pending_approvals = response.get("pending_approvals", [])

        # Log tool usage
        tools_used = [te["tool_name"] for te in tool_executions]
        logger.info(f"Task {task_id} used tools: {tools_used}")

        # Update task status in database
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
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            "tools_executed": len(tool_executions),
            "tools_used": tools_used,
            "pending_approvals": len(pending_approvals),
            "outcome": response_text[:2000] if response_text else "Task completed",
        }

        logger.info(f"Task {task_id} completed with {len(tool_executions)} tool executions")

        return result

    except Exception as e:
        logger.error(f"Error executing task {task_id}: {e}", exc_info=True)

        # Update task status to error
        try:
            db = get_db()
            await db.execute(
                """
                UPDATE reactive_jobs
                SET status = 'error', finished_at = NOW()
                WHERE id = $1
                """,
                UUID(task_id) if isinstance(task_id, str) else task_id,
            )
        except Exception:
            pass

        return {
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


__all__ = ["execute"]
