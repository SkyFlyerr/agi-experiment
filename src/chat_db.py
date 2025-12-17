"""src/chat_db.py

PostgreSQL-backed chat history storage.

Purpose:
- Persist all Telegram dialog turns (user/bot) for long-term coherence.
- Provide a small recent-history slice to include in Claude prompts.

Design goals:
- Optional: if DATABASE_URL is not set or DB unavailable, functions become no-ops.
- Safe: never raise to caller by default; log and continue.

Env:
- DATABASE_URL: e.g. postgresql://user:pass@127.0.0.1:5432/server_agent
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover
    psycopg2 = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str  # 'user' | 'assistant' | 'system'
    chat_id: int
    message_id: Optional[int]
    user_id: Optional[int]
    text: str
    attachments: Optional[Dict[str, Any]]


class ChatDB:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")

    def enabled(self) -> bool:
        return bool(self.database_url) and psycopg2 is not None

    def _connect(self):
        assert self.database_url
        return psycopg2.connect(self.database_url, connect_timeout=3)

    def ensure_schema(self) -> None:
        if not self.enabled():
            return

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS chat_messages (
                          id BIGSERIAL PRIMARY KEY,
                          chat_id BIGINT NOT NULL,
                          message_id BIGINT,
                          user_id BIGINT,
                          role TEXT NOT NULL,
                          text TEXT NOT NULL,
                          attachments JSONB,
                          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );

                        CREATE INDEX IF NOT EXISTS chat_messages_chat_id_created_at_idx
                          ON chat_messages (chat_id, created_at DESC);
                        """
                    )
            logger.info("ChatDB: schema ensured")
        except Exception as e:
            logger.error("ChatDB.ensure_schema failed: %s", e, exc_info=True)

    def log_message(self, msg: ChatMessage) -> None:
        if not self.enabled():
            return

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_messages (chat_id, message_id, user_id, role, text, attachments)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            int(msg.chat_id),
                            int(msg.message_id) if msg.message_id is not None else None,
                            int(msg.user_id) if msg.user_id is not None else None,
                            msg.role,
                            msg.text,
                            json.dumps(msg.attachments) if msg.attachments is not None else None,
                        ),
                    )
        except Exception as e:
            logger.error("ChatDB.log_message failed: %s", e, exc_info=True)

    def fetch_recent(self, chat_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Return most recent messages in chronological order."""
        if not self.enabled():
            return []

        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT role, text, created_at
                        FROM chat_messages
                        WHERE chat_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (int(chat_id), int(limit)),
                    )
                    rows = cur.fetchall() or []

            # rows are newest-first, reverse for chronological
            return list(reversed(rows))
        except Exception as e:
            logger.error("ChatDB.fetch_recent failed: %s", e, exc_info=True)
            return []
