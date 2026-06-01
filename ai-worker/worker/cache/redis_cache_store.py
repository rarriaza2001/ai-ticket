"""Fail-open Redis cache wrapper (JSON + Pydantic validation)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TypeVar

import redis.asyncio as redis
import structlog
from pydantic import BaseModel, ValidationError

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    redis_get_errors: int = 0
    redis_set_errors: int = 0
    redis_delete_errors: int = 0
    validation_failures: int = 0
    redis_get_latency_ms_total: float = 0.0
    redis_set_latency_ms_total: float = 0.0
    redis_get_count: int = 0
    redis_set_count: int = 0

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class RedisCacheStore:
    def __init__(
        self,
        client: redis.Redis,
        *,
        enabled: bool = True,
        delete_invalid_on_read: bool = True,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self._client = client
        self._enabled = enabled
        self._delete_invalid_on_read = delete_invalid_on_read
        self.metrics = metrics or CacheMetrics()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def get_model(self, key: str, model_type: type[T]) -> T | None:
        if not self._enabled:
            self.metrics.record_miss()
            return None

        started = time.perf_counter()
        try:
            raw = await self._client.get(key)
            self.metrics.redis_get_count += 1
            self.metrics.redis_get_latency_ms_total += (time.perf_counter() - started) * 1000
        except Exception:
            self.metrics.redis_get_errors += 1
            self.metrics.record_miss()
            logger.warning("cache.redis_error", operation="get", key_family=_key_family(key))
            return None

        if raw is None:
            self.metrics.record_miss()
            logger.debug("cache.miss", key_family=_key_family(key))
            return None

        try:
            data = json.loads(raw)
            dto = model_type.model_validate(data)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            self.metrics.validation_failures += 1
            self.metrics.record_miss()
            logger.warning("cache.validation_failed", key_family=_key_family(key))
            if self._delete_invalid_on_read:
                await self.delete(key)
            return None

        self.metrics.record_hit()
        logger.debug("cache.hit", key_family=_key_family(key))
        return dto

    async def set_model(self, key: str, value: BaseModel, ttl_seconds: int) -> bool:
        if not self._enabled:
            return False

        payload = value.model_dump_json()
        started = time.perf_counter()
        try:
            await self._client.set(key, payload, ex=ttl_seconds)
            self.metrics.redis_set_count += 1
            self.metrics.redis_set_latency_ms_total += (time.perf_counter() - started) * 1000
            return True
        except Exception:
            self.metrics.redis_set_errors += 1
            logger.warning("cache.redis_error", operation="set", key_family=_key_family(key))
            return False

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._client.delete(*keys)
            self.metrics.invalidations += len(keys)
        except Exception:
            self.metrics.redis_delete_errors += 1
            logger.warning(
                "cache.redis_error",
                operation="delete",
                key_family=_key_family(keys[0]),
                key_count=len(keys),
            )


def _key_family(key: str) -> str:
    parts = key.split(":")
    if len(parts) >= 3 and parts[0] == "ai-ticket" and parts[1] == "v1":
        if parts[2] == "ticket" and len(parts) >= 5:
            return f"ticket:{parts[4]}"
        if parts[2] == "similarity":
            return "similarity"
    return "unknown"
