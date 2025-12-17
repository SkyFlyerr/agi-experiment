"""Telegram webhook handler for FastAPI."""

import logging
from typing import Dict, Any

from fastapi import Request, Response, HTTPException, Header
from aiogram.types import Update

from app.telegram.ingestion import ingest_telegram_update
from app.config import settings

logger = logging.getLogger(__name__)


async def handle_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
) -> Response:
    """
    Handle incoming Telegram webhook requests.

    This endpoint:
    1. Verifies webhook secret (if configured)
    2. Parses Telegram Update object
    3. Returns 200 OK immediately (< 100ms)
    4. Processes update asynchronously

    Args:
        request: FastAPI request object
        x_telegram_bot_api_secret_token: Telegram secret token header

    Returns:
        200 OK response

    Raises:
        HTTPException: If verification fails or invalid payload
    """
    try:
        # Verify webhook secret if configured
        if settings.TELEGRAM_WEBHOOK_SECRET:
            if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
                logger.warning(
                    f"Webhook secret mismatch: "
                    f"expected={settings.TELEGRAM_WEBHOOK_SECRET}, "
                    f"got={x_telegram_bot_api_secret_token}"
                )
                raise HTTPException(status_code=403, detail="Invalid webhook secret")

        # Parse request body
        body: Dict[str, Any] = await request.json()

        # Log webhook reception (but not full payload for privacy)
        logger.info(
            f"Webhook received: update_id={body.get('update_id')}, "
            f"has_message={bool(body.get('message'))}, "
            f"has_callback={bool(body.get('callback_query'))}"
        )

        # Parse Update object
        try:
            update = Update(**body)
        except Exception as e:
            logger.error(f"Failed to parse Update object: {e}")
            raise HTTPException(status_code=400, detail="Invalid update format")

        # Return 200 OK immediately (Telegram requires < 100ms response)
        # Process update asynchronously in background
        import asyncio
        asyncio.create_task(ingest_telegram_update(update))

        return Response(status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        # Still return 200 to prevent Telegram from retrying
        return Response(status_code=200)


__all__ = ["handle_telegram_webhook"]
