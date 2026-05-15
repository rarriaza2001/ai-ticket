import redis.asyncio as redis
from shared_contracts import ReadinessResponse

from app.core.errors import PostgresUnavailable
from app.repositories.health_repository import HealthRepository


class ReadinessService:
    """Compose dependency probes for `/ready` (no FastAPI imports)."""

    def __init__(self, health_repository: HealthRepository, redis_client: redis.Redis) -> None:
        self._repo = health_repository
        self._redis = redis_client

    async def _probe_redis(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def evaluate(self) -> ReadinessResponse:
        try:
            await self._repo.ping_postgres()
        except Exception as exc:
            redis_ok = await self._probe_redis()
            raise PostgresUnavailable(redis_ok=redis_ok) from exc

        redis_ok = await self._probe_redis()

        return ReadinessResponse(
            postgres=True,
            redis=redis_ok,
            degraded=not redis_ok,
        )
