"""src/action_executor.py

Centralized action execution with safety guardrails.

Goals:
- Single place to control what the agent is allowed to do.
- Explicit allowlist of actions.
- Clear separation between decision-making and side effects.

This is intentionally minimal: it executes only a small set of safe actions and
routes anything risky through human approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


SAFE_INTERNAL_ACTIONS = {
    "develop_skill",
    "work_on_task",
    "meditate",
}

SAFE_EXTERNAL_ACTIONS = {
    "communicate",
    "ask_master",
}

RISKY_EXTERNAL_ACTIONS = {
    "proactive_outreach",
}


@dataclass
class ActionResult:
    success: bool
    message: str
    timestamp: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.data is not None:
            payload["data"] = self.data
        return payload


class ActionExecutor:
    """Executes actions produced by the agent's decision step."""

    def __init__(self, state_manager, telegram_bot=None, telegram_client=None):
        self.state_manager = state_manager
        self.telegram_bot = telegram_bot
        self.telegram_client = telegram_client

    async def execute(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        action_type = decision.get("action")
        details = decision.get("details", {})

        now = datetime.now().isoformat()

        if action_type in SAFE_INTERNAL_ACTIONS:
            if action_type == "develop_skill":
                skill_name = details.get("skill_name", "unknown_skill")
                self.state_manager.add_skill(
                    skill_name,
                    {
                        "description": decision.get("reasoning", ""),
                        "status": "in_progress",
                    },
                )
                return ActionResult(
                    success=True,
                    message=f"Skill development initiated: {skill_name}",
                    timestamp=now,
                ).to_dict()

            if action_type == "work_on_task":
                task_id = details.get("task_id")
                return ActionResult(
                    success=True,
                    message=f"Task {task_id} in progress",
                    timestamp=now,
                ).to_dict()

            if action_type == "meditate":
                duration = details.get("duration_minutes")
                return ActionResult(
                    success=True,
                    message=f"Meditation period: {duration} minutes" if duration else "Meditation period",
                    timestamp=now,
                ).to_dict()

        if action_type in SAFE_EXTERNAL_ACTIONS:
            if not self.telegram_bot:
                return ActionResult(
                    success=False,
                    message="Telegram bot not available",
                    timestamp=now,
                ).to_dict()

            if action_type == "communicate":
                message = details.get("message", "")
                await self.telegram_bot.notify_master(message)
                return ActionResult(
                    success=True,
                    message="Message sent to Master",
                    timestamp=now,
                ).to_dict()

            if action_type == "ask_master":
                question = details.get("question", "")
                response = await self.telegram_bot.ask_master(question)
                self.state_manager.record_guidance(question, response)
                return ActionResult(
                    success=True,
                    message="Question sent to Master",
                    timestamp=now,
                    data={"response": response},
                ).to_dict()

        if action_type in RISKY_EXTERNAL_ACTIONS:
            # Guardrail: proactive outreach requires explicit approval and a working user client.
            username = details.get("telegram_username", "")
            message = details.get("outreach_message", "")
            reason = details.get("outreach_reason", "No reason provided")

            if not self.telegram_client:
                return ActionResult(
                    success=False,
                    message="Telegram client not available",
                    timestamp=now,
                ).to_dict()

            approved = await self.telegram_client.request_permission_to_message(username, reason)
            if not approved:
                return ActionResult(
                    success=True,
                    message=f"Permission requested from Master to message @{username}",
                    timestamp=now,
                ).to_dict()

            success = await self.telegram_client.send_message(username, message, require_approval=True)
            return ActionResult(
                success=success,
                message=f"Message sent to @{username}" if success else f"Failed to send to @{username}",
                timestamp=now,
            ).to_dict()

        return ActionResult(
            success=False,
            message=f"Disallowed/unknown action type: {action_type}",
            timestamp=now,
        ).to_dict()