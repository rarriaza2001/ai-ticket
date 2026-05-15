"""Redis client factory for the worker (connectivity checks only in Phase 1)."""

import redis.asyncio as redis

from worker.core.config import Settings


def create_redis_client(settings: Settings) -> redis.Redis:
    return redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )
