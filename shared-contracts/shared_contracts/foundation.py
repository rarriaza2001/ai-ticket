"""Neutral HTTP/ops schemas shared by api-service and ai-worker (Phase 1 foundation only)."""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Liveness payload for `GET /health`."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="ok", description="Process is running.")


class ReadinessResponse(BaseModel):
    """Readiness payload for `GET /ready` (dependency probes)."""

    model_config = ConfigDict(extra="forbid")

    postgres: bool = Field(description="Authoritative store reachable.")
    redis: bool = Field(description="Ephemeral cache reachable.")
    degraded: bool = Field(
        description="True when Postgres is up but Redis is not (non-authoritative degradation).",
    )
