from fastapi import APIRouter
from shared_contracts import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: process is running (no dependency checks)."""
    return HealthResponse()
