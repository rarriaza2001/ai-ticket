from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_tracing
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    configure_tracing(enabled=False)

    app.state.db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout_seconds,
    )
    app.state.redis = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )
    logger.info("startup.complete", service=settings.service_name)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.db_pool.close()
        logger.info("shutdown.complete", service=settings.service_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Ticket Triage API",
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "Phase 1 scaffolding: authoritative data will live in Postgres; "
            "Redis is ephemeral cache only. Ticket routes return 501 until Phase 2."
        ),
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
