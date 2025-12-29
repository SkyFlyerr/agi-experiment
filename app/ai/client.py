"""Claude AI client wrapper for Server Agent vNext."""

import logging
from typing import Dict, Any, Optional, List
import anthropic
from anthropic.types import Message, Usage

from app.config import settings
from app.db import get_db
from app.db.tokens import log_tokens
from app.db.models import TokenScope

logger = logging.getLogger(__name__)


def get_claude_client(api_key: str = None, model: str = None):
    """
    Get appropriate Claude client based on API key type.

    Args:
        api_key: OAuth token (if None, uses settings.CLAUDE_CODE_OAUTH_TOKEN)
        model: Model to use (if None, uses settings.CLAUDE_MODEL)

    Returns:
        ClaudeClient or ClaudeCLIClient (ClaudeCLIClient for OAuth tokens)
    """
    # Determine which key to use - ALWAYS use OAuth token with Claude CLI
    if api_key is None:
        api_key = settings.CLAUDE_CODE_OAUTH_TOKEN
        if not api_key:
            logger.error("CLAUDE_CODE_OAUTH_TOKEN is not set!")
            raise ValueError("CLAUDE_CODE_OAUTH_TOKEN is required but not set")

    model = model or settings.CLAUDE_MODEL

    # OAuth tokens (sk-ant-oat*) MUST use Claude CLI - they don't work with Anthropic API directly
    # Regular API keys can use the SDK directly
    if api_key.startswith("sk-ant-oat"):
        from .claude_cli import ClaudeCLIClient
        logger.info(f"Using ClaudeCLIClient for OAuth token (starts with: {api_key[:15]}...)")
        return ClaudeCLIClient(model=model)
    else:
        logger.info("Using ClaudeClient with API key")
        return ClaudeClient(api_key=api_key, model=model)


class ClaudeClient:
    """Wrapper around Anthropic Claude API with token logging."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key or OAuth token (sk-ant-oat01-...)
            model: Model to use (default: Claude 3.5 Sonnet)
        """
        # Check if this is an OAuth token or regular API key
        if api_key.startswith("sk-ant-oat"):
            # OAuth token (from Claude Max subscription)
            self.client = anthropic.Anthropic(auth_token=api_key)
            logger.info(f"Claude client initialized with OAuth token (Claude Max)")
        else:
            # Regular API key (pay-as-you-go)
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info(f"Claude client initialized with API key")

        self.model = model
        logger.info(f"Using model: {model}")

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        scope: str = "reactive",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send message to Claude and log token usage.

        Args:
            messages: List of message dicts with "role" and "content"
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            scope: Token scope for logging ("proactive" or "reactive")
            meta: Optional metadata to log with tokens

        Returns:
            Dictionary with response text and metadata:
            {
                "text": str,
                "usage": {"input_tokens": int, "output_tokens": int},
                "model": str,
                "stop_reason": str
            }
        """
        try:
            # Call Claude API (synchronous, but we can wrap it)
            # Note: anthropic SDK doesn't have async support yet, so we use sync
            response: Message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages,
            )

            # Extract response
            response_text = ""
            if response.content:
                for block in response.content:
                    if block.type == "text":
                        response_text += block.text

            # Log token usage
            usage: Usage = response.usage
            log_meta = {
                "model": self.model,
                "stop_reason": response.stop_reason,
                **(meta or {}),
            }

            await log_tokens(
                scope=TokenScope(scope),
                provider="anthropic",
                tokens_input=usage.input_tokens,
                tokens_output=usage.output_tokens,
                meta_json=log_meta,
            )

            logger.info(
                f"Claude response: {usage.input_tokens} input tokens, "
                f"{usage.output_tokens} output tokens, scope={scope}"
            )

            return {
                "text": response_text,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                },
                "model": self.model,
                "stop_reason": response.stop_reason,
            }

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise


# Global client instance
# Note: get_claude_client() is now defined at the top of this file (line 16)
# It automatically chooses ClaudeClient vs ClaudeCLIClient based on token type


__all__ = ["ClaudeClient", "get_claude_client"]
