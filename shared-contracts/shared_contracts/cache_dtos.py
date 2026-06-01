"""JSON cache value DTOs (validated on read/write)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared_contracts.cache_keys import SimilarityFilters

CACHE_SCHEMA_VERSION: Literal[1] = 1

# Ticket status values used across api-service and ai-worker persistence.
_VALID_TICKET_STATUSES = frozenset(
    {
        "received",
        "pending_embedding",
        "embedded",
        "routing_pending",
        "routed",
        "failed",
    }
)

_VALID_SUGGESTION_STATUSES = frozenset({"pending_review", "superseded", "failed"})

_VALID_EVENT_TYPES = frozenset(
    {
        "ticket_received",
        "ticket_status_changed",
        "embedding_stored",
        "routing_decision_stored",
        "ticket_failed",
        "ai_processing_started",
        "classification_completed",
        "retrieval_completed",
        "draft_suggestion_stored",
        "ai_processing_completed",
        "ai_processing_failed",
    }
)


class CacheDtoBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = CACHE_SCHEMA_VERSION


class CachedTicketStatus(CacheDtoBase):
    ticket_id: uuid.UUID
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _VALID_TICKET_STATUSES:
            msg = f"invalid ticket status: {value}"
            raise ValueError(msg)
        return value


class CachedRoutingDecision(CacheDtoBase):
    id: uuid.UUID
    ticket_id: uuid.UUID
    route_to: str
    decision_type: str
    confidence: Decimal | None
    reason: str | None
    decided_by: str
    created_at: datetime
    human_review_required: bool = False


class CachedDraftSuggestion(CacheDtoBase):
    id: uuid.UUID
    ticket_id: uuid.UUID
    draft_text: str
    provider_name: str
    model_name: str
    prompt_version: str
    status: str
    confidence: Decimal | None
    requires_human_review: bool
    created_at: datetime

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _VALID_SUGGESTION_STATUSES:
            msg = f"invalid suggestion status: {value}"
            raise ValueError(msg)
        return value


class CachedEventSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    event_type: str
    created_at: datetime

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value not in _VALID_EVENT_TYPES:
            msg = f"invalid event type: {value}"
            raise ValueError(msg)
        return value


class CachedTicketEventsSummary(CacheDtoBase):
    ticket_id: uuid.UUID
    events: list[CachedEventSummaryItem] = Field(default_factory=list, max_length=50)


class CachedSimilarityResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: uuid.UUID
    embedding_id: uuid.UUID
    subject: str
    source: str
    status: str
    distance: float

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _VALID_TICKET_STATUSES:
            msg = f"invalid ticket status: {value}"
            raise ValueError(msg)
        return value


class CachedSimilarityFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    exclude_ticket_id: uuid.UUID | None
    embedding_model: str
    embedding_dimension: int
    max_ticket_age_days: int | None = None

    @classmethod
    def from_similarity_filters(cls, filters: SimilarityFilters) -> CachedSimilarityFilters:
        return cls(
            limit=filters.limit,
            exclude_ticket_id=filters.exclude_ticket_id,
            embedding_model=filters.embedding_model,
            embedding_dimension=filters.embedding_dimension,
            max_ticket_age_days=filters.max_ticket_age_days,
        )


class CachedSimilarityResult(CacheDtoBase):
    embedding_model: str
    embedding_dimension: int
    query_hash: str
    filters_hash: str
    filters: CachedSimilarityFilters
    results: list[CachedSimilarityResultItem]
    cached_at: datetime
