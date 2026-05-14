from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shared_contracts.enums import TicketStatus


class Ticket(BaseModel):
    """Authoritative ticket shape exchanged over HTTP and persisted in Postgres (Phase 2)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: TicketStatus
    subject: str
    body: str
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(default=1, description="Optimistic concurrency / audit pointer (Phase 2).")


class TicketCreateRequest(BaseModel):
    """Request body for ticket intake; duplicates resolved via Idempotency-Key (Phase 2)."""

    subject: str = Field(..., max_length=512)
    body: str = Field(..., max_length=65535)


class TicketEmbedding(BaseModel):
    """Embedding row associated with a ticket; vector stored in pgvector (Phase 2).

    Assumption: Postgres column uses `vector(dim)` from the pgvector extension alongside
    `ticket_id` FK and model metadata. The `vector` field is worker-internal and omitted from JSON.
    """

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    model_name: str = Field(default="placeholder", description="Embedding model id (Phase 2).")
    dimensions: int = Field(default=0, description="Vector dimension when materialized.")
    vector: bytes | None = Field(
        default=None,
        exclude=True,
        description="Serialized float vector or opaque blob for worker use only.",
    )
    created_at: datetime


class TicketSuggestion(BaseModel):
    """Suggested reply or next action for a ticket (AI output; auditable in Phase 2)."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    suggestion: str = Field(default="", description="Primary suggestion payload (Phase 2).")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    correlation_id: UUID | None = None
    created_at: datetime


class RoutingDecision(BaseModel):
    """Routing outcome produced by the worker (Phase 2)."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    target_queue: str = Field(default="", description="Logical queue or team id (Phase 2).")
    rationale: str = Field(default="", description="Human-readable rationale (Phase 2).")
    model_run_id: str | None = Field(default=None, description="Opaque model invocation id.")
    decided_at: datetime


class TicketEvent(BaseModel):
    """Append-only style audit event (stored in Postgres in Phase 2)."""

    model_config = ConfigDict(from_attributes=True)

    event_type: str
    ticket_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    source: Literal["api", "worker"]
    dedupe_key: str | None = Field(
        default=None,
        description="Idempotency key for deduplicating mirrored events.",
    )


class SimilarTicketSnapshot(BaseModel):
    """Point-in-time similar-ticket retrieval result (Phase 2)."""

    model_config = ConfigDict(from_attributes=True)

    anchor_ticket_id: UUID
    similar_ticket_ids: list[UUID] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list, description="Similarity scores aligned to ids.")
    computed_at: datetime
