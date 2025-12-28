"""Bot initialization and webhook configuration for Telegram."""

import logging
from typing import Optional
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings

logger = logging.getLogger(__name__)

# Global bot instance
_bot: Optional[Bot] = None


async def init_bot() -> Bot:
    """
    Initialize Telegram bot.

    If TELEGRAM_USE_POLLING is True, webhook will not be set.
    Otherwise, webhook will be configured if TELEGRAM_WEBHOOK_URL is provided.

    Returns:
        Bot instance
    """
    global _bot

    if _bot is not None:
        logger.warning("Bot already initialized")
        return _bot

    try:
        # Initialize bot with HTML parse mode by default
        _bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        logger.info("Bot initialized successfully")

        # Use polling mode - don't set webhook
        if settings.TELEGRAM_USE_POLLING:
            # Delete any existing webhook with retry
            import asyncio
            for attempt in range(3):
                try:
                    await _bot.delete_webhook(drop_pending_updates=False)
                    logger.info("Polling mode enabled, webhook deleted")
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"delete_webhook failed (attempt {attempt+1}), retrying in 5s: {e}")
                        await asyncio.sleep(5)
                    else:
                        logger.warning(f"delete_webhook failed after 3 attempts, continuing anyway: {e}")
            return _bot

        # Set webhook if URL is configured
        if settings.TELEGRAM_WEBHOOK_URL:
            webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/webhook/telegram"

            # Delete existing webhook first
            await _bot.delete_webhook(drop_pending_updates=True)
            logger.info("Deleted existing webhook")

            # Set new webhook
            await _bot.set_webhook(
                url=webhook_url,
                secret_token=settings.TELEGRAM_WEBHOOK_SECRET if settings.TELEGRAM_WEBHOOK_SECRET else None,
                drop_pending_updates=True
            )

            # Verify webhook was set
            webhook_info = await _bot.get_webhook_info()
            logger.info(
                f"Webhook set successfully:\n"
                f"  URL: {webhook_info.url}\n"
                f"  Pending updates: {webhook_info.pending_update_count}\n"
                f"  Max connections: {webhook_info.max_connections}"
            )
        else:
            logger.warning("TELEGRAM_WEBHOOK_URL not configured, webhook not set")

        return _bot

    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        raise


def get_bot() -> Bot:
    """
    Get global bot instance.

    Returns:
        Bot instance

    Raises:
        RuntimeError: If bot not initialized
    """
    if _bot is None:
        raise RuntimeError("Bot not initialized. Call init_bot() first.")
    return _bot


async def shutdown_bot() -> None:
    """Shutdown bot and delete webhook."""
    global _bot

    if _bot is None:
        logger.warning("Bot not initialized")
        return

    try:
        # Delete webhook
        await _bot.delete_webhook(drop_pending_updates=False)
        logger.info("Webhook deleted")

        # Close bot session
        await _bot.session.close()
        logger.info("Bot session closed")

        _bot = None

    except Exception as e:
        logger.error(f"Error shutting down bot: {e}")
        raise


__all__ = ["init_bot", "get_bot", "shutdown_bot"]
