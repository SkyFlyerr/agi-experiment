"""Token budget management for proactive scope.

This module enforces the 7M tokens/day budget for proactive operations only.
Reactive scope is unlimited.
"""

import logging
from datetime import date, datetime
from typing import Dict, Any

from app.config import settings
from app.db import get_db
from app.db.models import TokenScope

logger = logging.getLogger(__name__)

# Constants
PROACTIVE_DAILY_LIMIT = settings.PROACTIVE_DAILY_TOKEN_LIMIT
PROACTIVE_WARNING_THRESHOLD = 0.8  # Warn at 5.6M tokens
PROACTIVE_CRITICAL_THRESHOLD = 0.95  # Critical at 6.65M tokens


async def get_daily_token_usage(
    scope: str = "proactive",
    target_date: date = None,
) -> int:
    """
    Get total token usage for a specific scope and date.

    Args:
        scope: Token scope ("proactive" or "reactive")
        target_date: Date to query (default: today)

    Returns:
        Total tokens used for the specified scope and date
    """
    if target_date is None:
        target_date = date.today()

    db = get_db()

    try:
        result = await db.fetch_one(
            """
            SELECT COALESCE(SUM(tokens_total), 0) as total_tokens
            FROM token_ledger
            WHERE scope = $1
              AND DATE(created_at) = $2
            """,
            scope,
            target_date,
        )

        total_tokens = result["total_tokens"] if result else 0

        logger.debug(
            f"Token usage for {scope} on {target_date}: {total_tokens:,} tokens"
        )
        return total_tokens

    except Exception as e:
        logger.error(f"Error fetching daily token usage: {e}")
        raise


async def get_remaining_budget(scope: str = "proactive") -> int:
    """
    Calculate remaining token budget for today.

    Args:
        scope: Token scope ("proactive" or "reactive")

    Returns:
        Remaining tokens available today (0 if over budget)
        For reactive scope, returns a large number (effectively unlimited)
    """
    if scope == "reactive":
        # Reactive scope is unlimited
        return 999_999_999

    # Get today's usage
    used = await get_daily_token_usage(scope=scope, target_date=date.today())

    # Calculate remaining
    remaining = max(0, PROACTIVE_DAILY_LIMIT - used)

    # Log warnings
    usage_ratio = used / PROACTIVE_DAILY_LIMIT
    if usage_ratio >= PROACTIVE_CRITICAL_THRESHOLD:
        logger.warning(
            f"CRITICAL: Proactive budget at {usage_ratio:.1%} "
            f"({used:,}/{PROACTIVE_DAILY_LIMIT:,} tokens)"
        )
    elif usage_ratio >= PROACTIVE_WARNING_THRESHOLD:
        logger.warning(
            f"WARNING: Proactive budget at {usage_ratio:.1%} "
            f"({used:,}/{PROACTIVE_DAILY_LIMIT:,} tokens)"
        )

    logger.debug(f"Remaining budget for {scope}: {remaining:,} tokens")
    return remaining


async def check_budget_available(
    tokens_needed: int,
    scope: str = "proactive",
) -> bool:
    """
    Check if sufficient budget is available for an operation.

    Args:
        tokens_needed: Estimated tokens needed for operation
        scope: Token scope ("proactive" or "reactive")

    Returns:
        True if budget is available, False otherwise
        Always True for reactive scope
    """
    if scope == "reactive":
        # Reactive scope is unlimited
        return True

    remaining = await get_remaining_budget(scope=scope)
    available = remaining >= tokens_needed

    if not available:
        logger.warning(
            f"Insufficient budget: need {tokens_needed:,}, "
            f"have {remaining:,} remaining"
        )

    return available


async def get_token_stats() -> Dict[str, Any]:
    """
    Get comprehensive token usage statistics.

    Returns:
        Dictionary with token statistics:
        {
            "today": {
                "proactive": {"used": int, "remaining": int, "limit": int},
                "reactive": {"used": int}
            },
            "yesterday": {
                "proactive": {"used": int},
                "reactive": {"used": int}
            }
        }
    """
    db = get_db()

    try:
        today = date.today()
        from datetime import timedelta

        yesterday = today - timedelta(days=1)

        # Get today's usage
        proactive_today = await get_daily_token_usage(
            scope="proactive", target_date=today
        )
        reactive_today = await get_daily_token_usage(
            scope="reactive", target_date=today
        )

        # Get yesterday's usage
        proactive_yesterday = await get_daily_token_usage(
            scope="proactive", target_date=yesterday
        )
        reactive_yesterday = await get_daily_token_usage(
            scope="reactive", target_date=yesterday
        )

        stats = {
            "today": {
                "proactive": {
                    "used": proactive_today,
                    "remaining": max(0, PROACTIVE_DAILY_LIMIT - proactive_today),
                    "limit": PROACTIVE_DAILY_LIMIT,
                    "usage_ratio": proactive_today / PROACTIVE_DAILY_LIMIT,
                },
                "reactive": {
                    "used": reactive_today,
                },
            },
            "yesterday": {
                "proactive": {
                    "used": proactive_yesterday,
                },
                "reactive": {
                    "used": reactive_yesterday,
                },
            },
        }

        logger.debug(f"Token stats: proactive={proactive_today:,}, reactive={reactive_today:,}")
        return stats

    except Exception as e:
        logger.error(f"Error fetching token stats: {e}")
        raise


__all__ = [
    "get_daily_token_usage",
    "get_remaining_budget",
    "check_budget_available",
    "get_token_stats",
    "PROACTIVE_DAILY_LIMIT",
    "PROACTIVE_WARNING_THRESHOLD",
    "PROACTIVE_CRITICAL_THRESHOLD",
]
