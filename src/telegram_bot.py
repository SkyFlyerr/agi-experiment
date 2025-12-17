"""src/telegram_bot.py

Telegram Bot - Primary communication interface with humans.
"""

import asyncio
import logging
import os
from typing import Callable, Optional

from telegram_utils import send_long_message

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for agent communication"""

    def __init__(self, state_manager, on_task_callback: Optional[Callable] = None, telegram_client=None, proactivity_loop=None):
        self.token = os.getenv("TELEGRAM_API_TOKEN")
        self.bot_name = os.getenv("TELEGRAM_BOT_NAME")

        # Optional PostgreSQL chat history store (injected by ServerAgent)
        self.chat_db = None

        # Support multiple master chat IDs (comma-separated)
        master_ids_str = os.getenv("MASTER_CHAT_IDS") or os.getenv("MASTER_MAX_TELEGRAM_CHAT_ID")
        self.master_chat_ids = [int(x.strip()) for x in master_ids_str.split(",")]
        # Keep single ID for backwards compatibility (sending messages)
        self.master_chat_id = self.master_chat_ids[0]
        logger.info(f"Configured master chat IDs: {self.master_chat_ids}")

        self.state_manager = state_manager
        self.on_task_callback = on_task_callback
        self.telegram_client = telegram_client  # Reference to user client for approvals
        self.proactivity_loop = proactivity_loop  # Reference for quick acknowledgment
        self.application = None

        # Simple request/response channel for ask_master()
        self.pending_question: Optional[str] = None
        self._pending_future: Optional[asyncio.Future] = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 <b>Server-Agent Online</b>\n\n"
            "I am an autonomous AGI agent running on a server.\n\n"
            "<b>Available commands:</b>\n"
            "/status - Current state and focus\n"
            "/task <description> - Assign a task\n"
            "/pause - Pause autonomous operation\n"
            "/resume - Resume operation\n"
            "/report - Detailed activity report\n"
            "/skills - List learned skills\n"
            "/help - Show this message",
            parse_mode="HTML"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        summary = self.state_manager.get_session_summary()

        status_text = (
            f"📊 <b>Agent Status</b>\n\n"
            f"<b>Current Focus:</b> {summary['current_focus']}\n"
            f"<b>Certainty Level:</b> {summary['certainty']:.1%}\n"
            f"<b>Session Cycles:</b> {summary['cycles']}\n"
            f"<b>Active Tasks:</b> {summary['active_tasks']}\n"
            f"<b>Recent Actions:</b> {summary['recent_actions']}\n\n"
            f"<b>All-Time Metrics:</b>\n"
            f"Total Cycles: {summary['total_cycles_all_time']}\n"
            f"Autonomy Ratio: {summary['autonomous_ratio']:.1%}\n"
            f"Token Usage (24h): {summary['token_usage_24h']:,}\n\n"
            f"Started: {summary['started_at'][:19]}"
        )

        await update.message.reply_text(status_text, parse_mode="HTML")

    async def task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /task command"""
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a task description.\n"
                "Example: /task Learn about blockchain",
                parse_mode="HTML"
            )
            return

        task_description = " ".join(context.args)

        task = {
            "id": f"task_{update.message.message_id}",
            "description": task_description,
            "assigned_by": update.effective_user.id,
            "priority": "high" if update.effective_user.id in self.master_chat_ids else "normal"
        }

        self.state_manager.add_task(task)

        # Add signal to notify proactivity loop
        self.state_manager.add_signal("task_assigned", {
            "task_id": task["id"],
            "description": task_description,
            "priority": task["priority"],
            "user_id": update.effective_user.id
        })

        await update.message.reply_text(
            f"✅ <b>Task Added</b>\n\n"
            f"Description: {task_description}\n"
            f"Priority: {task['priority']}\n\n"
            f"I will work on this immediately.",
            parse_mode="HTML"
        )

        # Trigger task callback if available
        if self.on_task_callback:
            await self.on_task_callback(task)

    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        ctx = self.state_manager.load_context()

        recent_actions = ctx["working_memory"]["recent_actions"][-5:]

        report = "📋 <b>Activity Report</b>\n\n"

        if recent_actions:
            report += "<b>Recent Actions:</b>\n"
            for i, action in enumerate(recent_actions, 1):
                action_type = action["action"].get("action", "unknown")
                timestamp = action["timestamp"][:19]
                report += f"{i}. {action_type} ({timestamp})\n"
        else:
            report += "No recent actions.\n"

        report += f"\n<b>Skills Learned:</b> {len(ctx['long_term_memory']['skills_learned'])}\n"

        await update.message.reply_text(report, parse_mode="HTML")

    async def skills_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /skills command"""
        ctx = self.state_manager.load_context()
        skills = ctx["long_term_memory"]["skills_learned"]

        if not skills:
            await update.message.reply_text(
                "📚 No skills learned yet.\n\n"
                "I am ready to learn! Assign me tasks to develop new capabilities.",
                parse_mode="HTML"
            )
            return

        skills_text = "📚 <b>Learned Skills</b>\n\n"
        for skill in skills:
            skills_text += f"• {skill['name']} (learned {skill['learned_at'][:10]})\n"

        await update.message.reply_text(skills_text, parse_mode="HTML")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await self.start_command(update, context)

    async def approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approve command - approve agent to message someone"""
        if update.effective_user.id not in self.master_chat_ids:
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a username.\n"
                "Example: /approve username",
                parse_mode="HTML"
            )
            return

        username = context.args[0].lstrip('@')

        # Approve in client
        if self.telegram_client:
            self.telegram_client.approve_contact(username)
            await update.message.reply_text(
                f"✅ <b>Approved</b>\n\n"
                f"Agent can now message @{username}",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ Telegram client not available",
                parse_mode="HTML"
            )

    async def deny_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /deny command - deny agent from messaging someone"""
        if update.effective_user.id not in self.master_chat_ids:
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a username.\n"
                "Example: /deny username",
                parse_mode="HTML"
            )
            return

        username = context.args[0].lstrip('@')

        # Deny in client
        if self.telegram_client:
            self.telegram_client.deny_contact(username)
            await update.message.reply_text(
                f"❌ <b>Denied</b>\n\n"
                f"Agent will not message @{username}",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ Telegram client not available",
                parse_mode="HTML"
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (text + attachments).

        Requirements:
        - Messages with attachments (photo/document) must be captured.
        - Text can be in caption.
        """
        msg = update.message
        if not msg:
            return

        message_text = msg.text or msg.caption or ""

        # Log all incoming messages to capture chat IDs
        logger.info(
            f"Message from user {update.effective_user.id} (@{update.effective_user.username}): "
            f"{message_text[:50] if message_text else 'No text'}..."
        )

        # Only respond to Master for now
        if update.effective_user.id not in self.master_chat_ids:
            logger.warning(
                f"Message from non-master user {update.effective_user.id} (@{update.effective_user.username}) - ignoring"
            )
            return

        # Collect attachments (download to local disk for now).
        attachments = []
        incoming_dir = os.path.join("data", "incoming")
        os.makedirs(incoming_dir, exist_ok=True)

        try:
            if msg.photo:
                photo = msg.photo[-1]
                tg_file = await photo.get_file()
                local_path = os.path.join(incoming_dir, f"photo_{msg.message_id}_{photo.file_unique_id}.jpg")
                await tg_file.download_to_drive(custom_path=local_path)
                attachments.append(
                    {
                        "type": "photo",
                        "local_path": local_path,
                        "file_id": photo.file_id,
                        "file_unique_id": photo.file_unique_id,
                    }
                )

            if msg.document:
                doc = msg.document
                tg_file = await doc.get_file()
                safe_name = doc.file_name or f"document_{msg.message_id}_{doc.file_unique_id}"
                local_path = os.path.join(incoming_dir, safe_name)
                await tg_file.download_to_drive(custom_path=local_path)
                attachments.append(
                    {
                        "type": "document",
                        "local_path": local_path,
                        "file_id": doc.file_id,
                        "file_unique_id": doc.file_unique_id,
                        "file_name": doc.file_name,
                        "mime_type": doc.mime_type,
                    }
                )

        except Exception as e:
            logger.error(f"Attachment download failed: {e}", exc_info=True)

        # Persist incoming user message into DB (optional)
        if self.chat_db and update.effective_chat:
            try:
                from chat_db import ChatMessage

                self.chat_db.log_message(
                    ChatMessage(
                        role="user",
                        chat_id=int(update.effective_chat.id),
                        message_id=int(msg.message_id) if msg.message_id else None,
                        user_id=int(update.effective_user.id) if update.effective_user else None,
                        text=message_text or "",
                        attachments={"items": attachments} if attachments else None,
                    )
                )
            except Exception as e:
                logger.warning(f"ChatDB user log failed: {e}")

        # If there's a pending question, treat this as the answer.
        if self.pending_question:
            answer_text = message_text

            # Resolve waiting future (if any)
            if self._pending_future and not self._pending_future.done():
                self._pending_future.set_result(answer_text)

            self.state_manager.add_signal(
                "guidance_received",
                {
                    "question": self.pending_question,
                    "answer": answer_text,
                    "user_id": update.effective_user.id,
                    "attachments": attachments,
                },
            )

            await msg.reply_text(
                "✅ Thank you for your guidance. Proceeding with your input.",
                parse_mode="HTML",
            )

            self.pending_question = None
            self._pending_future = None
            return

        # Regular conversation/task message -> add signal.
        self.state_manager.add_signal(
            "user_message",
            {
                "message": message_text,
                "user_id": update.effective_user.id,
                "message_id": msg.message_id,
                "chat_id": update.effective_chat.id,
                "attachments": attachments,
            },
        )

        # React with 👀 emoji
        try:
            await msg.set_reaction("👀")
        except Exception as e:
            logger.warning(f"Could not set reaction: {e}")

        # Send quick acknowledgment if proactivity_loop is available
        if self.proactivity_loop and message_text:
            try:
                await self.proactivity_loop.quick_acknowledge_message(
                    message=message_text,
                    chat_id=update.effective_chat.id,
                )
            except Exception as e:
                logger.error(f"Quick acknowledgment failed: {e}")

    async def ask_master(self, question: str) -> str:
        """Ask Master a question and wait for response.

        This is used by the agent loop when certainty is below threshold.
        """
        self.pending_question = question
        self._pending_future = asyncio.get_running_loop().create_future()

        # Send question to Master
        await send_long_message(
            bot=self.application.bot,
            chat_id=self.master_chat_id,
            text=(
                "🤔 <b>Question from Agent</b>\n\n"
                f"{question}\n\n"
                "Please reply with your guidance."
            ),
            parse_mode="HTML",
        )

        try:
            # Conservative timeout to avoid blocking the whole loop forever.
            answer = await asyncio.wait_for(self._pending_future, timeout=30 * 60)
            return str(answer)
        except asyncio.TimeoutError:
            # Keep pending_question cleared to avoid misrouting future messages.
            self.pending_question = None
            self._pending_future = None
            return "(timeout waiting for Master guidance)"

    async def notify_master(self, message: str):
        """Send notification to Master"""
        await send_long_message(
            bot=self.application.bot,
            chat_id=self.master_chat_id,
            text=f"ℹ️ {message}",
            parse_mode="HTML",
        )

    def setup_handlers(self):
        """Setup command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("task", self.task_command))
        self.application.add_handler(CommandHandler("report", self.report_command))
        self.application.add_handler(CommandHandler("skills", self.skills_command))

        # Permission management commands
        self.application.add_handler(CommandHandler("approve", self.approve_command))
        self.application.add_handler(CommandHandler("deny", self.deny_command))

        # Handle regular messages (text + attachments)
        self.application.add_handler(
            MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message)
        )

    async def start(self):
        """Start the bot"""
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

        logger.info(f"Starting Telegram bot: @{self.bot_name}")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self):
        """Stop the bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")


# Standalone mode for testing
if __name__ == "__main__":
    import asyncio
    from state_manager import StateManager

    async def main():
        state_mgr = StateManager()
        bot = TelegramBot(state_mgr)
        await bot.start()

        try:
            # Keep running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await bot.stop()

    asyncio.run(main())
