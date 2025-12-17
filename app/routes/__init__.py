"""FastAPI routes package."""

from app.routes.webhook import router as webhook_router

__all__ = ["webhook_router"]
