"""src/health_server.py

Minimal FastAPI server for healthchecks and lightweight metrics.

This is intended for VPS operations (systemd + monitoring).
Endpoints:
- GET /healthz: process liveness + basic state
- GET /metrics: simple JSON metrics extracted from StateManager
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app(state_manager) -> FastAPI:
    app = FastAPI(title="server-agent", version="0.1")

    @app.get("/healthz")
    def healthz():
        ctx = state_manager.load_context()
        return {
            "status": "ok",
            "cycle": ctx.get("current_session", {}).get("cycle_count"),
            "focus": ctx.get("current_session", {}).get("current_focus"),
        }

    @app.get("/metrics")
    def metrics():
        ctx = state_manager.load_context()
        return ctx.get("metrics", {})

    return app