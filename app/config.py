"""
Configuration module for Server Agent vNext
Loads settings from environment variables
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Database
    DATABASE_URL: str = "postgresql://agent:agent_password@postgres:5432/server_agent"

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    MASTER_CHAT_IDS: str = "46808774"  # Comma-separated list

    # Claude Code
    CLAUDE_CODE_OAUTH_TOKEN: str
    CLAUDE_CODE_API_URL: str = "https://api.anthropic.com/v1"
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Haiku (can use same Anthropic API)
    HAIKU_API_KEY: str = ""  # If empty, use CLAUDE_CODE_OAUTH_TOKEN
    HAIKU_MODEL: str = "claude-3-5-haiku-20241022"

    # MinIO (optional)
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "server-agent"
    MINIO_ENABLED: bool = False

    # Token budget
    PROACTIVE_DAILY_TOKEN_LIMIT: int = 7_000_000
    REACTIVE_TOKEN_WARNING_THRESHOLD: int = 100_000  # Warn if single request exceeds this

    # Scheduling
    PROACTIVE_MIN_INTERVAL_SECONDS: int = 60  # Minimum 1 minute between cycles
    PROACTIVE_MAX_INTERVAL_SECONDS: int = 3600  # Maximum 1 hour between cycles

    # Context
    MESSAGE_HISTORY_LIMIT: int = 30  # Last N messages to include in context

    # Approval
    APPROVAL_TIMEOUT_SECONDS: int = 3600  # 1 hour timeout for approvals

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def master_chat_ids_list(self) -> List[int]:
        """Parse master chat IDs from comma-separated string"""
        return [int(chat_id.strip()) for chat_id in self.MASTER_CHAT_IDS.split(",")]

    @property
    def haiku_api_key_resolved(self) -> str:
        """Get Haiku API key, falling back to Claude Code token"""
        return self.HAIKU_API_KEY or self.CLAUDE_CODE_OAUTH_TOKEN


# Global settings instance
settings = Settings()
