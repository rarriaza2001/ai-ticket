from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import DbPool, RedisClient

router = APIRouter(tags=["readiness"])


class ReadinessResponse(BaseModel):
    """Readiness: Postgres is required; Redis failure marks degraded mode only (HTTP 200)."""

    postgres: bool = Field(description="Authoritative store reachable.")
    redis: bool = Field(description="Ephemeral cache reachable.")
    degraded: bool = Field(description="True when Postgres is up but Redis is not.")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(pool: DbPool, redis_client: RedisClient) -> ReadinessResponse:
    postgres_ok = False
    redis_ok = False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        postgres_ok = True
    except Exception:
        postgres_ok = False

    try:
        pong = await redis_client.ping()
        redis_ok = bool(pong)
    except Exception:
        redis_ok = False

    if not postgres_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"postgres": False, "redis": redis_ok, "degraded": False},
        )

    return ReadinessResponse(
        postgres=True,
        redis=redis_ok,
        degraded=not redis_ok,
    )
