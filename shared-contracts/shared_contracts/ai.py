"""Shared AI DTOs and enums for api-service and ai-worker (Phase 3 scaffolding)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SuggestionStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class AiTicketEventType(StrEnum):
    AI_PROCESSING_STARTED = "ai_processing_started"
    CLASSIFICATION_COMPLETED = "classification_completed"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    DRAFT_SUGGESTION_STORED = "draft_suggestion_stored"
    AI_PROCESSING_COMPLETED = "ai_processing_completed"
    AI_PROCESSING_FAILED = "ai_processing_failed"


class AiPipelineObservability(BaseModel):
    """Structured metadata for logs and audit event payloads (no full ticket/draft text)."""

    model_config = ConfigDict(extra="forbid")

    embedding_latency_ms: float | None = None
    classification_latency_ms: float | None = None
    retrieval_latency_ms: float | None = None
    suggestion_latency_ms: float | None = None
    total_latency_ms: float | None = None
    provider_name: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    similarity_match_count: int | None = None
    top_similarity_distance: float | None = None
    confidence: float | None = None
    retry_count: int = 0
    fallback_reason: str | None = None
    requires_human_review: bool | None = None
    failure_reason: str | None = None
