"""AI integration module for Server Agent vNext."""

# Proactive AI (budget, client, prompts)
from .budget import (
    get_daily_token_usage,
    get_remaining_budget,
    check_budget_available,
    get_token_stats,
    PROACTIVE_DAILY_LIMIT,
    PROACTIVE_WARNING_THRESHOLD,
    PROACTIVE_CRITICAL_THRESHOLD,
)
from .client import ClaudeClient, get_claude_client
from .claude_cli import ClaudeCLIClient, RateLimitError
from .proactive_prompts import (
    build_proactive_prompt,
    PROACTIVE_SYSTEM_PROMPT,
    ProactiveDecision,
)

# Reactive AI (Haiku classification, Claude execution)
from .haiku import classify_intent, ClassificationResult
from .claude import execute_task, ExecutionResult
from .context import build_conversation_context
from .prompts import (
    CLASSIFICATION_SYSTEM_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    build_classification_prompt,
    build_execution_prompt,
)

__all__ = [
    # Budget (proactive)
    "get_daily_token_usage",
    "get_remaining_budget",
    "check_budget_available",
    "get_token_stats",
    "PROACTIVE_DAILY_LIMIT",
    "PROACTIVE_WARNING_THRESHOLD",
    "PROACTIVE_CRITICAL_THRESHOLD",
    # Client (proactive)
    "ClaudeClient",
    "ClaudeCLIClient",
    "RateLimitError",
    "get_claude_client",
    # Proactive prompts
    "build_proactive_prompt",
    "PROACTIVE_SYSTEM_PROMPT",
    "ProactiveDecision",
    # Reactive classification
    "classify_intent",
    "ClassificationResult",
    # Reactive execution
    "execute_task",
    "ExecutionResult",
    # Reactive context
    "build_conversation_context",
    # Reactive prompts
    "CLASSIFICATION_SYSTEM_PROMPT",
    "EXECUTION_SYSTEM_PROMPT",
    "build_classification_prompt",
    "build_execution_prompt",
]
