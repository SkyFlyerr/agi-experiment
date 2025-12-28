"""Telegram integration package for Server Agent vNext."""

from app.telegram.bot import init_bot, get_bot, shutdown_bot
from app.telegram.ingestion import ingest_telegram_update
from app.telegram.responses import send_message, send_approval_request
from app.telegram.polling import TelegramPoller, get_poller

__all__ = [
    "init_bot",
    "get_bot",
    "shutdown_bot",
    "ingest_telegram_update",
    "send_message",
    "send_approval_request",
    "TelegramPoller",
    "get_poller",
]
