"""Token ledger operations."""

import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID

from .models import TokenLedger, TokenScope
from .queries import (
    LOG_TOKENS,
    GET_DAILY_TOKEN_USAGE,
    GET_TOKEN_STATS_BY_SCOPE,
    GET_TOKEN_STATS_BY_PROVIDER,
)
from . import get_db

logger = logging.getLogger(__name__)


async def log_tokens(
    scope: TokenScope,
    provider: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    meta_json: Optional[Dict[str, Any]] = None,
) -> TokenLedger:
    """
    Log token usage to the ledger.

    Args:
        scope: Token scope (proactive/reactive)
        provider: AI provider (e.g., "anthropic", "openai")
        tokens_input: Number of input tokens
        tokens_output: Number of output tokens
        meta_json: Optional metadata (model name, job_id, etc.)

    Returns:
        Created TokenLedger instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        scope_value = scope.value if isinstance(scope, TokenScope) else scope

        # Calculate total tokens
        tokens_total = tokens_input + tokens_output

        row = await db.fetch_one(
            LOG_TOKENS,
            scope_value,
            provider,
            tokens_input,
            tokens_output,
            tokens_total,
            meta_json,
        )

        logger.info(
            f"Logged {tokens_total} tokens (scope={scope_value}, provider={provider})"
        )
        return TokenLedger(**row)

    except Exception as e:
        logger.error(
            f"Error logging tokens (scope={scope}, provider={provider}): {e}"
        )
        raise


async def get_daily_token_usage(
    target_date: date,
) -> List[Dict[str, Any]]:
    """
    Get token usage for a specific date, grouped by scope and provider.

    Args:
        target_date: Date to query

    Returns:
        List of dictionaries with keys: scope, provider, total_tokens
    """
    db = get_db()

    try:
        rows = await db.fetch_all(GET_DAILY_TOKEN_USAGE, target_date)

        logger.debug(f"Fetched daily token usage for {target_date}: {len(rows)} rows")
        return rows

    except Exception as e:
        logger.error(f"Error fetching daily token usage for {target_date}: {e}")
        raise


async def get_token_stats(
    since: Optional[datetime] = None,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Get aggregated token statistics.

    Args:
        since: Start datetime for aggregation (default: 7 days ago)
        days_back: Number of days to look back if since is not provided

    Returns:
        Dictionary with token statistics:
        {
            "by_scope": [{"scope": "proactive", "total_input": 1000, ...}, ...],
            "by_provider": [{"provider": "anthropic", "total_input": 1000, ...}, ...],
            "period_start": datetime,
            "period_end": datetime,
        }
    """
    db = get_db()

    try:
        # Default to looking back N days
        if since is None:
            since = datetime.utcnow() - timedelta(days=days_back)

        # Fetch stats by scope
        scope_stats = await db.fetch_all(GET_TOKEN_STATS_BY_SCOPE, since)

        # Fetch stats by provider
        provider_stats = await db.fetch_all(GET_TOKEN_STATS_BY_PROVIDER, since)

        stats = {
            "by_scope": scope_stats,
            "by_provider": provider_stats,
            "period_start": since,
            "period_end": datetime.utcnow(),
        }

        logger.debug(
            f"Fetched token stats since {since}: "
            f"{len(scope_stats)} scopes, {len(provider_stats)} providers"
        )
        return stats

    except Exception as e:
        logger.error(f"Error fetching token stats since {since}: {e}")
        raise


__all__ = [
    "log_tokens",
    "get_daily_token_usage",
    "get_token_stats",
]
