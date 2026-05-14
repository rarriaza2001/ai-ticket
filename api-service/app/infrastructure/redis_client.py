"""Redis client construction lives in `app.main` lifespan; this module documents timeouts."""

from redis.asyncio import Redis

__all__ = ["Redis"]
