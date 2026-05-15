"""Shared contracts for api-service and ai-worker (Phase 1: foundation schemas only)."""

from shared_contracts.foundation import HealthResponse, ReadinessResponse
from shared_contracts.version import __version__

__all__ = [
    "__version__",
    "HealthResponse",
    "ReadinessResponse",
]
