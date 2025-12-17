"""
Main entry point for the Server-Agent system
"""
import asyncio
import logging
import signal
from state_manager import StateManager
from telegram_bot import TelegramBot
from proactivity_loop import ProactivityLoop

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
    """Main server agent orchestrator"""

    def __init__(self):
        self.state_manager = StateManager()
        self.telegram_bot = None
        self.proactivity_loop = None
        self.running = False

    async def start(self):
        """Start all components"""
        logger.info("=== Starting Server-Agent ===")

        # Initialize components
        self.telegram_bot = TelegramBot(
            self.state_manager,
            on_task_callback=self.on_task_assigned
        )

        self.proactivity_loop = ProactivityLoop(
            self.state_manager,
            self.telegram_bot
        )

        # Start Telegram bot
        await self.telegram_bot.start()
        logger.info("Telegram bot started")

        # Add pause/resume commands
        from telegram import Update
        from telegram.ext import CommandHandler, ContextTypes

        async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id == self.telegram_bot.master_chat_id:
                self.proactivity_loop.pause()
                await update.message.reply_text(
                    "⏸️ <b>Proactivity loop paused</b>\n\n"
                    "Use /resume to continue autonomous operation.",
                    parse_mode="HTML"
                )

        async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id == self.telegram_bot.master_chat_id:
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
            "Autonomous operation initialized.\n"
            "Use /status to check current state.\n"
            "Use /help for available commands."
        )

        # Start proactivity loop
        self.running = True
        logger.info("Starting proactivity loop...")

        # Run both concurrently
        await self.proactivity_loop.run()

    async def stop(self):
        """Stop all components gracefully"""
        logger.info("=== Stopping Server-Agent ===")
        self.running = False

        if self.proactivity_loop:
            self.proactivity_loop.stop()

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
    import os
    os.makedirs("logs", exist_ok=True)

    # Run the agent
    asyncio.run(main())
