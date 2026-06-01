"""Cache preflight checks before cold-cache / warm-cache benchmarks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import httpx

from phase4_benchmark.manifest import SeedManifest
from phase4_benchmark.redis_util import (
    flush_cache_keys_with_fallback,
    ping_redis,
    scan_cache_keys_with_fallback,
)


@dataclass
class PreflightResult:
    ok: bool
    cache_enabled_assumed: bool = True
    redis_reachable: bool = False
    redis_keys_after_warmup: int = 0
    status_miss_header: bool | None = None
    status_hit_header: bool | None = None
    similar_miss_header: bool | None = None
    similar_hit_header: bool | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def loud_warning(self) -> str | None:
        if self.ok:
            return None
        return (
            "CACHE PREFLIGHT FAILED: cache hits/misses were not observed. "
            "This benchmark run is invalid_for_cache_analysis. "
            "Rebuild api-service image, confirm CACHE_ENABLED=true in the container, "
            "and verify X-Cache-Hit headers plus ai-ticket:v1:* keys in Redis."
        )


def _parse_cache_hit(headers: httpx.Headers) -> bool | None:
    raw = headers.get("x-cache-hit")
    if raw is None:
        return None
    return raw in ("1", "true", "True")


async def run_cache_preflight(
    *,
    base_url: str,
    manifest: SeedManifest,
    redis_url: str,
    docker_redis_container: str = "docker-redis-1",
) -> PreflightResult:
    result = PreflightResult(ok=False)
    ticket_id = uuid.UUID(manifest.sample_ticket_id)

    result.redis_reachable = await ping_redis(redis_url)
    if not result.redis_reachable:
        result.warnings.append(
            f"Redis not reachable at {redis_url}; using docker exec on {docker_redis_container}."
        )

    deleted = await flush_cache_keys_with_fallback(
        redis_url, docker_container=docker_redis_container
    )
    print(f"Preflight: flushed {deleted} cache keys (ai-ticket:v1:*)")

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        path = f"/tickets/{ticket_id}/status"
        r1 = await client.get(path)
        r1.raise_for_status()
        result.status_miss_header = _parse_cache_hit(r1.headers)

        r2 = await client.get(path)
        r2.raise_for_status()
        result.status_hit_header = _parse_cache_hit(r2.headers)

        from phase4_benchmark.common import deterministic_vector

        body = {"embedding": deterministic_vector(manifest.similar_query_index), "limit": 10}
        s1 = await client.post("/tickets/similar", json=body)
        s1.raise_for_status()
        result.similar_miss_header = _parse_cache_hit(s1.headers)

        s2 = await client.post("/tickets/similar", json=body)
        s2.raise_for_status()
        result.similar_hit_header = _parse_cache_hit(s2.headers)

    keys = await scan_cache_keys_with_fallback(redis_url, docker_container=docker_redis_container)
    result.redis_keys_after_warmup = len(keys)
    if keys:
        print(f"Preflight: found {len(keys)} Redis keys (sample: {keys[0]})")
    else:
        result.errors.append("No ai-ticket:v1:* keys in Redis after warmup requests.")

    if result.status_miss_header is None and result.status_hit_header is None:
        result.errors.append("X-Cache-Hit header missing on status endpoint (cache middleware not active?).")

    if result.status_hit_header is not True:
        result.errors.append(
            f"Expected second status call hit (X-Cache-Hit=1), got {result.status_hit_header!r}"
        )

    if result.similar_hit_header is not True:
        result.warnings.append(
            f"Similarity second call not a cache hit (X-Cache-Hit={result.similar_hit_header!r}). "
            "Verify POST /tickets/similar cache-aside and stable query/filter hashes."
        )

    if result.redis_keys_after_warmup > 0 and "No ai-ticket:v1:* keys" in " ".join(result.errors):
        result.errors = [
            e
            for e in result.errors
            if not e.startswith("No ai-ticket:v1:* keys")
        ]

    result.ok = (
        result.status_hit_header is True
        and result.redis_keys_after_warmup > 0
        and len(result.errors) == 0
    )
    return result
