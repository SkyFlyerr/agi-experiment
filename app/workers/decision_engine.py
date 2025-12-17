"""Decision engine for parsing and routing proactive decisions.

This module interprets Claude's decision responses and routes them to
appropriate action handlers based on certainty and significance thresholds.
"""

import json
import logging
from typing import Dict, Any, Optional
from pydantic import ValidationError

from app.ai.proactive_prompts import ProactiveDecision

logger = logging.getLogger(__name__)

# Thresholds
CERTAINTY_THRESHOLD = 0.8  # Execute autonomously if >= 0.8
SIGNIFICANCE_THRESHOLD = 0.8  # Notify Master if >= 0.8


def parse_decision(claude_response: str) -> Optional[ProactiveDecision]:
    """
    Parse Claude's response into a structured decision.

    Args:
        claude_response: Raw text response from Claude

    Returns:
        ProactiveDecision object, or None if parsing failed
    """
    try:
        # Try to extract JSON from response (Claude might wrap it in text)
        # Look for JSON block
        start = claude_response.find("{")
        end = claude_response.rfind("}") + 1

        if start == -1 or end == 0:
            logger.error("No JSON object found in Claude response")
            return None

        json_str = claude_response[start:end]
        decision_dict = json.loads(json_str)

        # Validate with Pydantic
        decision = ProactiveDecision(**decision_dict)

        logger.info(
            f"Parsed decision: action={decision.action}, "
            f"certainty={decision.certainty:.2f}, "
            f"significance={decision.significance:.2f}"
        )
        return decision

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return None
    except ValidationError as e:
        logger.error(f"Decision validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing decision: {e}")
        return None


def validate_decision(decision: ProactiveDecision) -> bool:
    """
    Validate decision structure and constraints.

    Args:
        decision: ProactiveDecision to validate

    Returns:
        True if valid, False otherwise
    """
    valid_actions = [
        "develop_skill",
        "work_on_task",
        "communicate",
        "meditate",
        "ask_master",
        "proactive_outreach",
    ]

    if decision.action not in valid_actions:
        logger.error(f"Invalid action: {decision.action}")
        return False

    if not 0.0 <= decision.certainty <= 1.0:
        logger.error(f"Invalid certainty: {decision.certainty}")
        return False

    if not 0.0 <= decision.significance <= 1.0:
        logger.error(f"Invalid significance: {decision.significance}")
        return False

    if decision.type not in ["internal", "external"]:
        logger.error(f"Invalid type: {decision.type}")
        return False

    # Validate action-specific details
    required_fields = {
        "develop_skill": ["skill_name", "approach"],
        "work_on_task": ["task_id", "approach"],
        "communicate": ["recipient", "message"],
        "meditate": ["duration"],
        "ask_master": ["question", "context"],
        "proactive_outreach": ["chat_id", "message", "purpose"],
    }

    action = decision.action
    if action in required_fields:
        for field in required_fields[action]:
            if field not in decision.details:
                logger.error(
                    f"Missing required field '{field}' for action '{action}'"
                )
                return False

    logger.debug(f"Decision validated: {decision.action}")
    return True


def should_execute_autonomously(decision: ProactiveDecision) -> bool:
    """
    Check if decision should be executed autonomously.

    Args:
        decision: ProactiveDecision to check

    Returns:
        True if certainty >= threshold, False otherwise
    """
    autonomous = decision.certainty >= CERTAINTY_THRESHOLD

    if autonomous:
        logger.info(
            f"Decision will execute autonomously (certainty={decision.certainty:.2f})"
        )
    else:
        logger.info(
            f"Decision requires approval (certainty={decision.certainty:.2f})"
        )

    return autonomous


def should_notify_master(decision: ProactiveDecision) -> bool:
    """
    Check if Master should be notified about this decision/result.

    Args:
        decision: ProactiveDecision to check

    Returns:
        True if significance >= threshold, False otherwise
    """
    notify = decision.significance >= SIGNIFICANCE_THRESHOLD

    if notify:
        logger.info(
            f"Decision will notify Master (significance={decision.significance:.2f})"
        )
    else:
        logger.debug(
            f"Decision will execute quietly (significance={decision.significance:.2f})"
        )

    return notify


async def execute_decision(decision: ProactiveDecision) -> Dict[str, Any]:
    """
    Route decision to appropriate action handler.

    Args:
        decision: Validated ProactiveDecision

    Returns:
        Action result dictionary:
        {
            "success": bool,
            "result": Any,
            "error": Optional[str]
        }
    """
    # Import action handlers dynamically to avoid circular imports
    from app.actions import (
        develop_skill,
        work_on_task,
        communicate,
        meditate,
        ask_master,
        proactive_outreach,
    )

    action_handlers = {
        "develop_skill": develop_skill.execute,
        "work_on_task": work_on_task.execute,
        "communicate": communicate.send_to_master,
        "meditate": meditate.execute,
        "ask_master": ask_master.execute,
        "proactive_outreach": communicate.proactive_outreach,
    }

    handler = action_handlers.get(decision.action)
    if handler is None:
        logger.error(f"No handler found for action: {decision.action}")
        return {"success": False, "error": f"Unknown action: {decision.action}"}

    try:
        logger.info(f"Executing action: {decision.action}")
        result = await handler(decision.details)

        logger.info(f"Action completed: {decision.action}")
        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Error executing action {decision.action}: {e}")
        return {"success": False, "error": str(e)}


__all__ = [
    "parse_decision",
    "validate_decision",
    "should_execute_autonomously",
    "should_notify_master",
    "execute_decision",
    "CERTAINTY_THRESHOLD",
    "SIGNIFICANCE_THRESHOLD",
]
