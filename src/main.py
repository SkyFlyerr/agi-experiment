"""src/main.py

Main entry point for the Server-Agent system.
"""

import asyncio
import logging
import os
import signal

from proactivity_loop import ProactivityLoop
from reactive_loop import ReactiveLoop
from state_manager import StateManager
from telegram_bot import TelegramBot
from telegram_client import AgentTelegramClient

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ServerAgent:
    """Main server agent orchestrator."""

    def __init__(self):
        self.state_manager = StateManager()
        self.telegram_bot = None
        self.telegram_client = None
        self.proactivity_loop = None
        self.reactive_loop = None
        self.health_server_task: asyncio.Task | None = None
        self.proactive_task: asyncio.Task | None = None
        self.reactive_task: asyncio.Task | None = None
        self.running = False

    async def start(self):
        """Start all components."""
        logger.info("=== Starting Server-Agent ===")

        # Start minimal health/metrics server (optional)
        try:
            from health_server import create_app
            import uvicorn

            host = os.getenv("HEALTH_HOST", "127.0.0.1")
            port = int(os.getenv("HEALTH_PORT", "8000"))

            app = create_app(self.state_manager)
            config = uvicorn.Config(app, host=host, port=port, log_level="info")
            server = uvicorn.Server(config)

            self.health_server_task = asyncio.create_task(server.serve())
            logger.info(f"Health server started on http://{host}:{port}")
        except Exception as e:
            logger.warning(f"Health server not started: {e}")

        # Initialize Telegram user client (Telethon) ONLY if explicitly enabled.
        # Telethon may require interactive login code; that must never block systemd.
        telethon_enabled = os.getenv("TELEGRAM_USER_CLIENT_ENABLED", "false").lower() in {"1", "true", "yes"}
        if telethon_enabled:
            try:
                self.telegram_client = AgentTelegramClient(self.state_manager)
                await self.telegram_client.start()
                logger.info("Telegram client started")
            except Exception as e:
                logger.warning(f"Telegram client not started: {e}")
                self.telegram_client = None
        else:
            self.telegram_client = None
            logger.info("Telegram client disabled (TELEGRAM_USER_CLIENT_ENABLED=false)")

        # Initialize Telegram bot
        self.telegram_bot = TelegramBot(
            self.state_manager,
            on_task_callback=self.on_task_assigned,
            telegram_client=self.telegram_client
        )

        # Initialize proactivity loop (autonomous actions only)
        self.proactivity_loop = ProactivityLoop(
            self.state_manager,
            self.telegram_bot,
            self.telegram_client
        )

        # Initialize reactive loop (signal processing and task execution)
        self.reactive_loop = ReactiveLoop(
            self.state_manager,
            self.telegram_bot,
            self.proactivity_loop.executor  # Share action executor
        )

        # Link proactivity_loop to telegram_bot for quick acknowledgments
        self.telegram_bot.proactivity_loop = self.proactivity_loop

        # Start Telegram bot
        await self.telegram_bot.start()
        logger.info("Telegram bot started")

        # Add pause/resume commands
        from telegram import Update
        from telegram.ext import CommandHandler, ContextTypes

        async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id in self.telegram_bot.master_chat_ids:
                self.proactivity_loop.pause()
                await update.message.reply_text(
                    "⏸️ <b>Proactivity loop paused</b>\n\n"
                    "Use /resume to continue autonomous operation.",
                    parse_mode="HTML"
                )

        async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id in self.telegram_bot.master_chat_ids:
                self.proactivity_loop.resume()
                await update.message.reply_text(
                    "▶️ <b>Proactivity loop resumed</b>\n\n"
                    "Autonomous operation continuing...",
                    parse_mode="HTML"
                )

        self.telegram_bot.application.add_handler(CommandHandler("pause", pause_cmd))
        self.telegram_bot.application.add_handler(CommandHandler("resume", resume_cmd))

        # Send startup notification
        await self.telegram_bot.notify_master(
            "<b>🤖 Server-Agent Online</b>\n\n"
            "Dual-loop system initialized:\n"
            "✅ Proactive loop - autonomous actions\n"
            "✅ Reactive loop - instant task execution\n\n"
            "Use /status to check current state.\n"
            "Use /help for available commands."
        )

        # Start both loops in parallel
        self.running = True
        logger.info("Starting both proactive and reactive loops in parallel...")

        # Create tasks for both loops
        self.proactive_task = asyncio.create_task(
            self.proactivity_loop.run(),
            name="proactive_loop"
        )
        self.reactive_task = asyncio.create_task(
            self.reactive_loop.start(),
            name="reactive_loop"
        )

        # Run both loops concurrently
        logger.info("Both loops started - waiting for completion...")
        await asyncio.gather(self.proactive_task, self.reactive_task, return_exceptions=True)

    async def stop(self):
        """Stop all components gracefully."""
        logger.info("=== Stopping Server-Agent ===")
        self.running = False

        if self.health_server_task:
            self.health_server_task.cancel()
            self.health_server_task = None

        # Stop both loops
        if self.proactivity_loop:
            self.proactivity_loop.stop()

        if self.reactive_loop:
            self.reactive_loop.stop()

        # Cancel both tasks
        if self.proactive_task and not self.proactive_task.done():
            self.proactive_task.cancel()

        if self.reactive_task and not self.reactive_task.done():
            self.reactive_task.cancel()

        if self.telegram_bot and self.telegram_bot.application:
            try:
                await self.telegram_bot.notify_master(
                    "<b>🛑 Server-Agent Shutting Down</b>\n\n"
                    "Graceful shutdown initiated."
                )
            except Exception as e:
                logger.error(f"Error sending shutdown notification: {e}")
            await self.telegram_bot.stop()

        logger.info("All components stopped")

    async def on_task_assigned(self, task):
        """Handle task assignment from Telegram"""
        logger.info(f"Task assigned: {task['description']}")
        # The proactivity loop will pick this up in the next cycle


async def main():
    """Main entry point"""
    agent = ServerAgent()

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(agent.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await agent.stop()


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    # Run the agent
    asyncio.run(main())
