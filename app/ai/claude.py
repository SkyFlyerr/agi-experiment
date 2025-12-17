"""Claude execution for reactive jobs."""

import logging
from typing import List
from uuid import UUID

from anthropic import AsyncAnthropic
from anthropic.types import Message

from app.config import settings
from app.db.models import ChatMessage, TokenScope
from app.db.tokens import log_tokens
from .prompts import EXECUTION_SYSTEM_PROMPT, build_execution_prompt

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of Claude task execution."""

    def __init__(
        self,
        response_text: str,
        tool_calls: list = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ):
        self.response_text = response_text
        self.tool_calls = tool_calls or []
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output

    @property
    def has_tool_calls(self) -> bool:
        """Check if execution included tool calls."""
        return len(self.tool_calls) > 0


async def execute_task(
    messages: List[ChatMessage],
    intent: str,
    summary: str,
    plan: str,
    job_id: UUID | None = None,
    max_tokens: int = 4000,
) -> ExecutionResult:
    """
    Execute task using Claude.

    Args:
        messages: Full conversation history (up to 30 messages)
        intent: Classified intent (question/command/other)
        summary: One-sentence summary of request
        plan: One-sentence plan for response
        job_id: Optional job ID for token logging metadata
        max_tokens: Maximum tokens for response (default: 4000)

    Returns:
        ExecutionResult with response text and tool calls

    Raises:
        Exception: If API call fails
    """
    try:
        # Build execution prompt
        user_prompt = build_execution_prompt(messages, intent, summary, plan)

        logger.info(f"Executing task with Claude (intent={intent})")

        # Initialize Anthropic client
        client = AsyncAnthropic(api_key=settings.CLAUDE_CODE_OAUTH_TOKEN)

        # Call Claude API
        response: Message = await client.messages.create(
            model="claude-sonnet-4-20250514",  # Latest Sonnet model
            max_tokens=max_tokens,
            system=EXECUTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            timeout=120.0,  # 2 minute timeout
        )

        # Extract response text
        response_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                response_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        logger.debug(f"Claude response: {len(response_text)} chars, {len(tool_calls)} tool calls")

        # Log token usage
        await log_tokens(
            scope=TokenScope.REACTIVE,
            provider="claude",
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
            meta_json={
                "job_id": str(job_id) if job_id else None,
                "model": "claude-sonnet-4-20250514",
                "intent": intent,
                "tool_calls": len(tool_calls),
            },
        )

        # Create result
        result = ExecutionResult(
            response_text=response_text.strip(),
            tool_calls=tool_calls,
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
        )

        logger.info(
            f"Execution complete: {result.tokens_input + result.tokens_output} tokens, "
            f"{len(tool_calls)} tool calls"
        )

        return result

    except Exception as e:
        logger.error(f"Error executing task with Claude: {e}", exc_info=True)
        raise


__all__ = [
    "execute_task",
    "ExecutionResult",
]
