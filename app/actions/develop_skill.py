"""Skill development action handler.

This module handles internal learning and skill development actions
using ClaudeToolsClient for real tool execution.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from app.ai.claude_tools import get_claude_tools_client

logger = logging.getLogger(__name__)

# System prompt for skill development with tools
SKILL_DEVELOPMENT_PROMPT = """You are an autonomous AGI agent developing a new skill.

You have access to real tools to actually practice and develop this skill:
- read_file: Read file contents
- write_file: Create or overwrite files
- list_directory: List directory contents
- run_bash: Execute shell commands
- search_code: Search for patterns in code
- send_telegram_message: Send messages to Master
- http_request: Make HTTP API calls
- remember: Store information in long-term memory
- recall: Retrieve information from memory

IMPORTANT: Don't just describe how you would develop this skill - ACTUALLY DO IT:
1. Use tools to explore, experiment, and practice
2. Create files to document your learnings
3. Test your understanding by actually doing things
4. Store key insights in memory with the remember tool
5. Report significant discoveries to Master via Telegram

The workspace is at /app - you can create files, run experiments, and learn by doing."""


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute skill development action using real tools.

    Uses ClaudeToolsClient to actually practice and develop skills.

    Args:
        details: Action details containing:
            - skill_name: Name of skill to develop
            - approach: How to develop it
            - duration_estimate: Optional estimated duration in minutes

    Returns:
        Result dictionary with skill development outcomes
    """
    skill_name = details.get("skill_name", "unknown")
    approach = details.get("approach", "unspecified approach")
    duration_estimate = details.get("duration_estimate", "unknown")

    logger.info(f"Developing skill with real tools: {skill_name} ({approach})")

    try:
        # Get Claude Tools client (with real tool execution)
        client = get_claude_tools_client()

        # Build skill development prompt
        user_prompt = f"""Develop the following skill by actually practicing it:

SKILL: {skill_name}
APPROACH: {approach}
TIME BUDGET: {duration_estimate} minutes

Instructions:
1. First, use tools to understand the current environment and available resources
2. Practice the skill by actually doing relevant tasks
3. Create documentation of what you learned in /app/skills/{skill_name.replace(' ', '_')}.md
4. Store the most important insights in memory with the remember tool
5. Summarize your learnings at the end

Remember: Actually USE the tools to practice and learn, don't just describe what you would do."""

        # Call Claude with tools enabled
        response = await client.send_message_with_tools(
            messages=[{"role": "user", "content": user_prompt}],
            system=SKILL_DEVELOPMENT_PROMPT,
            max_tokens=4096,
            scope="proactive",
            meta={
                "action": "develop_skill",
                "skill_name": skill_name,
            },
            max_tool_iterations=10,  # Allow multiple tool uses for learning
            enable_tools=True,
            auto_approve_safe_tools=True,  # Auto-approve read operations
        )

        response_text = response.get("text", "").strip()
        usage = response.get("usage", {})
        tool_executions = response.get("tool_executions", [])
        pending_approvals = response.get("pending_approvals", [])

        # Log tool usage
        tools_used = [te["tool_name"] for te in tool_executions]
        logger.info(f"Skill development used tools: {tools_used}")

        result = {
            "skill_name": skill_name,
            "approach": approach,
            "duration_estimate": duration_estimate,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            "tools_executed": len(tool_executions),
            "tools_used": tools_used,
            "pending_approvals": len(pending_approvals),
            "outcome": response_text[:2000] if response_text else "Skill development completed",
        }

        logger.info(f"Skill development completed: {skill_name} with {len(tool_executions)} tool executions")

        return result

    except Exception as e:
        logger.error(f"Error in skill development: {e}", exc_info=True)
        return {
            "skill_name": skill_name,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


__all__ = ["execute"]
