"""
Telegram User Client - For proactive agent communications
"""
import os
import logging
import time
from datetime import datetime
from typing import Optional, List
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class AgentTelegramClient:
    """Telegram client for proactive agent communications"""

    def __init__(self, state_manager, telegram_bot=None):
        # Telegram API credentials (get from https://my.telegram.org)
        self.api_id = int(os.getenv("TELEGRAM_API_ID"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone = os.getenv("AGENT_TELEGRAM_PHONE")

        self.state_manager = state_manager
        self.telegram_bot = telegram_bot  # Reference to bot for asking permissions

        # Create client
        self.client = TelegramClient(
            'agent_session',
            self.api_id,
            self.api_hash
        )

        # Master's chat ID for permission requests
        # Support multiple IDs but use first one for sending permission requests
        master_ids_str = os.getenv("MASTER_CHAT_IDS") or os.getenv("MASTER_MAX_TELEGRAM_CHAT_ID")
        self.master_chat_id = int(master_ids_str.split(",")[0].strip())

        # Approved contacts (loaded from state)
        self.approved_contacts = set()

    async def start(self):
        """Start the Telegram client"""
        logger.info("Starting Telegram user client...")

        await self.client.start(phone=self.phone)

        # Load approved contacts from state
        self._load_approved_contacts()

        logger.info(f"Telegram client started for {self.phone}")

    async def stop(self):
        """Stop the Telegram client"""
        await self.client.disconnect()
        logger.info("Telegram client stopped")

    def _load_approved_contacts(self):
        """Load approved contacts from state"""
        context = self.state_manager.load_context()
        self.approved_contacts = set(
            context.get("long_term_memory", {})
            .get("master_preferences", {})
            .get("approved_telegram_contacts", [])
        )
        logger.info(f"Loaded {len(self.approved_contacts)} approved contacts")

    def _save_approved_contact(self, username: str):
        """Save approved contact to state"""
        context = self.state_manager.load_context()

        if "approved_telegram_contacts" not in context["long_term_memory"]["master_preferences"]:
            context["long_term_memory"]["master_preferences"]["approved_telegram_contacts"] = []

        if username not in context["long_term_memory"]["master_preferences"]["approved_telegram_contacts"]:
            context["long_term_memory"]["master_preferences"]["approved_telegram_contacts"].append(username)
            self.state_manager.save_context(context)
            self.approved_contacts.add(username)
            logger.info(f"Saved approved contact: {username}")

    async def request_permission_to_message(self, username: str, reason: str) -> bool:
        """Ask Master for permission to message someone"""
        if username in self.approved_contacts:
            logger.info(f"Already approved: {username}")
            return True

        if not self.telegram_bot:
            logger.warning("No bot reference - cannot request permission")
            return False

        logger.info(f"Requesting permission to message {username}: {reason}")

        # Send permission request to Master via bot
        await self.telegram_bot.notify_master(
            f"<b>🤖 Permission Request</b>\n\n"
            f"<b>Contact:</b> @{username}\n"
            f"<b>Reason:</b> {reason}\n\n"
            f"Reply with:\n"
            f"✅ /approve {username}\n"
            f"❌ /deny {username}"
        )

        # Store pending permission request
        context = self.state_manager.load_context()
        if "pending_permissions" not in context["working_memory"]:
            context["working_memory"]["pending_permissions"] = {}
        context["working_memory"]["pending_permissions"][username] = {
            "reason": reason,
            "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.state_manager.save_context(context)

        return False  # Not approved yet

    async def send_message(self, username: str, message: str, require_approval: bool = True) -> bool:
        """Send message to a Telegram user/channel

        Args:
            username: Username or channel to message (without @)
            message: Message text
            require_approval: If True, ask Master for permission first

        Returns:
            True if message sent, False otherwise
        """
        try:
            # Check if approved
            if require_approval and username not in self.approved_contacts:
                logger.warning(f"Not approved to message {username}")
                return False

            # Send message
            await self.client.send_message(username, message)
            logger.info(f"Message sent to @{username}")

            # Record in state
            context = self.state_manager.load_context()
            if "sent_messages" not in context["working_memory"]:
                context["working_memory"]["sent_messages"] = []
            context["working_memory"]["sent_messages"].append({
                "to": username,
                "message": message[:100],  # Store first 100 chars
                "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            # Keep last 50 messages
            context["working_memory"]["sent_messages"] = context["working_memory"]["sent_messages"][-50:]
            self.state_manager.save_context(context)

            return True

        except Exception as e:
            logger.error(f"Error sending message to {username}: {e}")
            return False

    async def get_dialogs(self, limit: int = 10) -> List[dict]:
        """Get recent dialogs/chats"""
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=limit):
                dialogs.append({
                    "id": dialog.id,
                    "name": dialog.name,
                    "is_user": isinstance(dialog.entity, User),
                    "is_channel": isinstance(dialog.entity, Channel),
                    "is_group": isinstance(dialog.entity, Chat),
                    "username": getattr(dialog.entity, 'username', None)
                })
            return dialogs
        except Exception as e:
            logger.error(f"Error getting dialogs: {e}")
            return []

    def approve_contact(self, username: str):
        """Approve a contact (called when Master approves via bot command)"""
        self._save_approved_contact(username)

        # Remove from pending
        context = self.state_manager.load_context()
        if "pending_permissions" in context["working_memory"]:
            context["working_memory"]["pending_permissions"].pop(username, None)
            self.state_manager.save_context(context)

    def deny_contact(self, username: str):
        """Deny a contact (called when Master denies via bot command)"""
        # Remove from pending
        context = self.state_manager.load_context()
        if "pending_permissions" in context["working_memory"]:
            context["working_memory"]["pending_permissions"].pop(username, None)
            self.state_manager.save_context(context)
        logger.info(f"Denied contact: {username}")


# Standalone mode for testing
if __name__ == "__main__":
    import asyncio
    from state_manager import StateManager

    async def main():
        state_mgr = StateManager()
        client = AgentTelegramClient(state_mgr)

        await client.start()

        # Test: get dialogs
        dialogs = await client.get_dialogs()
        print(f"Recent dialogs: {len(dialogs)}")
        for d in dialogs[:5]:
            print(f"  - {d['name']} (@{d.get('username', 'N/A')})")

        await client.stop()

    asyncio.run(main())
