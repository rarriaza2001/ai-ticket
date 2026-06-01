"""Redis helpers for benchmark flush/scan (URL or docker exec fallback)."""

from __future__ import annotations

import subprocess

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


async def ping_redis(redis_url: str) -> bool:
    if redis is None:
        return False
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()


async def flush_cache_keys(redis_url: str) -> int:
    if redis is None:
        return 0
    client = redis.from_url(redis_url, decode_responses=True)
    deleted = 0
    try:
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="ai-ticket:v1:*", count=500)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
    finally:
        await client.aclose()
    return deleted


async def scan_cache_keys(redis_url: str) -> list[str]:
    if redis is None:
        return []
    client = redis.from_url(redis_url, decode_responses=True)
    keys: list[str] = []
    try:
        cursor = 0
        while True:
            cursor, batch = await client.scan(cursor=cursor, match="ai-ticket:v1:*", count=500)
            keys.extend(batch)
            if cursor == 0:
                break
    finally:
        await client.aclose()
    return keys


def flush_cache_keys_docker(container: str = "docker-redis-1") -> int:
    scan = subprocess.run(
        ["docker", "exec", container, "redis-cli", "--scan", "--pattern", "ai-ticket:v1:*"],
        capture_output=True,
        text=True,
        check=False,
    )
    keys = [line.strip() for line in scan.stdout.splitlines() if line.strip()]
    if not keys:
        return 0
    deleted = 0
    for key in keys:
        proc = subprocess.run(
            ["docker", "exec", container, "redis-cli", "DEL", key],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            deleted += 1
    return deleted


def docker_container_running(container: str = "docker-redis-1") -> bool:
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip().lower() == "true"


def scan_cache_keys_docker(container: str = "docker-redis-1") -> list[str]:
    proc = subprocess.run(
        ["docker", "exec", container, "redis-cli", "--scan", "--pattern", "ai-ticket:v1:*"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


async def flush_cache_keys_with_fallback(redis_url: str, *, docker_container: str) -> int:
    """Flush benchmark keys via REDIS_URL and docker exec (compose Redis is often not on localhost)."""
    deleted = 0
    if await ping_redis(redis_url):
        deleted += await flush_cache_keys(redis_url)
    deleted += flush_cache_keys_docker(docker_container)
    return deleted


async def scan_cache_keys_with_fallback(redis_url: str, *, docker_container: str) -> list[str]:
    """Scan benchmark keys; prefer docker exec when it finds more keys than REDIS_URL."""
    url_keys: list[str] = []
    if await ping_redis(redis_url):
        url_keys = await scan_cache_keys(redis_url)
    docker_keys = scan_cache_keys_docker(docker_container)
    return docker_keys if len(docker_keys) >= len(url_keys) else url_keys
