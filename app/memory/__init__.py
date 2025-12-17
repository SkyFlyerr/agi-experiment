"""Memory management module for proactive agent."""

from .writeback import (
    summarize_cycle,
    update_working_memory,
    store_next_prompt_aroma,
    get_recent_actions,
)

__all__ = [
    "summarize_cycle",
    "update_working_memory",
    "store_next_prompt_aroma",
    "get_recent_actions",
]
