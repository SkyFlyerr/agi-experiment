"""Memory writeback system for maintaining context between proactive cycles.

This module handles:
- Summarizing cycle results
- Updating working memory
- Storing context for next prompt
- Compressing long-term memory
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.db import get_db

logger = logging.getLogger(__name__)


async def summarize_cycle(
    decision: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Summarize a proactive cycle for storage.

    Args:
        decision: The decision that was made
        result: The result of executing that decision

    Returns:
        Summary dictionary suitable for storage
    """
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": decision.get("action", "unknown"),
        "certainty": decision.get("certainty", 0.0),
        "significance": decision.get("significance", 0.0),
        "type": decision.get("type", "unknown"),
        "result_status": "success" if result.get("success", False) else "failed",
        "result_summary": _extract_result_summary(result),
    }

    logger.debug(f"Cycle summary: {summary['action']} - {summary['result_status']}")
    return summary


def _extract_result_summary(result: Dict[str, Any]) -> str:
    """Extract a concise summary from result."""
    if not result.get("success", False):
        return f"Error: {result.get('error', 'Unknown error')}"

    result_data = result.get("result", {})

    # Different summarization based on result type
    if isinstance(result_data, dict):
        if "skill_name" in result_data:
            return f"Developed skill: {result_data['skill_name']}"
        elif "task_id" in result_data:
            return f"Completed task: {result_data['task_id']}"
        elif "message_id" in result_data:
            return f"Sent message (ID: {result_data['message_id']})"
        elif "duration_actual" in result_data:
            return f"Meditated for {result_data['duration_actual']:.1f}s"
        elif "response_status" in result_data:
            return f"Asked Master: {result_data['response_status']}"
        else:
            return "Action completed successfully"
    else:
        return str(result_data)[:100]  # Truncate to 100 chars


async def update_working_memory(summary: Dict[str, Any]) -> None:
    """
    Update working memory with cycle summary.

    For now, we store in a simple JSON metadata table.
    In production, this could be a dedicated working_memory table
    or a more sophisticated memory system.

    Args:
        summary: Cycle summary to store
    """
    db = get_db()

    try:
        # Store in a metadata-like structure
        # We can use the deployments table's report_text for now,
        # or create a new simple key-value metadata table

        # For simplicity, we'll append to a JSON file-like structure in DB
        # In real implementation, use a proper memory table

        await db.execute(
            """
            INSERT INTO token_ledger (scope, provider, tokens_input, tokens_output, tokens_total, meta_json)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            "proactive",
            "memory",
            0,
            0,
            0,
            {"type": "working_memory_update", "summary": summary},
        )

        logger.debug(f"Working memory updated: {summary['action']}")

    except Exception as e:
        logger.error(f"Error updating working memory: {e}")
        # Don't raise - memory updates shouldn't crash the system


async def store_next_prompt_aroma(context: Dict[str, Any]) -> None:
    """
    Store contextual 'aroma' for next proactive prompt.

    This helps maintain continuity between cycles by storing:
    - Current focus/priority
    - Pending items
    - Emotional/contextual state

    Args:
        context: Context to preserve for next cycle
    """
    db = get_db()

    try:
        await db.execute(
            """
            INSERT INTO token_ledger (scope, provider, tokens_input, tokens_output, tokens_total, meta_json)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            "proactive",
            "memory",
            0,
            0,
            0,
            {"type": "prompt_aroma", "context": context, "timestamp": datetime.utcnow().isoformat()},
        )

        logger.debug("Stored prompt aroma for next cycle")

    except Exception as e:
        logger.error(f"Error storing prompt aroma: {e}")


async def get_recent_actions(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve recent action summaries from working memory.

    Args:
        limit: Maximum number of recent actions to retrieve

    Returns:
        List of recent action summaries
    """
    db = get_db()

    try:
        # Query recent working memory entries
        rows = await db.fetch_all(
            """
            SELECT meta_json, created_at
            FROM token_ledger
            WHERE scope = 'proactive'
              AND provider = 'memory'
              AND meta_json->>'type' = 'working_memory_update'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

        actions = []
        for row in rows:
            meta = row["meta_json"]
            if "summary" in meta:
                summary = meta["summary"]
                summary["timestamp"] = row["created_at"].isoformat()
                actions.append(summary)

        logger.debug(f"Retrieved {len(actions)} recent actions from memory")
        return actions

    except Exception as e:
        logger.error(f"Error retrieving recent actions: {e}")
        return []


async def get_last_prompt_aroma() -> Optional[Dict[str, Any]]:
    """
    Retrieve the last stored prompt aroma.

    Returns:
        Last prompt aroma context, or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(
            """
            SELECT meta_json, created_at
            FROM token_ledger
            WHERE scope = 'proactive'
              AND provider = 'memory'
              AND meta_json->>'type' = 'prompt_aroma'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

        if row and "context" in row["meta_json"]:
            context = row["meta_json"]["context"]
            context["retrieved_at"] = datetime.utcnow().isoformat()
            logger.debug("Retrieved last prompt aroma")
            return context

        return None

    except Exception as e:
        logger.error(f"Error retrieving prompt aroma: {e}")
        return None


__all__ = [
    "summarize_cycle",
    "update_working_memory",
    "store_next_prompt_aroma",
    "get_recent_actions",
    "get_last_prompt_aroma",
]
