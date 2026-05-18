from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.embedding import EMBEDDING_DIMENSION


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    subject: str
    body: str
    external_id: str | None = None
    customer_email: str | None = None
    priority: str | None = None


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str | None
    source: str
    subject: str
    body: str
    customer_email: str | None
    status: str
    priority: str | None
    created_at: datetime
    updated_at: datetime


class TicketStatusResponse(BaseModel):
    ticket_id: uuid.UUID
    status: str


class TicketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    event_type: str
    payload: dict[str, Any] | None
    created_at: datetime


class RoutingDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    route_to: str
    decision_type: str
    confidence: Decimal | None
    reason: str | None
    decided_by: str
    created_at: datetime


class SimilarTicketsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding: list[float] = Field(
        description="Pre-computed query vector (no embedding generation in API)."
    )
    limit: int = Field(default=10, ge=1, le=100)
    exclude_ticket_id: uuid.UUID | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None

    @field_validator("embedding")
    @classmethod
    def validate_embedding_length(cls, value: list[float]) -> list[float]:
        if len(value) != EMBEDDING_DIMENSION:
            msg = f"embedding must have length {EMBEDDING_DIMENSION}, got {len(value)}"
            raise ValueError(msg)
        return value


class SimilarTicketResult(BaseModel):
    ticket_id: uuid.UUID
    embedding_id: uuid.UUID
    subject: str
    source: str
    status: str
    distance: float


class SimilarTicketsResponse(BaseModel):
    results: list[SimilarTicketResult]


class StoreTestEmbeddingRequest(BaseModel):
    """Local test/scaffolding only — accepts a provided vector, does not generate one."""

    model_config = ConfigDict(extra="forbid")

    embedding: list[float]
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    source_text_hash: str = "test-hash"

    @field_validator("embedding")
    @classmethod
    def validate_embedding_length(cls, value: list[float]) -> list[float]:
        if len(value) != EMBEDDING_DIMENSION:
            msg = f"embedding must have length {EMBEDDING_DIMENSION}, got {len(value)}"
            raise ValueError(msg)
        return value


class TicketEmbeddingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    embedding_model: str
    embedding_dimension: int
    source_text_hash: str
    is_active: bool
    embedded_at: datetime
    created_at: datetime
