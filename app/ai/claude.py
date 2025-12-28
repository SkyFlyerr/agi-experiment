"""Claude execution for reactive jobs using ClaudeCLIClient."""

import logging
from typing import List, Dict, Any
from uuid import UUID

from app.config import settings
from app.db.models import ChatMessage, TokenScope
from app.db.tokens import log_tokens
from app.ai.client import get_claude_client
from .prompts import EXECUTION_SYSTEM_PROMPT, build_execution_prompt

logger = logging.getLogger(__name__)

# Maximum tool execution iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


class ExecutionResult:
    """Result of Claude task execution."""

    def __init__(
        self,
        response_text: str,
        tool_calls: list = None,
        tool_results: list = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ):
        self.response_text = response_text
        self.tool_calls = tool_calls or []
        self.tool_results = tool_results or []
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
    Execute task using Claude via ClaudeCLIClient.

    Uses the unified client that automatically handles OAuth tokens
    by routing to Claude CLI.

    Args:
        messages: Full conversation history (up to 30 messages)
        intent: Classified intent (question/command/other)
        summary: One-sentence summary of request
        plan: One-sentence plan for response
        job_id: Optional job ID for token logging metadata
        max_tokens: Maximum tokens for response (default: 4000)

    Returns:
        ExecutionResult with response text

    Raises:
        Exception: If API call fails
    """
    try:
        # Build execution prompt
        user_prompt = build_execution_prompt(messages, intent, summary, plan)

        logger.info(f"Executing task with Claude (intent={intent})")

        # Get Claude client (auto-selects CLI for OAuth tokens)
        client = get_claude_client()

        # Call Claude
        response = await client.send_message(
            messages=[{"role": "user", "content": user_prompt}],
            system=EXECUTION_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            scope="reactive",
            meta={
                "job_id": str(job_id) if job_id else None,
                "intent": intent,
            },
        )

        response_text = response.get("text", "").strip()
        usage = response.get("usage", {})

        # Create result
        result = ExecutionResult(
            response_text=response_text,
            tool_calls=[],
            tool_results=[],
            tokens_input=usage.get("input_tokens", 0),
            tokens_output=usage.get("output_tokens", 0),
        )

        logger.info(
            f"Execution complete: {result.tokens_input + result.tokens_output} tokens"
        )

        return result

    except Exception as e:
        logger.error(f"Error executing task with Claude: {e}", exc_info=True)
        raise


__all__ = [
    "execute_task",
    "ExecutionResult",
]
