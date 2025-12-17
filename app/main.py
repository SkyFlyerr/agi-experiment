"""
Server Agent vNext - Main FastAPI Application
Based on AGI_ONE_PROMPT_SPEC.md

This is the core FastAPI application providing:
- Telegram webhook endpoint
- Reactive worker
- Proactive scheduler
- Admin/health endpoints
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db, close_db, get_db
from app.telegram import init_bot, shutdown_bot
from app.routes.webhook import router as webhook_router
from app.workers import ReactiveWorker
from app.workers.proactive import get_scheduler
from app.media.processor import get_media_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler"""
    logger.info("Starting Server Agent vNext...")

    # Initialize database
    db = init_db(settings.DATABASE_URL)
    await db.connect()
    logger.info("Database connected")

    # Initialize Telegram bot and webhook
    await init_bot()
    logger.info("Telegram bot initialized")

    # Start reactive worker
    reactive_worker = ReactiveWorker(poll_interval_ms=100)
    await reactive_worker.start()
    logger.info("Reactive worker started")

    # Start proactive scheduler
    proactive_scheduler = get_scheduler()
    await proactive_scheduler.start()
    logger.info("Proactive scheduler started")

    # Start media processor for async media processing
    media_processor = await get_media_processor()
    await media_processor.start()
    logger.info("Media processor started")

    logger.info("Server Agent vNext fully operational")

    yield

    # Shutdown
    logger.info("Shutting down Server Agent vNext...")

    # Stop media processor
    media_processor = await get_media_processor()
    await media_processor.stop()
    logger.info("Media processor stopped")

    # Stop proactive scheduler
    await proactive_scheduler.stop()
    logger.info("Proactive scheduler stopped")

    # Stop reactive worker
    await reactive_worker.stop()
    logger.info("Reactive worker stopped")

    # Shutdown Telegram bot
    await shutdown_bot()
    logger.info("Telegram bot shutdown")

    # Close database
    await close_db()
    logger.info("Database disconnected")

    logger.info("Server Agent vNext shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Server Agent vNext",
    description="AGI-style server agent with persistence-first architecture",
    version="2.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db = get_db()
        await db.execute("SELECT 1")

        return {
            "status": "healthy",
            "database": "connected",
            "telegram": "initialized"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        db = get_db()

        # Get message count
        message_count = await db.fetch_one(
            "SELECT COUNT(*) as count FROM chat_messages"
        )

        # Get token usage for today
        token_usage = await db.fetch_one(
            """
            SELECT
                scope,
                SUM(tokens_total) as total_tokens
            FROM token_ledger
            WHERE created_at >= CURRENT_DATE
            GROUP BY scope
            """
        )

        # Get job stats
        job_stats = await db.fetch_all(
            """
            SELECT
                status,
                COUNT(*) as count
            FROM reactive_jobs
            WHERE created_at >= CURRENT_DATE
            GROUP BY status
            """
        )

        return {
            "messages_total": message_count['count'] if message_count else 0,
            "token_usage_today": dict(token_usage) if token_usage else {},
            "jobs_today": {row['status']: row['count'] for row in job_stats}
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/test-telegram")
async def test_telegram_message(chat_id: str, text: str):
    """Send test message via Telegram (admin endpoint)"""
    try:
        from app.telegram import send_message

        message_id = await send_message(chat_id=chat_id, text=text)

        if message_id:
            return {"status": "success", "message_id": message_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")

    except Exception as e:
        logger.error(f"Failed to send test message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Server Agent vNext",
        "version": "2.0.0",
        "status": "operational",
        "philosophy": "Atmano moksartha jagat hitaya ca"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
