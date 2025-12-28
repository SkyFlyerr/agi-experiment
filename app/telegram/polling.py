"""Telegram polling handler for receiving updates without webhook."""

import asyncio
import logging
from typing import Optional

from aiogram import Dispatcher, Bot, F
from aiogram.types import Update, Message, CallbackQuery

from app.telegram.ingestion import ingest_telegram_update
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramPoller:
    """
    Telegram polling handler that receives updates via long polling.

    This is an alternative to webhook for environments without SSL.
    Uses aiogram Dispatcher for polling, but routes updates through
    the same ingestion pipeline as webhook.
    """

    def __init__(self, bot: Bot):
        """
        Initialize poller with bot instance.

        Args:
            bot: aiogram Bot instance
        """
        self.bot = bot
        self.dp = Dispatcher()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Register message handler (catches all messages)
        @self.dp.message()
        async def handle_message(message: Message):
            """Route messages through ingestion pipeline."""
            try:
                logger.info(
                    f"Polling received message: chat_id={message.chat.id}, "
                    f"from={message.from_user.id if message.from_user else 'unknown'}, "
                    f"text={message.text[:50] if message.text else '[no text]'}..."
                )
                # Reconstruct Update object for ingestion pipeline
                update = Update(update_id=0, message=message)
                await ingest_telegram_update(update)
            except Exception as e:
                logger.error(f"Error processing polled message: {e}", exc_info=True)

        # Register callback query handler (catches button presses)
        @self.dp.callback_query()
        async def handle_callback(callback: CallbackQuery):
            """Route callback queries through ingestion pipeline."""
            try:
                logger.info(
                    f"Polling received callback: chat_id={callback.message.chat.id if callback.message else 'unknown'}, "
                    f"data={callback.data}"
                )
                # Reconstruct Update object for ingestion pipeline
                update = Update(update_id=0, callback_query=callback)
                await ingest_telegram_update(update)
            except Exception as e:
                logger.error(f"Error processing polled callback: {e}", exc_info=True)

    async def start(self) -> None:
        """Start polling for updates."""
        if self._running:
            logger.warning("Telegram poller already running")
            return

        self._running = True
        logger.info("Starting Telegram polling...")

        # Delete any existing webhook first
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Deleted existing webhook before starting polling")
        except Exception as e:
            logger.warning(f"Could not delete webhook: {e}")

        # Start polling in background task
        self._task = asyncio.create_task(self._polling_loop())
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        """Stop polling gracefully."""
        if not self._running:
            logger.warning("Telegram poller not running")
            return

        logger.info("Stopping Telegram polling...")
        self._running = False

        # Stop dispatcher
        try:
            await self.dp.stop_polling()
        except Exception as e:
            logger.warning(f"Error stopping dispatcher polling: {e}")

        # Cancel and wait for task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Telegram polling stopped")

    async def _polling_loop(self) -> None:
        """Main polling loop using aiogram dispatcher."""
        try:
            await self.dp.start_polling(
                self.bot,
                polling_timeout=30,  # Long polling timeout
                handle_signals=False,  # Don't handle signals (let main app do it)
                close_bot_session=False,  # Don't close bot session (we manage it)
            )
        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
        except Exception as e:
            logger.error(f"Error in polling loop: {e}", exc_info=True)

    @property
    def is_running(self) -> bool:
        """Check if poller is running."""
        return self._running


# Global poller instance
_poller: Optional[TelegramPoller] = None


async def get_poller(bot: Bot) -> TelegramPoller:
    """
    Get or create global poller instance.

    Args:
        bot: aiogram Bot instance

    Returns:
        TelegramPoller instance
    """
    global _poller

    if _poller is None:
        _poller = TelegramPoller(bot)

    return _poller


__all__ = ["TelegramPoller", "get_poller"]
