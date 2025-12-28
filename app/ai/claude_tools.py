"""
Claude CLI client with tool support for OAuth token authentication.

This client uses Claude CLI which supports OAuth tokens and has built-in
tool execution capabilities (Bash, Edit, Read, Write, etc.)
"""

import logging
import subprocess
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from pydantic import BaseModel

from app.config import settings
from app.db.tokens import log_tokens
from app.db.models import TokenScope

logger = logging.getLogger(__name__)


class ToolExecutionResult(BaseModel):
    """Result of tool execution"""
    tool_use_id: str
    tool_name: str
    result: Dict[str, Any]
    required_approval: bool = False
    approved: bool = False


class ClaudeToolsClient:
    """Claude CLI client with built-in tool execution support."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude Tools client using CLI.

        Args:
            model: Model to use (default: Claude Sonnet 4)
        """
        self.model = model
        logger.info(f"Claude Tools client initialized with model: {model}")

    async def send_message_with_tools(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        scope: str = "reactive",
        meta: Optional[Dict[str, Any]] = None,
        max_tool_iterations: int = 10,
        enable_tools: bool = True,
        auto_approve_safe_tools: bool = True,
    ) -> Dict[str, Any]:
        """
        Send message to Claude CLI with tool support.

        Claude CLI has built-in tools: Bash, Read, Write, Edit, Glob, Grep, etc.
        With --dangerously-skip-permissions, it will execute tools autonomously.

        Args:
            messages: List of message dicts with "role" and "content"
            system: Optional system prompt
            max_tokens: Maximum tokens to generate (not directly used by CLI)
            temperature: Sampling temperature (not directly used by CLI)
            scope: Token scope for logging ("proactive" or "reactive")
            meta: Optional metadata to log with tokens
            max_tool_iterations: Not used - CLI handles iterations
            enable_tools: Whether to enable tool use (default: True)
            auto_approve_safe_tools: Whether to skip permissions (default: True)

        Returns:
            Dictionary with:
            {
                "text": str,  # Final text response
                "usage": {"input_tokens": int, "output_tokens": int},
                "model": str,
                "stop_reason": str,
                "tool_executions": List[Dict],  # Tools that were executed
                "pending_approvals": List[Dict],  # Always empty with CLI
            }
        """
        try:
            # Build prompt from messages
            prompt_parts = []

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    prompt_parts.append(content)
                elif role == "assistant":
                    prompt_parts.append(f"[Previous response: {content}]")

            prompt = "\n\n".join(prompt_parts)

            # Build CLI command
            cmd = [
                "claude",
                "--print",  # Non-interactive mode
                "--model", self.model,
                "--output-format", "json",  # Get structured response
            ]

            # Add system prompt if provided
            if system:
                cmd.extend(["--system-prompt", system])

            # Configure tools
            if enable_tools:
                # Use default tools (Bash, Read, Write, Edit, etc.)
                cmd.extend(["--tools", "default"])

                if auto_approve_safe_tools:
                    # Skip all permission prompts for autonomous execution
                    cmd.append("--dangerously-skip-permissions")
            else:
                # Disable all tools
                cmd.extend(["--tools", ""])

            # Add the prompt
            cmd.append(prompt)

            logger.info(f"Executing Claude CLI with tools...")
            logger.debug(f"Command: {' '.join(cmd[:10])}...")

            # Execute CLI
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for tool execution
                check=False,
                cwd="/app"  # Working directory in container
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Claude CLI error: {error_msg}")
                raise Exception(f"Claude CLI failed: {error_msg}")

            # Parse JSON response
            response_text = result.stdout.strip()

            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                # If not valid JSON, treat as plain text
                response_data = {
                    "result": response_text,
                    "costUSD": 0,
                    "isError": False,
                }

            # Extract response details
            if isinstance(response_data, dict):
                final_text = response_data.get("result", response_text)
                cost_usd = response_data.get("costUSD", 0)
                is_error = response_data.get("isError", False)

                # Estimate tokens from cost (rough: $3/1M input, $15/1M output for Sonnet)
                # Assuming 50/50 split for simplicity
                estimated_tokens = int(cost_usd * 500000) if cost_usd else len(prompt) // 4
                input_tokens = estimated_tokens // 2
                output_tokens = estimated_tokens // 2
            else:
                final_text = str(response_data)
                input_tokens = len(prompt) // 4
                output_tokens = len(final_text) // 4

            # Extract tool usage from response (look for tool markers)
            tool_executions = self._extract_tool_usage(final_text)

            # Log token usage
            log_meta = {
                "model": self.model,
                "messages_count": len(messages),
                "has_system": system is not None,
                "tools_enabled": enable_tools,
                "tools_used": len(tool_executions),
                **(meta or {})
            }

            await log_tokens(
                scope=TokenScope(scope),
                provider="claude_cli_tools",
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                meta_json=json.dumps(log_meta)
            )

            logger.info(
                f"Claude CLI with tools complete: {len(final_text)} chars, "
                f"{len(tool_executions)} tools used"
            )

            return {
                "text": final_text,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
                "model": self.model,
                "stop_reason": "end_turn",
                "tool_executions": [
                    {
                        "tool_name": te.tool_name,
                        "result": te.result,
                        "required_approval": te.required_approval,
                        "approved": te.approved,
                    }
                    for te in tool_executions
                ],
                "pending_approvals": [],  # CLI handles all approvals
            }

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timeout after 300s")
            raise Exception("Claude CLI request timed out")
        except Exception as e:
            logger.error(f"Error calling Claude CLI with tools: {e}", exc_info=True)
            raise

    def _extract_tool_usage(self, response_text: str) -> List[ToolExecutionResult]:
        """
        Extract tool usage from Claude CLI response.

        Claude CLI output includes markers for tool usage.
        """
        tools = []

        # Look for common tool usage patterns in the response
        tool_patterns = [
            (r"```bash\n(.*?)```", "bash"),
            (r"Read\((.*?)\)", "read_file"),
            (r"Write\((.*?)\)", "write_file"),
            (r"Edit\((.*?)\)", "edit"),
            (r"Bash\((.*?)\)", "bash"),
            (r"created file:?\s*([^\n]+)", "write_file"),
            (r"read file:?\s*([^\n]+)", "read_file"),
            (r"executed:?\s*([^\n]+)", "bash"),
        ]

        for pattern, tool_name in tool_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                tools.append(ToolExecutionResult(
                    tool_use_id=f"{tool_name}_{len(tools)}",
                    tool_name=tool_name,
                    result={"output": match[:500] if isinstance(match, str) else str(match)[:500]},
                    required_approval=False,
                    approved=True
                ))

        return tools


# Global client instance
_tools_client: Optional[ClaudeToolsClient] = None


def get_claude_tools_client(model: Optional[str] = None) -> ClaudeToolsClient:
    """Get or create global Claude Tools client"""
    global _tools_client

    if _tools_client is None or (model and _tools_client.model != model):
        _tools_client = ClaudeToolsClient(model=model or settings.CLAUDE_MODEL)

    return _tools_client


__all__ = [
    "ClaudeToolsClient",
    "ToolExecutionResult",
    "get_claude_tools_client",
]
