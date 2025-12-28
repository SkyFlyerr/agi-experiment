"""Task executor using Claude Code subprocess.

This executor:
1. Launches Claude Code as a subprocess with the task
2. Monitors execution in real-time
3. Verifies result against goal criteria
4. Retries if goal not achieved
"""

import asyncio
import logging
import subprocess
import json
import os
import sys
import signal
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from pathlib import Path

from typing import List
import re
from app.db.tasks import (
    AgentTask,
    get_task_by_id,
    start_task,
    complete_task,
    fail_task,
    create_subtasks,
    TaskStatus,
)
from app.db.tokens import log_tokens
from app.db.models import TokenScope
from app.telegram import send_message
from app.config import settings

logger = logging.getLogger(__name__)

# Claude Code execution timeout (10 minutes per attempt)
EXECUTION_TIMEOUT = 600

# Working directory for Claude Code
WORKING_DIR = "/app"

# App code directory (for detecting self-modifications)
APP_CODE_DIR = "/app/app"

# Flag to track if restart is needed
_restart_scheduled = False


def schedule_restart():
    """Schedule a graceful restart after code changes."""
    global _restart_scheduled
    if _restart_scheduled:
        return
    _restart_scheduled = True
    logger.info("Self-modification detected, scheduling restart...")

    async def delayed_restart():
        """Wait a bit then restart."""
        await asyncio.sleep(5)  # Give time for notifications
        logger.info("Restarting application to apply code changes...")
        # Signal the main process to restart
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(delayed_restart())


def check_python_files_modified(output: str) -> bool:
    """Check if task output mentions modifying Python files in app directory."""
    indicators = [
        ".py",
        "config.py",
        "main.py",
        "/app/app/",
        "modified",
        "updated",
        "created",
        "wrote",
    ]
    output_lower = output.lower()
    return any(ind.lower() in output_lower for ind in indicators)


class TaskExecutor:
    """Executor that runs Claude Code for tasks."""

    def __init__(self):
        """Initialize task executor."""
        self.current_task: Optional[AgentTask] = None
        self.current_process: Optional[asyncio.subprocess.Process] = None

    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Execute a task using Claude Code subprocess.

        Args:
            task: AgentTask to execute

        Returns:
            Execution result dictionary
        """
        self.current_task = task
        logger.info(f"Starting execution of task {task.id}: {task.title}")

        try:
            # Mark task as running
            await start_task(task.id)

            # Notify Master if it's a Master task
            if task.source == "master":
                await self._notify_task_started(task)

            # Build the prompt for Claude Code
            prompt = self._build_execution_prompt(task)

            # Execute with Claude Code
            result = await self._run_claude_code(prompt, task)

            # Check if Claude decided to decompose the task into subtasks
            decomposition = self._check_decomposition(result.get("output", ""))
            if decomposition and task.depth == 0:  # Only root tasks can decompose
                logger.info(f"Task {task.id} decomposed into {len(decomposition)} subtasks")
                return await self._handle_decomposition(task, decomposition)

            # Verify result against goal criteria
            if task.goal_criteria:
                goal_achieved = await self._verify_goal(task, result)
            else:
                # No specific criteria - assume success if no error
                goal_achieved = result.get("success", False)

            if goal_achieved:
                # Task completed successfully
                await complete_task(task.id, result.get("output", "Completed"))

                if task.source == "master":
                    await self._notify_task_completed(task, result)

                logger.info(f"Task {task.id} completed successfully")

                # Check if Python files in app directory were modified
                output = result.get("output", "")
                if check_python_files_modified(output):
                    logger.info("Python files modified, scheduling restart...")
                    # Notify Master about pending restart
                    try:
                        master_chat_ids = settings.master_chat_ids_list
                        if master_chat_ids:
                            await send_message(
                                chat_id=str(master_chat_ids[0]),
                                text="🔄 <b>Self-modification detected</b>\n\n"
                                     f"Task '{task.title}' modified Python files.\n"
                                     "Scheduling graceful restart in 5 seconds to apply changes...",
                            )
                    except Exception as e:
                        logger.error(f"Error notifying about restart: {e}")
                    schedule_restart()

                return {
                    "success": True,
                    "task_id": str(task.id),
                    "output": result.get("output", ""),
                    "goal_achieved": True,
                }
            else:
                # Goal not achieved - will retry
                error_msg = result.get("error", "Goal criteria not met")
                await fail_task(task.id, error_msg)

                logger.warning(f"Task {task.id} goal not achieved: {error_msg}")
                return {
                    "success": False,
                    "task_id": str(task.id),
                    "error": error_msg,
                    "goal_achieved": False,
                    "will_retry": task.attempts + 1 < task.max_attempts,
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing task {task.id}: {e}", exc_info=True)

            try:
                await fail_task(task.id, error_msg)
            except Exception:
                pass

            return {
                "success": False,
                "task_id": str(task.id),
                "error": error_msg,
            }
        finally:
            self.current_task = None
            self.current_process = None

    def _build_execution_prompt(self, task: AgentTask) -> str:
        """Build prompt for Claude Code execution."""

        # Check if this is a root task (can be decomposed) or subtask
        is_root_task = task.depth == 0

        prompt = f"""You are an autonomous AGI agent executing a task.

TASK: {task.title}

DESCRIPTION:
{task.description}

"""
        if task.goal_criteria:
            prompt += f"""COMPLETION CRITERIA:
{task.goal_criteria}

"""

        prompt += f"""PRIORITY: {task.priority.value}
SOURCE: {task.source}
ATTEMPT: {task.attempts + 1} / {task.max_attempts}

=== CRITICAL RULES ===

1. CONTAINER ARCHITECTURE:
   - You run inside container server_agent_vnext_app
   - NEVER modify your own code in /app/app/ to add services
   - For web services, dashboards, tools - CREATE SEPARATE CONTAINERS ON HOST

   Command to create containers:
   ssh -i /app/secrets/host_key -p 58504 -o StrictHostKeyChecking=no root@host.docker.internal "docker run -d --name service_name --network server_agent_vnext_network image"

2. AUTONOMY: Don't ask permission for:
   - Creating Docker containers
   - Configuring nginx, SSL
   - Creating files on host
   Just do it.

3. EXECUTE the task for real, don't just describe what you would do.

"""

        # Add decomposition instructions for root tasks
        if is_root_task:
            prompt += """
TASK DECOMPOSITION:
If the task is complex and requires multiple independent steps, you can break it into subtasks.
To create subtasks, output a JSON block at the END of your response:

```json
{"decompose": true, "subtasks": [
  {"title": "Step 1: ...", "description": "...", "goal_criteria": "..."},
  {"title": "Step 2: ...", "description": "...", "goal_criteria": "..."}
]}
```

Decompose ONLY if:
- Task requires 3+ independent steps
- Each step can be verified separately

Do NOT decompose if:
- Task is simple (1-2 steps)
- You can complete it in a single execution
"""

        if task.last_result:
            prompt += f"""
PREVIOUS ATTEMPT RESULT:
{task.last_result[:1000]}

Learn from mistakes and try a different approach.
"""

        return prompt

    async def _run_claude_code(
        self,
        prompt: str,
        task: AgentTask,
    ) -> Dict[str, Any]:
        """
        Run Claude Code as subprocess.

        Args:
            prompt: Execution prompt
            task: Current task

        Returns:
            Execution result
        """
        try:
            # Build Claude Code command
            cmd = [
                "claude",
                "--print",
                "--model", settings.CLAUDE_MODEL,
                "--output-format", "json",
                "--tools", "default",
                "--dangerously-skip-permissions",
                prompt
            ]

            logger.info(f"Launching Claude Code for task {task.id}...")
            logger.debug(f"Command: {' '.join(cmd[:8])}...")

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=WORKING_DIR,
            )
            self.current_process = process

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=EXECUTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.error(f"Claude Code timeout after {EXECUTION_TIMEOUT}s")
                return {
                    "success": False,
                    "error": f"Execution timeout after {EXECUTION_TIMEOUT}s",
                    "output": "",
                }

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Log stderr if any
            if stderr_str:
                logger.warning(f"Claude Code stderr: {stderr_str[:500]}")

            # Parse JSON response
            try:
                response_data = json.loads(stdout_str)
                output = response_data.get("result", stdout_str)
                cost_usd = response_data.get("costUSD", 0)
                is_error = response_data.get("isError", False)

                # Log token usage (estimate from cost)
                if cost_usd:
                    estimated_tokens = int(cost_usd * 500000)
                    await log_tokens(
                        scope=TokenScope.PROACTIVE,
                        provider="claude_code_subprocess",
                        tokens_input=estimated_tokens // 2,
                        tokens_output=estimated_tokens // 2,
                        meta_json=json.dumps({
                            "task_id": str(task.id),
                            "task_title": task.title,
                            "cost_usd": cost_usd,
                        })
                    )

            except json.JSONDecodeError:
                output = stdout_str
                is_error = process.returncode != 0

            if process.returncode != 0 or is_error:
                return {
                    "success": False,
                    "error": stderr_str or "Claude Code returned error",
                    "output": output,
                }

            logger.info(f"Claude Code completed: {len(output)} chars output")

            return {
                "success": True,
                "output": output,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error running Claude Code: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "output": "",
            }

    async def _verify_goal(
        self,
        task: AgentTask,
        result: Dict[str, Any],
    ) -> bool:
        """
        Verify if task goal was achieved.

        Uses Claude to analyze result against goal criteria.
        """
        if not task.goal_criteria:
            return result.get("success", False)

        try:
            # Build verification prompt - be very strict about format
            verify_prompt = f"""Analyze if the following task goal was achieved.

TASK: {task.title}

GOAL CRITERIA:
{task.goal_criteria}

EXECUTION OUTPUT:
{result.get('output', 'No output')[:3000]}

CRITICAL: Your response MUST start with exactly "YES" or "NO" on the first line.
Then provide a brief explanation on the next line.

Example correct responses:
YES
The file was created successfully with all required sections.

NO
The file was not created.

Now analyze and respond:
"""

            # Use Claude CLI for verification
            cmd = [
                "claude",
                "--print",
                "--model", "claude-3-5-haiku-20241022",  # Use Haiku for quick verification
                "--output-format", "text",
                verify_prompt
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=WORKING_DIR,
            )

            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )

            response = stdout.decode("utf-8", errors="replace").strip().upper()

            # More robust parsing: look for YES anywhere in response if goal seems achieved
            # Check first line first, then look for YES/NO patterns
            first_line = response.split('\n')[0].strip() if response else ""

            if first_line.startswith("YES"):
                goal_achieved = True
            elif first_line.startswith("NO"):
                goal_achieved = False
            elif "✅" in response or "GOAL ACHIEVED" in response or "YES" in response.split('\n')[0]:
                # Haiku sometimes uses checkmarks or verbose responses
                goal_achieved = True
            elif "❌" in response or "NOT ACHIEVED" in response or "FAILED" in response:
                goal_achieved = False
            else:
                # Default: check if YES appears more than NO
                yes_count = response.count("YES")
                no_count = response.count("NO")
                goal_achieved = yes_count > no_count

            logger.info(f"Goal verification: {goal_achieved} - {response[:100]}")

            return goal_achieved

        except Exception as e:
            logger.error(f"Error verifying goal: {e}")
            # On error, fall back to checking if execution was successful
            return result.get("success", False)

    async def _notify_task_started(self, task: AgentTask) -> None:
        """Notify Master that task execution started."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            message = f"🚀 <b>Starting Task</b>\n\n"
            message += f"<b>Task:</b> {task.title}\n"
            message += f"<b>Priority:</b> {task.priority.value}\n"
            message += f"<b>Attempt:</b> {task.attempts + 1}/{task.max_attempts}\n\n"
            message += f"<i>Executing...</i>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
            )

        except Exception as e:
            logger.error(f"Error notifying task start: {e}")

    async def _notify_task_completed(
        self,
        task: AgentTask,
        result: Dict[str, Any],
    ) -> None:
        """Notify Master that task was completed."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            output = result.get("output", "")
            # Truncate output for Telegram
            if len(output) > 1000:
                output = output[:1000] + "...[truncated]"

            message = f"✅ <b>Task Completed</b>\n\n"
            message += f"<b>Task:</b> {task.title}\n"
            message += f"<b>Attempts:</b> {task.attempts + 1}\n\n"
            message += f"<b>Result:</b>\n<pre>{output}</pre>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
            )

        except Exception as e:
            logger.error(f"Error notifying task completion: {e}")

    async def cancel_current_task(self) -> bool:
        """Cancel currently running task."""
        if self.current_process and self.current_task:
            try:
                self.current_process.terminate()
                await asyncio.wait_for(self.current_process.wait(), timeout=5)
                logger.info(f"Cancelled task {self.current_task.id}")
                return True
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")
                self.current_process.kill()
                return True
        return False

    def _check_decomposition(self, output: str) -> Optional[List[Dict[str, Any]]]:
        """
        Check if Claude's output contains task decomposition.

        Returns list of subtask dicts if decomposition found, None otherwise.
        """
        if not output:
            return None

        try:
            # Look for JSON block with decomposition
            # Pattern: ```json\n{"decompose": true, "subtasks": [...]}```
            json_pattern = r'```json\s*(\{[^`]*"decompose"\s*:\s*true[^`]*\})\s*```'
            match = re.search(json_pattern, output, re.DOTALL | re.IGNORECASE)

            if not match:
                # Also try without code block
                json_pattern2 = r'\{"decompose"\s*:\s*true\s*,\s*"subtasks"\s*:\s*\[.*?\]\}'
                match = re.search(json_pattern2, output, re.DOTALL)

            if not match:
                return None

            json_str = match.group(1) if match.lastindex else match.group(0)
            data = json.loads(json_str)

            if data.get("decompose") and data.get("subtasks"):
                subtasks = data["subtasks"]
                # Validate subtasks structure
                valid_subtasks = []
                for st in subtasks:
                    if isinstance(st, dict) and st.get("title"):
                        valid_subtasks.append({
                            "title": st["title"],
                            "description": st.get("description", st["title"]),
                            "goal_criteria": st.get("goal_criteria"),
                        })

                if len(valid_subtasks) >= 2:
                    logger.info(f"Found decomposition with {len(valid_subtasks)} subtasks")
                    return valid_subtasks

        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse decomposition JSON: {e}")
        except Exception as e:
            logger.error(f"Error checking decomposition: {e}")

        return None

    async def _handle_decomposition(
        self,
        task: AgentTask,
        subtasks_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Handle task decomposition by creating subtasks.

        Args:
            task: Parent task
            subtasks_data: List of subtask definitions

        Returns:
            Result dict with decomposition status
        """
        try:
            # Create subtasks in database
            subtasks = await create_subtasks(task.id, subtasks_data)

            # Update parent task to track decomposition (keep as pending, subtasks will run first)
            from app.db import get_db
            db = get_db()
            await db.execute(
                """
                UPDATE agent_tasks
                SET last_result = $2, status = 'pending'
                WHERE id = $1
                """,
                task.id,
                f"Decomposed into {len(subtasks)} subtasks: " +
                ", ".join([st.title for st in subtasks])
            )

            # Notify Master about decomposition
            if task.source == "master":
                try:
                    master_chat_ids = settings.master_chat_ids_list
                    if master_chat_ids:
                        subtask_list = "\n".join([
                            f"  {i+1}. {st.title}"
                            for i, st in enumerate(subtasks)
                        ])
                        await send_message(
                            chat_id=str(master_chat_ids[0]),
                            text=f"📋 <b>Task Decomposed</b>\n\n"
                                 f"<b>Task:</b> {task.title}\n\n"
                                 f"<b>Subtasks:</b>\n{subtask_list}\n\n"
                                 f"<i>Will execute each subtask in order.</i>",
                        )
                except Exception as e:
                    logger.error(f"Error notifying decomposition: {e}")

            logger.info(f"Task {task.id} decomposed into {len(subtasks)} subtasks")

            return {
                "success": True,
                "task_id": str(task.id),
                "decomposed": True,
                "subtask_count": len(subtasks),
                "subtask_ids": [str(st.id) for st in subtasks],
            }

        except Exception as e:
            logger.error(f"Error handling decomposition: {e}", exc_info=True)
            # Fall back to treating as regular task
            return {
                "success": False,
                "task_id": str(task.id),
                "error": f"Decomposition failed: {e}",
            }


# Global executor instance
_executor: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """Get or create global task executor."""
    global _executor

    if _executor is None:
        _executor = TaskExecutor()

    return _executor


__all__ = [
    "TaskExecutor",
    "get_task_executor",
    "EXECUTION_TIMEOUT",
]
