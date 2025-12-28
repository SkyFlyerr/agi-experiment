"""Haiku classification for reactive jobs using Claude CLI."""

import json
import logging
from typing import Dict, Any, List
from uuid import UUID

from app.config import settings
from app.db.models import ChatMessage, TokenScope
from app.db.tokens import log_tokens
from .prompts import CLASSIFICATION_SYSTEM_PROMPT, build_classification_prompt
from .claude_cli import ClaudeCLIClient

logger = logging.getLogger(__name__)


class SubtaskInfo:
    """Subtask information."""

    def __init__(self, title: str, description: str, goal_criteria: str):
        self.title = title
        self.description = description
        self.goal_criteria = goal_criteria

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "goal_criteria": self.goal_criteria,
        }


class TaskInfo:
    """Task information extracted from classification."""

    def __init__(
        self,
        title: str,
        description: str,
        goal_criteria: str,
        priority: str = "high",
        subtasks: List["SubtaskInfo"] = None,
    ):
        self.title = title
        self.description = description
        self.goal_criteria = goal_criteria
        self.priority = priority
        self.subtasks = subtasks or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "title": self.title,
            "description": self.description,
            "goal_criteria": self.goal_criteria,
            "priority": self.priority,
        }
        if self.subtasks:
            result["subtasks"] = [s.to_dict() for s in self.subtasks]
        return result


class ClassificationResult:
    """Result of intent classification."""

    def __init__(
        self,
        intent: str,
        summary: str,
        plan: str,
        needs_confirmation: bool,
        confidence: float,
        raw_response: str = "",
        task: TaskInfo = None,
    ):
        self.intent = intent
        self.summary = summary
        self.plan = plan
        self.needs_confirmation = needs_confirmation
        self.confidence = confidence
        self.raw_response = raw_response
        self.task = task  # Only present when intent="task"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "intent": self.intent,
            "summary": self.summary,
            "plan": self.plan,
            "needs_confirmation": self.needs_confirmation,
            "confidence": self.confidence,
        }
        if self.task:
            result["task"] = self.task.to_dict()
        return result


async def classify_intent(
    messages: List[ChatMessage],
    trigger_message: ChatMessage,
    job_id: UUID | None = None,
) -> ClassificationResult:
    """
    Classify user intent using Claude CLI (Haiku model).

    Args:
        messages: List of recent messages (up to 30)
        trigger_message: The message that triggered classification
        job_id: Optional job ID for token logging metadata

    Returns:
        ClassificationResult with intent, summary, plan, needs_confirmation, confidence

    Raises:
        Exception: If API call fails or response is invalid
    """
    try:
        # Build classification prompt
        user_prompt = build_classification_prompt(messages, trigger_message)

        logger.info(f"Classifying intent for message {trigger_message.id}")

        # Use Claude CLI with haiku model
        client = ClaudeCLIClient(model="claude-sonnet-4-20250514")  # Use same model as proactive

        # Call Claude CLI
        response = await client.send_message(
            messages=[{"role": "user", "content": user_prompt}],
            system=CLASSIFICATION_SYSTEM_PROMPT,
            max_tokens=500,
            scope="reactive",
            meta={
                "job_id": str(job_id) if job_id else None,
                "message_id": str(trigger_message.id),
                "task": "classification",
            },
        )

        # Extract response text
        response_text = response.get("text", "")

        logger.debug(f"Classification response: {response_text}")

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_match = None
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                result_json = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON response: {response_text}")
            raise ValueError(f"Invalid JSON response from classifier: {e}")

        # Validate required fields
        required_fields = ["intent", "summary", "plan", "needs_confirmation", "confidence"]
        for field in required_fields:
            if field not in result_json:
                raise ValueError(f"Missing required field in classification response: {field}")

        # Validate intent value
        valid_intents = ["question", "command", "task", "other"]
        if result_json["intent"] not in valid_intents:
            logger.warning(
                f"Invalid intent '{result_json['intent']}', defaulting to 'other'"
            )
            result_json["intent"] = "other"

        # Validate confidence range
        confidence = float(result_json["confidence"])
        if not 0.0 <= confidence <= 1.0:
            logger.warning(f"Confidence {confidence} out of range, clamping to [0,1]")
            confidence = max(0.0, min(1.0, confidence))

        # Extract task info if intent is "task"
        task_info = None
        if result_json["intent"] == "task" and "task" in result_json:
            task_data = result_json["task"]
            if isinstance(task_data, dict):
                # Parse subtasks if present
                subtasks = []
                if "subtasks" in task_data and isinstance(task_data["subtasks"], list):
                    for st in task_data["subtasks"]:
                        if isinstance(st, dict):
                            subtasks.append(SubtaskInfo(
                                title=st.get("title", "Subtask"),
                                description=st.get("description", ""),
                                goal_criteria=st.get("goal_criteria", "Completed"),
                            ))
                    logger.info(f"Parsed {len(subtasks)} subtasks for task")

                task_info = TaskInfo(
                    title=task_data.get("title", result_json["summary"]),
                    description=task_data.get("description", result_json["plan"]),
                    goal_criteria=task_data.get("goal_criteria", "Task completed successfully"),
                    subtasks=subtasks,
                    priority=task_data.get("priority", "high"),
                )
                logger.info(f"Extracted task: {task_info.title} (priority={task_info.priority})")

        # Create result
        classification = ClassificationResult(
            intent=result_json["intent"],
            summary=result_json["summary"],
            plan=result_json["plan"],
            needs_confirmation=bool(result_json["needs_confirmation"]),
            confidence=confidence,
            raw_response=response_text,
            task=task_info,
        )

        logger.info(
            f"Classification complete: intent={classification.intent}, "
            f"confidence={classification.confidence:.2f}, "
            f"needs_confirmation={classification.needs_confirmation}"
        )

        return classification

    except Exception as e:
        logger.error(f"Error classifying intent: {e}", exc_info=True)
        raise


__all__ = [
    "classify_intent",
    "ClassificationResult",
    "TaskInfo",
]
