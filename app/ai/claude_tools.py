"""
Claude API client with native tool support.

This client uses the Anthropic Python SDK directly with tool calling support,
allowing Claude to autonomously use tools during execution.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import anthropic

from app.config import settings
from app.db import get_db
from app.db.tokens import log_tokens
from app.db.models import TokenScope
from app.tools.registry import get_tool_registry, ToolSafety

logger = logging.getLogger(__name__)


class ToolExecutionResult(BaseModel):
    """Result of tool execution"""
    tool_use_id: str
    tool_name: str
    result: Dict[str, Any]
    required_approval: bool = False
    approved: bool = False


class ClaudeToolsClient:
    """Claude API client with native tool calling support"""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude Tools client.

        Args:
            model: Model to use (default: Claude Sonnet 4)
        """
        self.model = model
        self.client = anthropic.Anthropic(api_key=settings.CLAUDE_CODE_OAUTH_TOKEN)
        self.tool_registry = get_tool_registry()

        logger.info(f"Claude Tools client initialized with model: {model}")

    async def send_message_with_tools(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        scope: str = "reactive",
        meta: Optional[Dict[str, Any]] = None,
        max_tool_iterations: int = 5,
        enable_tools: bool = True,
        auto_approve_safe_tools: bool = True,
    ) -> Dict[str, Any]:
        """
        Send message to Claude with tool support.

        Args:
            messages: List of message dicts with "role" and "content"
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            scope: Token scope for logging ("proactive" or "reactive")
            meta: Optional metadata to log with tokens
            max_tool_iterations: Maximum number of tool use cycles (default: 5)
            enable_tools: Whether to enable tool use (default: True)
            auto_approve_safe_tools: Auto-approve tools marked as SAFE (default: True)

        Returns:
            Dictionary with:
            {
                "text": str,  # Final text response
                "usage": {"input_tokens": int, "output_tokens": int},
                "model": str,
                "stop_reason": str,
                "tool_executions": List[ToolExecutionResult],  # Tools that were executed
                "pending_approvals": List[Dict],  # Tools awaiting approval
            }
        """
        try:
            # Build Anthropic messages format
            api_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Anthropic API expects 'user' or 'assistant' roles
                if role in ["user", "assistant"]:
                    api_messages.append({
                        "role": role,
                        "content": content
                    })

            # Get available tools
            tools = self.tool_registry.get_tools_for_claude() if enable_tools else []

            # Track tool executions
            tool_executions: List[ToolExecutionResult] = []
            pending_approvals: List[Dict[str, Any]] = []

            # Total token usage
            total_input_tokens = 0
            total_output_tokens = 0

            # Tool use loop
            iteration = 0
            final_text = ""

            while iteration < max_tool_iterations:
                iteration += 1
                logger.debug(f"Tool iteration {iteration}/{max_tool_iterations}")

                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system if system else anthropic.NOT_GIVEN,
                    messages=api_messages,
                    tools=tools if tools else anthropic.NOT_GIVEN,
                )

                # Track tokens
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                # Check stop reason
                stop_reason = response.stop_reason

                # Process response content
                has_tool_use = False
                text_content = ""

                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                        final_text = block.text  # Update final text

                    elif block.type == "tool_use":
                        has_tool_use = True
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        logger.info(f"Claude wants to use tool: {tool_name}")
                        logger.debug(f"Tool input: {json.dumps(tool_input, indent=2)}")

                        # Check if tool requires approval
                        tool_def = self.tool_registry.get_tool_definition(tool_name)

                        if not tool_def:
                            # Unknown tool
                            tool_result = {
                                "status": "error",
                                "error": f"Unknown tool: {tool_name}"
                            }
                            approved = False
                            required_approval = False

                        elif tool_def.safety_level == ToolSafety.DANGEROUS:
                            # Blocked tool
                            tool_result = {
                                "status": "error",
                                "error": f"Tool {tool_name} is marked as dangerous and cannot be executed"
                            }
                            approved = False
                            required_approval = True

                        elif tool_def.safety_level == ToolSafety.REQUIRES_APPROVAL:
                            # Check if we should auto-approve
                            if auto_approve_safe_tools and self._is_safe_command(tool_name, tool_input):
                                # Auto-approve safe commands
                                logger.info(f"Auto-approving safe tool: {tool_name}")
                                tool_result = await self.tool_registry.execute_tool(
                                    tool_name,
                                    tool_input
                                )
                                approved = True
                                required_approval = True
                            else:
                                # Requires approval
                                logger.warning(f"Tool {tool_name} requires approval")
                                pending_approvals.append({
                                    "tool_use_id": tool_use_id,
                                    "tool_name": tool_name,
                                    "tool_input": tool_input,
                                    "reasoning": text_content,
                                })

                                tool_result = {
                                    "status": "pending",
                                    "message": "Waiting for approval from Master"
                                }
                                approved = False
                                required_approval = True

                        else:
                            # Safe tool - execute
                            logger.info(f"Executing safe tool: {tool_name}")
                            tool_result = await self.tool_registry.execute_tool(
                                tool_name,
                                tool_input
                            )
                            approved = True
                            required_approval = False

                        # Record execution
                        tool_executions.append(
                            ToolExecutionResult(
                                tool_use_id=tool_use_id,
                                tool_name=tool_name,
                                result=tool_result,
                                required_approval=required_approval,
                                approved=approved,
                            )
                        )

                        # Add tool result to conversation
                        api_messages.append({
                            "role": "assistant",
                            "content": response.content  # Include full response with tool_use
                        })

                        api_messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps(tool_result),
                                }
                            ]
                        })

                # If no tool use, we're done
                if not has_tool_use:
                    logger.info(f"No more tool use. Final response: {len(final_text)} chars")
                    break

                # If stop reason is not tool_use, we're also done
                if stop_reason != "tool_use":
                    logger.info(f"Stop reason: {stop_reason}")
                    break

            # Log total token usage
            log_meta = {
                "model": self.model,
                "messages_count": len(messages),
                "has_system": system is not None,
                "tool_iterations": iteration,
                "tools_used": len(tool_executions),
                **(meta or {})
            }

            await log_tokens(
                scope=TokenScope(scope),
                provider="anthropic_api",
                tokens_input=total_input_tokens,
                tokens_output=total_output_tokens,
                meta_json=json.dumps(log_meta)
            )

            logger.info(
                f"Claude API complete: {total_input_tokens} input, "
                f"{total_output_tokens} output tokens, "
                f"{len(tool_executions)} tools executed"
            )

            return {
                "text": final_text,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
                "model": self.model,
                "stop_reason": stop_reason,
                "tool_executions": [
                    {
                        "tool_name": te.tool_name,
                        "result": te.result,
                        "required_approval": te.required_approval,
                        "approved": te.approved,
                    }
                    for te in tool_executions
                ],
                "pending_approvals": pending_approvals,
            }

        except Exception as e:
            logger.error(f"Error calling Claude API with tools: {e}", exc_info=True)
            raise

    def _is_safe_command(self, tool_name: str, tool_input: Dict[str, Any]) -> bool:
        """
        Check if a command is safe to auto-approve.

        Safe commands include:
        - Read operations (read_file, list_directory)
        - Non-destructive bash commands (ls, cat, grep, etc.)
        - GET requests
        """
        if tool_name in ["read_file", "list_directory", "search_code", "recall"]:
            return True

        if tool_name == "run_bash":
            command = tool_input.get("command", "")

            # Check for dangerous patterns
            from app.tools.executor import DESTRUCTIVE_COMMANDS
            for dangerous in DESTRUCTIVE_COMMANDS:
                if dangerous in command:
                    return False

            # Safe read-only commands
            safe_commands = ["ls", "cat", "grep", "find", "echo", "pwd", "whoami", "date", "which"]
            first_word = command.strip().split()[0] if command.strip() else ""

            if first_word in safe_commands:
                return True

            # Default to unsafe for unknown commands
            return False

        if tool_name == "http_request":
            method = tool_input.get("method", "GET").upper()
            return method == "GET"

        # Default to requiring approval
        return False


# Import at module level to avoid circular dependency
from pydantic import BaseModel


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
