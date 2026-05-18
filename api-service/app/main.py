from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_tracing
from app.db.session import create_async_engine_from_settings, create_session_factory
from app.infrastructure.redis import create_redis_client
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    configure_tracing(enabled=False)

    engine = create_async_engine_from_settings(
        url=settings.sqlalchemy_async_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory: async_sessionmaker[AsyncSession] = session_factory
    app.state.redis = create_redis_client(settings)

    logger.info("startup.complete", service=settings.service_name)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        eng: AsyncEngine = app.state.engine
        await eng.dispose()
        logger.info("shutdown.complete", service=settings.service_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Ticket Triage API",
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "Phase 2 persistence: ticket intake, embeddings (pgvector), routing decisions, "
            "and audit events. Postgres is authoritative; Redis is non-authoritative. "
            "No AI generation, queue processing, or caching in this phase."
        ),
    )
    register_exception_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
