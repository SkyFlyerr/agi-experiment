"""Claude CLI client wrapper for OAuth token authentication."""

import logging
import subprocess
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.config import settings
from app.db import get_db
from app.db.tokens import log_tokens
from app.db.models import TokenScope

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Exception raised when Claude API rate limit is reached."""

    def __init__(self, message: str, reset_time: Optional[datetime] = None):
        """
        Initialize RateLimitError.

        Args:
            message: Original error message from Claude CLI
            reset_time: Datetime when the rate limit resets (UTC)
        """
        super().__init__(message)
        self.message = message
        self.reset_time = reset_time or self._parse_reset_time(message)

    @staticmethod
    def _parse_reset_time(message: str) -> Optional[datetime]:
        """
        Parse reset time from error message.

        Handles format: "Limit reached · resets 1am (UTC)"

        Args:
            message: Error message containing reset time

        Returns:
            Datetime of reset time in UTC, or None if parsing fails
        """
        try:
            # Pattern: "resets 1am (UTC)" or "resets 1pm (UTC)"
            match = re.search(r'resets\s+(\d{1,2})(am|pm)\s*\(UTC\)', message, re.IGNORECASE)
            if not match:
                return None

            hour = int(match.group(1))
            period = match.group(2).lower()

            # Convert to 24-hour format
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            # Get current UTC time
            now = datetime.now(timezone.utc)

            # Build reset datetime for today
            reset_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)

            # If reset time already passed today, it's tomorrow
            if reset_time <= now:
                reset_time = reset_time.replace(day=now.day + 1)

            logger.info(f"Parsed rate limit reset time: {reset_time.isoformat()}")
            return reset_time

        except Exception as e:
            logger.warning(f"Failed to parse reset time from '{message}': {e}")
            return None

    @staticmethod
    def is_rate_limit_error(message: str) -> bool:
        """Check if error message indicates a rate limit."""
        return 'limit reached' in message.lower()


class ClaudeCLIClient:
    """Wrapper around Claude CLI for OAuth token support."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Claude CLI client.

        Args:
            model: Model to use (default: Claude 3.5 Sonnet)
        """
        self.model = model
        logger.info(f"Claude CLI client initialized with model: {model}")

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
        Send message to Claude via CLI and log token usage.

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
            # Build prompt from messages
            prompt_parts = []
            if system:
                prompt_parts.append(f"<system>{system}</system>")

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    prompt_parts.append(f"<user>{content}</user>")
                elif role == "assistant":
                    prompt_parts.append(f"<assistant>{content}</assistant>")

            prompt = "\n\n".join(prompt_parts)

            # Call Claude CLI
            # Note: Claude CLI uses --print for non-interactive output
            cmd = [
                "claude",
                "--print",  # Non-interactive mode
                "--model", self.model,
                "--output-format", "text",  # Get plain text response
                prompt
            ]

            logger.debug(f"Executing Claude CLI: {' '.join(cmd[:6])}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                check=False
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Claude CLI error: {error_msg}")
                
                # Check for rate limit error
                if RateLimitError.is_rate_limit_error(error_msg):
                    raise RateLimitError(error_msg)
                
                raise Exception(f"Claude CLI failed: {error_msg}")

            # Parse response
            response_text = result.stdout.strip()

            # Try to parse as JSON first (if --json worked)
            try:
                response_data = json.loads(response_text)
                text = response_data.get("text", response_text)
                input_tokens = response_data.get("input_tokens", 0)
                output_tokens = response_data.get("output_tokens", 0)
            except json.JSONDecodeError:
                # Plain text response
                text = response_text
                # Estimate tokens (rough approximation)
                input_tokens = len(prompt) // 4
                output_tokens = len(text) // 4

            # Log token usage
            log_meta = {
                "model": self.model,
                "messages_count": len(messages),
                "has_system": system is not None,
                **(meta or {})
            }

            await log_tokens(
                scope=TokenScope(scope),
                provider="claude_cli",
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                meta_json=json.dumps(log_meta)
            )

            logger.info(
                f"Claude CLI response: {len(text)} chars, "
                f"{input_tokens} input tokens, {output_tokens} output tokens"
            )

            return {
                "text": text,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                },
                "model": self.model,
                "stop_reason": "end_turn"
            }

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timeout after 120s")
            raise Exception("Claude CLI request timed out")
        except Exception as e:
            logger.error(f"Error calling Claude CLI: {e}")
            raise
