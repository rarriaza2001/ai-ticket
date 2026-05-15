from fastapi import APIRouter
from shared_contracts import ReadinessResponse

from app.deps import ReadinessSvc

router = APIRouter(tags=["readiness"])


@router.get("/ready", response_model=ReadinessResponse)
async def ready(service: ReadinessSvc) -> ReadinessResponse:
    """Readiness: Postgres required; Redis failure is degraded only (HTTP 200)."""
    return await service.evaluate()
