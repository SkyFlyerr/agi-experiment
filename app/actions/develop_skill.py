"""Skill development action handler.

This module handles internal learning and skill development actions
using ClaudeToolsClient for real tool execution.

Follows AI Harness patterns from Anthropic research:
- Focus on one skill per session
- Document learnings in progress files
- Update feature_list.json status
- Maintain clean state
"""

import logging
import json
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from app.ai.claude_tools import get_claude_tools_client

logger = logging.getLogger(__name__)

# Paths for harness pattern files
FEATURE_LIST_PATH = Path("/app/data/feature_list.json")
PROGRESS_FILE_PATH = Path("/app/data/claude-progress.txt")

# System prompt for skill development with AI Harness patterns
SKILL_DEVELOPMENT_PROMPT = """You are an autonomous AGI agent developing a skill following AI Harness patterns.

## Available Tools
- read_file: Read file contents
- write_file: Create or overwrite files
- list_directory: List directory contents
- run_bash: Execute shell commands
- search_code: Search for patterns in code
- send_telegram_message: Send messages to Master
- http_request: Make HTTP API calls
- remember: Store information in long-term memory
- recall: Retrieve information from memory

## AI Harness Development Pattern

Follow this structured approach:

1. **Read Current State**
   - Check data/feature_list.json for related features
   - Read data/claude-progress.txt for context
   - Understand what's already implemented

2. **Practice the Skill**
   - Actually USE tools to practice
   - Create test cases to verify understanding
   - Run experiments and observe results

3. **Document Learnings**
   - Create /app/skills/{skill_name}.md with findings
   - Store key insights in memory with remember tool
   - Update progress file with session notes

4. **Update Feature Status**
   - If skill relates to a feature in feature_list.json
   - Update feature status if now passing
   - NEVER mark as passing without verification tests

5. **Maintain Clean State**
   - Commit any code changes with descriptive messages
   - Update progress file
   - Leave codebase in mergeable state

CRITICAL:
- Focus on ONE skill completely
- Test everything before marking as complete
- Update progress files for session continuity
- Don't just describe - ACTUALLY DO IT"""


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute skill development action using real tools.

    Uses ClaudeToolsClient to actually practice and develop skills.
    Follows AI Harness patterns for systematic skill development.

    Args:
        details: Action details containing:
            - skill_name: Name of skill to develop
            - approach: How to develop it
            - related_feature: Optional feature ID from feature_list.json
            - duration_estimate: Optional estimated duration in minutes

    Returns:
        Result dictionary with skill development outcomes
    """
    skill_name = details.get("skill_name", "unknown")
    approach = details.get("approach", "unspecified approach")
    related_feature = details.get("related_feature", None)
    duration_estimate = details.get("duration_estimate", "unknown")

    logger.info(f"Developing skill with AI Harness pattern: {skill_name} ({approach})")

    # Load feature context if related_feature provided
    feature_context = ""
    if related_feature:
        try:
            if FEATURE_LIST_PATH.exists():
                with open(FEATURE_LIST_PATH, "r") as f:
                    feature_list = json.load(f)
                    for feature in feature_list.get("features", []):
                        if feature.get("id") == related_feature:
                            feature_context = f"""
## Related Feature from feature_list.json

ID: {feature.get('id')}
Name: {feature.get('name')}
Status: {feature.get('status')}
Priority: {feature.get('priority')}
Steps:
{chr(10).join('- ' + step for step in feature.get('steps', []))}

If you successfully develop this skill and can verify it works,
update the feature status to 'passing' in feature_list.json.
"""
                            break
        except Exception as e:
            logger.warning(f"Could not load feature context: {e}")

    try:
        # Get Claude Tools client (with real tool execution)
        client = get_claude_tools_client()

        # Build skill development prompt with harness patterns
        user_prompt = f"""Develop the following skill using AI Harness patterns:

SKILL: {skill_name}
APPROACH: {approach}
RELATED FEATURE: {related_feature or 'None'}
TIME BUDGET: {duration_estimate} minutes
{feature_context}

## Session Startup (do these first):
1. Read /app/data/claude-progress.txt to understand current state
2. Check if there's related context from previous sessions
3. Understand what's already implemented

## Skill Development Steps:
1. Practice the skill by actually using tools
2. Create test cases to verify your understanding
3. Run experiments and observe results
4. Document learnings in /app/skills/{skill_name.replace(' ', '_').lower()}.md

## Session Cleanup (do these at end):
1. Store key insights with the remember tool
2. Update /app/data/claude-progress.txt with:
   - What you learned
   - Any issues encountered
   - Next steps for future sessions
3. If skill is verified working, update feature status

Remember: ACTUALLY DO IT - use tools, run tests, verify results."""

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

        # Check if feature was updated
        feature_updated = False
        if related_feature and "write_file" in tools_used:
            # Check if feature_list.json was modified
            for te in tool_executions:
                if te.get("tool_name") == "write_file":
                    tool_input = te.get("tool_input", {})
                    if "feature_list.json" in str(tool_input.get("path", "")):
                        feature_updated = True
                        break

        result = {
            "skill_name": skill_name,
            "approach": approach,
            "related_feature": related_feature,
            "duration_estimate": duration_estimate,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            "tools_executed": len(tool_executions),
            "tools_used": tools_used,
            "pending_approvals": len(pending_approvals),
            "feature_updated": feature_updated,
            "outcome": response_text[:2000] if response_text else "Skill development completed",
            "harness_pattern": "ai_harness_v1",
        }

        logger.info(
            f"Skill development completed: {skill_name} with {len(tool_executions)} tool executions"
            f"{' (feature updated)' if feature_updated else ''}"
        )

        return result

    except Exception as e:
        logger.error(f"Error in skill development: {e}", exc_info=True)
        return {
            "skill_name": skill_name,
            "related_feature": related_feature,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "harness_pattern": "ai_harness_v1",
        }


__all__ = ["execute"]
