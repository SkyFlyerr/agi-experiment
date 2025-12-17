"""Webhook routes for Telegram and other integrations."""

import logging
from fastapi import APIRouter, Request, Response, Header

from app.telegram.webhook import handle_telegram_webhook

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
) -> Response:
    """
    Telegram webhook endpoint.

    This endpoint receives updates from Telegram Bot API and processes them
    asynchronously. Returns 200 OK immediately to satisfy Telegram's
    timeout requirements (< 100ms).

    Args:
        request: FastAPI request object
        x_telegram_bot_api_secret_token: Telegram secret token header

    Returns:
        200 OK response
    """
    return await handle_telegram_webhook(request, x_telegram_bot_api_secret_token)


@router.get("/health")
async def webhook_health():
    """
    Webhook health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "webhook",
        "endpoints": ["telegram"]
    }


__all__ = ["router"]
