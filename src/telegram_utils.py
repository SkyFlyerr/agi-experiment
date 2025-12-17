"""src/telegram_utils.py

Telegram helper utilities.

Key requirements:
- Telegram enforces 4096 char limit per message.
- We should split long outputs at intelligent breakpoints.

We keep implementation deliberately simple and safe for Telegram HTML parse_mode.
"""

from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional


TELEGRAM_MAX_LEN = 4096
TELEGRAM_SAFE_LEN = 4000  # leave headroom for continuation markers


def _split_text_intelligently(text: str, max_len: int) -> List[str]:
    if len(text) <= max_len:
        return [text]

    parts: List[str] = []
    remaining = text

    breakpoints: List[str] = ["\n\n", "\n", ". ", "! ", "? ", " "]

    while len(remaining) > max_len:
        window = remaining[:max_len]

        cut = -1
        for bp in breakpoints:
            idx = window.rfind(bp)
            if idx > cut:
                cut = idx

        if cut <= 0:
            # Worst case: hard cut
            cut = max_len

        # If breakpoint is multi-char, include it in the first part
        chunk = remaining[: cut + 1] if cut < len(remaining) and remaining[cut : cut + 1] in {"\n", " "} else remaining[:cut]
        chunk = chunk.rstrip()
        if chunk:
            parts.append(chunk)

        remaining = remaining[len(chunk) :].lstrip()

    if remaining:
        parts.append(remaining)

    return parts


async def send_long_message(
    *,
    bot,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "HTML",
    sleep_s: float = 0.4,
) -> None:
    """Send a message, auto-splitting if it exceeds Telegram limits."""

    if not text:
        return

    if len(text) <= TELEGRAM_MAX_LEN:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return

    parts = _split_text_intelligently(text, TELEGRAM_SAFE_LEN)

    for i, part in enumerate(parts):
        prefix = "(continued) " if i > 0 else ""
        suffix = " ... (continued)" if i < len(parts) - 1 else ""
        await bot.send_message(chat_id=chat_id, text=f"{prefix}{part}{suffix}", parse_mode=parse_mode)
        if i < len(parts) - 1:
            await asyncio.sleep(sleep_s)
