"""Voice Assistant FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .db.session import init_db
from .limiter import limiter
from .routes import health, orders, voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("voice_assistant.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Initialize the database on startup. Don't hard-fail if Postgres isn't up:
    # token issuance and health checks still work without it, and the operator
    # gets a clear log line pointing at docker-compose.
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001 - startup should not crash the app
        logger.warning(
            "Database initialization failed (%s). Order/policy APIs will be "
            "unavailable until Postgres is reachable. Start it with "
            "`docker compose up -d postgres`.",
            exc,
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Voice Assistant Backend",
        version="0.1.0",
        description="Voice Assistant: LiveKit token issuance, session lifecycle, and order APIs.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate-limiting: attach the slowapi state and its 429 handler.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health.router)
    app.include_router(voice.router)
    app.include_router(orders.router)
    return app


app = create_app()
