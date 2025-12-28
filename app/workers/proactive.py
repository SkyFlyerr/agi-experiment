"""Proactive scheduler with dynamic token budget management.

This is the autonomous decision loop that runs continuously on the server,
making decisions, executing actions, and managing resources intelligently.
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
import json

from app.config import settings
from app.ai import (
    get_claude_client,
    build_proactive_prompt,
    check_budget_available,
    get_remaining_budget,
    get_token_stats,
    RateLimitError,
)
from app.workers.decision_engine import (
    parse_decision,
    validate_decision,
    should_execute_autonomously,
    should_notify_master,
    execute_decision,
)
from app.workers.task_executor import get_task_executor
from app.memory import (
    summarize_cycle,
    update_working_memory,
    store_next_prompt_aroma,
    get_recent_actions,
)
from app.telegram import send_message

logger = logging.getLogger(__name__)


class ProactiveScheduler:
    """Autonomous proactive scheduler with token budget management."""

    def __init__(self):
        """Initialize proactive scheduler."""
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.cycle_count = 0
        
        # Rate limit tracking
        self.rate_limit_until: Optional[datetime] = None

        # Configuration
        self.min_interval = settings.PROACTIVE_MIN_INTERVAL_SECONDS
        self.max_interval = settings.PROACTIVE_MAX_INTERVAL_SECONDS

        logger.info(
            f"ProactiveScheduler initialized (interval: {self.min_interval}-{self.max_interval}s)"
        )

    async def start(self) -> None:
        """Start the proactive scheduler loop."""
        if self.running:
            logger.warning("ProactiveScheduler already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info("ProactiveScheduler started")

    async def stop(self) -> None:
        """Stop the proactive scheduler loop."""
        if not self.running:
            logger.warning("ProactiveScheduler not running")
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("ProactiveScheduler task cancelled")

        logger.info("ProactiveScheduler stopped")

    async def _run_loop(self) -> None:
        """Main proactive loop - runs continuously while scheduler is active."""
        logger.info("ProactiveScheduler loop started")

        # Send startup notification to Master
        try:
            master_chat_ids = settings.master_chat_ids_list
            if master_chat_ids:
                await send_message(
                    chat_id=str(master_chat_ids[0]),
                    text="🤖 <b>Agent Online</b>\n\nAutonomous decision loop initiated.\n\n<i>Atmano moksartha jagat hitaya ca</i>",
                )
        except Exception as e:
            logger.error(f"Error sending startup notification: {e}")

        while self.running:
            try:
                # Check if we're in rate limit cooldown
                if self.rate_limit_until:
                    now = datetime.now(timezone.utc)
                    if now < self.rate_limit_until:
                        sleep_seconds = (self.rate_limit_until - now).total_seconds()
                        logger.info(
                            f"Rate limit active. Sleeping until {self.rate_limit_until.isoformat()} "
                            f"({sleep_seconds:.0f}s remaining)"
                        )
                        await asyncio.sleep(sleep_seconds)
                    
                    # Rate limit period has passed
                    self.rate_limit_until = None
                    logger.info("Rate limit period ended, resuming proactive cycle")
                    
                    # Notify Master that we're resuming
                    await self._notify_rate_limit_resumed()

                # Run a single proactive cycle
                await self.run_cycle()

                # Calculate dynamic sleep interval based on budget usage
                sleep_interval = await self.calculate_dynamic_interval()

                logger.info(f"Cycle {self.cycle_count} complete. Sleeping {sleep_interval}s...")
                await asyncio.sleep(sleep_interval)

            except asyncio.CancelledError:
                logger.info("ProactiveScheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in proactive loop: {e}", exc_info=True)
                # Sleep before retrying to avoid tight error loop
                await asyncio.sleep(60)

        logger.info("ProactiveScheduler loop ended")

    async def run_cycle(self) -> None:
        """
        Run a single proactive decision cycle.

        Priority order:
        1. Check for pending tasks from Master (highest priority)
        2. Check for pending self-assigned tasks
        3. If no tasks, use AI to decide next action

        Steps:
        1. Check token budget
        2. Check task queue for pending work
        3. If task exists, execute it
        4. If no tasks, get decision from Claude
        5. Update memory
        """
        self.cycle_count += 1
        cycle_start = datetime.utcnow()

        logger.info(f"=== Proactive Cycle {self.cycle_count} ===")

        try:
            # Step 1: Check token budget
            remaining = await get_remaining_budget(scope="proactive")
            if remaining < 10000:  # Need at least 10k tokens for meaningful cycle
                logger.warning(
                    f"Insufficient budget remaining: {remaining:,} tokens. "
                    "Entering meditation mode until budget resets."
                )
                # Notify Master if this is the first time hitting budget
                await self._notify_budget_exhausted()
                return

            logger.info(f"Token budget available: {remaining:,} tokens remaining")

            # Step 2: Check task queue for pending work (PRIORITY!)
            pending_task = await self._check_task_queue()

            if pending_task:
                # Execute pending task with TaskExecutor
                logger.info(f"Found pending task: {pending_task.title} (priority={pending_task.priority.value})")

                executor = get_task_executor()
                result = await executor.execute_task(pending_task)

                # Update memory with task result
                summary = {
                    "action": "execute_task",
                    "task_id": str(pending_task.id),
                    "task_title": pending_task.title,
                    "success": result.get("success", False),
                    "goal_achieved": result.get("goal_achieved", False),
                }
                await update_working_memory(json.dumps(summary))

                # Check if task belongs to a goal and if goal is complete
                if pending_task.goal_id:
                    await self._check_goal_completion(pending_task.goal_id)

                cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
                logger.info(f"Cycle {self.cycle_count} (task execution) completed in {cycle_duration:.1f}s")
                return

            # Step 2.5: Check for goals needing attention (all tasks done but goal still active)
            goals_needing_attention = await self._check_goals_needing_attention()
            if goals_needing_attention:
                # Goals were handled - don't proceed to proactive decision
                cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
                logger.info(f"Cycle {self.cycle_count} (goal attention) completed in {cycle_duration:.1f}s")
                return

            # Step 3: No pending tasks - use AI to decide next action
            logger.info("No pending tasks, requesting decision from Claude...")

            recent_actions = await get_recent_actions(limit=10)
            token_stats = await get_token_stats()

            # Get task queue summary for context
            task_summary = await self._get_task_queue_summary()

            # Get current focus (from memory or default)
            current_focus = "Exploring capabilities and learning autonomously"

            prompt_data = await build_proactive_prompt(
                recent_actions=recent_actions,
                active_tasks=task_summary.get("pending_tasks", []),
                current_focus=current_focus,
                token_stats=token_stats,
            )

            # Step 3: Get decision from Claude
            logger.info("Requesting decision from Claude...")
            claude = get_claude_client()

            response = await claude.send_message(
                messages=prompt_data["messages"],
                system=prompt_data["system"],
                max_tokens=2048,
                temperature=0.7,
                scope="proactive",
                meta={"cycle": self.cycle_count},
            )

            response_text = response["text"]
            logger.debug(f"Claude response: {response_text[:200]}...")

            # Step 4: Parse and validate decision
            decision = parse_decision(response_text)

            if not decision:
                logger.error("Failed to parse decision from Claude response")
                return

            if not validate_decision(decision):
                logger.error("Decision validation failed")
                return

            logger.info(
                f"Decision: action={decision.action}, "
                f"certainty={decision.certainty:.2f}, "
                f"significance={decision.significance:.2f}"
            )

            # Step 5: Execute or request approval
            decision_dict = decision.model_dump()

            if should_execute_autonomously(decision):
                # Execute autonomously
                logger.info(f"Executing autonomously: {decision.action}")
                result = await execute_decision(decision)

                # Notify Master if significant
                if should_notify_master(decision) and result.get("success"):
                    await self._notify_master_of_result(decision_dict, result)

            else:
                # Request approval from Master
                logger.info(f"Requesting approval for: {decision.action}")
                result = await self._request_approval(decision_dict)

            # Step 6: Update memory
            summary = await summarize_cycle(decision_dict, result)
            await update_working_memory(summary)

            # Store aroma for next cycle
            await store_next_prompt_aroma({
                "last_action": decision.action,
                "current_focus": current_focus,
                "timestamp": datetime.utcnow().isoformat(),
            })

            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(f"Cycle {self.cycle_count} completed in {cycle_duration:.1f}s")

        except RateLimitError as e:
            logger.warning(f"Rate limit reached in cycle {self.cycle_count}: {e.message}")
            
            # Notify Master about rate limit
            await self._notify_rate_limit(e)
            
            # Set cooldown until reset time
            if e.reset_time:
                self.rate_limit_until = e.reset_time
                logger.info(f"Rate limit cooldown set until {e.reset_time.isoformat()}")
            else:
                # Fallback: wait 1 hour if couldn't parse reset time
                self.rate_limit_until = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.warning("Could not parse reset time, defaulting to 1 hour cooldown")

        except Exception as e:
            logger.error(f"Error in cycle {self.cycle_count}: {e}", exc_info=True)

    async def calculate_dynamic_interval(self) -> int:
        """
        Calculate dynamic sleep interval based on budget usage.

        Formula:
        - Usage < 50%: short intervals (60-300s)
        - Usage 50-80%: medium intervals (300-1800s)
        - Usage > 80%: long intervals (1800-3600s)

        Returns:
            Sleep interval in seconds
        """
        try:
            token_stats = await get_token_stats()
            usage_ratio = token_stats["today"]["proactive"]["usage_ratio"]

            if usage_ratio < 0.5:
                # Low usage - be more active
                interval = self.min_interval + int((300 - self.min_interval) * usage_ratio)
            elif usage_ratio < 0.8:
                # Medium usage - moderate activity
                interval = 300 + int((1800 - 300) * (usage_ratio - 0.5) / 0.3)
            else:
                # High usage - conserve budget
                interval = 1800 + int((self.max_interval - 1800) * (usage_ratio - 0.8) / 0.2)

            # Clamp to configured min/max
            interval = max(self.min_interval, min(self.max_interval, interval))

            logger.debug(
                f"Dynamic interval: {interval}s (usage ratio: {usage_ratio:.1%})"
            )
            return interval

        except Exception as e:
            logger.error(f"Error calculating dynamic interval: {e}")
            # Fallback to medium interval
            return (self.min_interval + self.max_interval) // 2

    async def _notify_master_of_result(
        self,
        decision: dict,
        result: dict,
    ) -> None:
        """Notify Master of significant action result."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            action = decision.get("action", "unknown")
            significance = decision.get("significance", 0.0)
            result_summary = result.get("result", {})

            message = f"📊 <b>Significant Action Completed</b>\n\n"
            message += f"<b>Action:</b> {action}\n"
            message += f"<b>Significance:</b> {significance:.1%}\n"
            message += f"<b>Result:</b> {json.dumps(result_summary, indent=2)}\n"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
                
            )

            logger.info("Notified Master of significant result")

        except Exception as e:
            logger.error(f"Error notifying Master: {e}")

    async def _request_approval(self, decision: dict) -> dict:
        """Request approval from Master for uncertain decision."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                logger.error("No master chat IDs configured")
                return {"success": False, "error": "No master configured"}

            action = decision.get("action", "unknown")
            reasoning = decision.get("reasoning", "")
            certainty = decision.get("certainty", 0.0)

            message = f"🤔 <b>Approval Needed</b>\n\n"
            message += f"<b>Action:</b> {action}\n"
            message += f"<b>Reasoning:</b> {reasoning}\n"
            message += f"<b>Certainty:</b> {certainty:.1%}\n\n"
            message += f"<i>Should I proceed?</i>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
                
            )

            logger.info("Approval request sent to Master")

            # For now, return pending status
            # In full implementation, would wait for callback response
            return {
                "success": True,
                "result": {"status": "approval_pending", "action": action},
            }

        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            return {"success": False, "error": str(e)}

    async def _notify_budget_exhausted(self) -> None:
        """Notify Master that daily budget is exhausted."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            token_stats = await get_token_stats()
            proactive = token_stats["today"]["proactive"]

            message = f"⚠️ <b>Budget Exhausted</b>\n\n"
            message += f"Daily proactive budget reached:\n"
            message += f"Used: {proactive['used']:,} / {proactive['limit']:,} tokens\n\n"
            message += f"<i>Entering meditation mode until midnight UTC...</i>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
                
            )

            logger.info("Notified Master of budget exhaustion")

        except Exception as e:
            logger.error(f"Error notifying budget exhaustion: {e}")

    async def _notify_rate_limit(self, error: RateLimitError) -> None:
        """Notify Master that API rate limit was reached."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            # Format reset time for display
            if error.reset_time:
                reset_str = error.reset_time.strftime("%H:%M UTC")
                time_remaining = error.reset_time - datetime.now(timezone.utc)
                hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                minutes = remainder // 60
                duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                reset_str = "unknown"
                duration_str = "~1 hour"

            message = f"⏸️ <b>Rate Limit Reached</b>\n\n"
            message += f"Proactive cycle paused.\n\n"
            message += f"<b>Limit reset:</b> {reset_str}\n"
            message += f"<b>Wait time:</b> {duration_str}\n\n"
            message += f"<i>Will resume automatically.</i>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
                
            )

            logger.info("Notified Master of rate limit")

        except Exception as e:
            logger.error(f"Error notifying rate limit: {e}")

    async def _notify_rate_limit_resumed(self) -> None:
        """Notify Master that proactive cycle is resuming after rate limit."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            message = f"▶️ <b>Resuming Proactive Cycle</b>\n\n"
            message += f"Rate limit period ended.\n"
            message += f"Continuing autonomous operation."

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,

            )

            logger.info("Notified Master of rate limit resume")

        except Exception as e:
            logger.error(f"Error notifying rate limit resume: {e}")

    async def _check_task_queue(self):
        """
        Check task queue for pending tasks.

        Returns:
            AgentTask if pending task exists, None otherwise
        """
        try:
            from app.db.tasks import get_next_pending_task
            return await get_next_pending_task()
        except Exception as e:
            logger.error(f"Error checking task queue: {e}")
            return None

    async def _check_goals_needing_attention(self) -> bool:
        """
        Check for goals where all tasks are done but goal is still active.

        These goals need Master notification for either:
        - Verification (if all tasks succeeded)
        - Decision on failures (if some tasks failed)

        Returns:
            True if any goals were handled, False otherwise
        """
        try:
            from app.db.goals import (
                get_goals_needing_attention,
                check_goal_completion,
                complete_goal,
            )

            goals = await get_goals_needing_attention()
            if not goals:
                return False

            logger.info(f"Found {len(goals)} goals needing attention")

            for goal in goals:
                status = await check_goal_completion(goal.id)

                if status.get("ready_for_verification"):
                    # All tasks completed successfully!
                    logger.info(f"Goal {goal.id} ready for verification: {goal.title}")
                    await complete_goal(goal.id)
                    await self._notify_goal_complete(goal)

                elif status.get("all_tasks_done") and status.get("has_failures"):
                    # Some tasks failed - notify Master
                    logger.warning(f"Goal {goal.id} has failures: {status['failed']} failed tasks")
                    await self._notify_goal_failures(goal, status)

            return True

        except Exception as e:
            logger.error(f"Error checking goals needing attention: {e}")
            return False

    async def _check_goal_completion(self, goal_id) -> None:
        """
        Check if a goal is complete and notify Master.

        If all tasks are done and goal criteria can be verified,
        marks goal as completed and asks Master to verify.
        """
        try:
            from app.db.goals import (
                get_goal_by_id,
                check_goal_completion,
                complete_goal,
                add_tasks_to_goal,
            )

            goal = await get_goal_by_id(goal_id)
            if not goal:
                return

            status = await check_goal_completion(goal_id)

            if status.get("ready_for_verification"):
                # All tasks completed successfully!
                logger.info(f"Goal {goal_id} ready for verification: {goal.title}")

                # Mark goal as completed
                await complete_goal(goal_id)

                # Notify Master to verify
                await self._notify_goal_complete(goal)

            elif status.get("all_tasks_done") and status.get("has_failures"):
                # Some tasks failed - notify Master
                logger.warning(f"Goal {goal_id} has failures: {status['failed']} failed tasks")
                await self._notify_goal_failures(goal, status)

            else:
                # Goal still in progress
                logger.info(f"Goal {goal_id} progress: {status.get('progress', 'unknown')}")

        except Exception as e:
            logger.error(f"Error checking goal completion: {e}")

    async def _notify_goal_complete(self, goal) -> None:
        """Notify Master that goal is complete and needs verification."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            message = f"🎯 <b>Goal Achieved!</b>\n\n"
            message += f"<b>Goal:</b> {goal.title}\n\n"
            message += f"<b>Success criteria:</b>\n{goal.success_criteria}\n\n"
            message += f"<b>Tasks:</b> {goal.completed_tasks}/{goal.total_tasks} completed\n\n"
            message += f"<i>Please verify the result.</i>\n"
            message += f"Reply /verify_goal {goal.id} to confirm."

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
            )

            logger.info(f"Notified Master about goal completion: {goal.id}")

        except Exception as e:
            logger.error(f"Error notifying goal completion: {e}")

    async def _notify_goal_failures(self, goal, status: dict) -> None:
        """Notify Master that goal has failures."""
        try:
            master_chat_ids = settings.master_chat_ids_list
            if not master_chat_ids:
                return

            message = f"⚠️ <b>Task Failures Detected</b>\n\n"
            message += f"<b>Goal:</b> {goal.title}\n\n"
            message += f"<b>Progress:</b> {status.get('progress', 'unknown')}\n"
            message += f"<b>Failed tasks:</b> {status.get('failed', 0)}\n\n"
            message += f"<i>Retry failed tasks?</i>"

            await send_message(
                chat_id=str(master_chat_ids[0]),
                text=message,
            )

            logger.info(f"Notified Master about goal failures: {goal.id}")

        except Exception as e:
            logger.error(f"Error notifying goal failures: {e}")

    async def _get_task_queue_summary(self) -> dict:
        """Get summary of task queue for context."""
        try:
            from app.db.tasks import get_task_queue_summary, get_pending_tasks

            summary = await get_task_queue_summary()
            pending = await get_pending_tasks(limit=5)

            return {
                **summary,
                "pending_tasks": [
                    {"title": t.title, "priority": t.priority.value, "source": t.source}
                    for t in pending
                ]
            }
        except Exception as e:
            logger.error(f"Error getting task queue summary: {e}")
            return {"pending_tasks": [], "master_tasks": 0, "self_tasks": 0}


# Global scheduler instance
_scheduler: Optional[ProactiveScheduler] = None


def get_scheduler() -> ProactiveScheduler:
    """Get or create global scheduler instance."""
    global _scheduler

    if _scheduler is None:
        _scheduler = ProactiveScheduler()

    return _scheduler


__all__ = ["ProactiveScheduler", "get_scheduler"]
