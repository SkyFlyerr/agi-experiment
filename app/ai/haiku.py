"""Haiku classification for reactive jobs."""

import json
import logging
from typing import Dict, Any, List
from uuid import UUID

from anthropic import AsyncAnthropic
from anthropic.types import Message

from app.config import settings
from app.db.models import ChatMessage, TokenScope
from app.db.tokens import log_tokens
from .prompts import CLASSIFICATION_SYSTEM_PROMPT, build_classification_prompt

logger = logging.getLogger(__name__)


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
    ):
        self.intent = intent
        self.summary = summary
        self.plan = plan
        self.needs_confirmation = needs_confirmation
        self.confidence = confidence
        self.raw_response = raw_response

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "summary": self.summary,
            "plan": self.plan,
            "needs_confirmation": self.needs_confirmation,
            "confidence": self.confidence,
        }


async def classify_intent(
    messages: List[ChatMessage],
    trigger_message: ChatMessage,
    job_id: UUID | None = None,
) -> ClassificationResult:
    """
    Classify user intent using Haiku.

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

        # Initialize Anthropic client
        client = AsyncAnthropic(api_key=settings.haiku_api_key_resolved)

        # Call Haiku API
        response: Message = await client.messages.create(
            model=settings.HAIKU_MODEL,
            max_tokens=500,  # Classification should be concise
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            timeout=30.0,  # 30 second timeout
        )

        # Extract response text
        response_text = response.content[0].text if response.content else ""

        logger.debug(f"Haiku response: {response_text}")

        # Log token usage
        await log_tokens(
            scope=TokenScope.REACTIVE,
            provider="haiku",
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
            meta_json={
                "job_id": str(job_id) if job_id else None,
                "model": settings.HAIKU_MODEL,
                "message_id": str(trigger_message.id),
            },
        )

        # Parse JSON response
        try:
            result_json = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Haiku JSON response: {response_text}")
            raise ValueError(f"Invalid JSON response from Haiku: {e}")

        # Validate required fields
        required_fields = ["intent", "summary", "plan", "needs_confirmation", "confidence"]
        for field in required_fields:
            if field not in result_json:
                raise ValueError(f"Missing required field in Haiku response: {field}")

        # Validate intent value
        valid_intents = ["question", "command", "other"]
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

        # Create result
        classification = ClassificationResult(
            intent=result_json["intent"],
            summary=result_json["summary"],
            plan=result_json["plan"],
            needs_confirmation=bool(result_json["needs_confirmation"]),
            confidence=confidence,
            raw_response=response_text,
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
]
