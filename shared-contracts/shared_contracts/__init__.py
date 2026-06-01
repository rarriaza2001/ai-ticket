"""Shared contracts for api-service and ai-worker."""

from shared_contracts.ai import (
    AiPipelineObservability,
    AiTicketEventType,
    SuggestionStatus,
)
from shared_contracts.classification import ClassificationOutput, SuggestionMetadata
from shared_contracts.foundation import HealthResponse, ReadinessResponse
from shared_contracts.taxonomy import SupportTeam, TicketCategory, TicketPriority
from shared_contracts.cache_dtos import (
    CachedDraftSuggestion,
    CachedEventSummaryItem,
    CachedRoutingDecision,
    CachedSimilarityFilters,
    CachedSimilarityResult,
    CachedSimilarityResultItem,
    CachedTicketEventsSummary,
    CachedTicketStatus,
    CACHE_SCHEMA_VERSION,
)
from shared_contracts.cache_keys import (
    CACHE_NAMESPACE,
    SimilarityFilters,
    hash_embedding_query,
    hash_similarity_filters,
    similarity_key,
    ticket_draft_latest_key,
    ticket_events_key,
    ticket_routing_latest_key,
    ticket_status_key,
)
from shared_contracts.version import __version__

__all__ = [
    "__version__",
    "HealthResponse",
    "ReadinessResponse",
    "SuggestionStatus",
    "AiTicketEventType",
    "AiPipelineObservability",
    "TicketCategory",
    "SupportTeam",
    "TicketPriority",
    "ClassificationOutput",
    "SuggestionMetadata",
    "CACHE_NAMESPACE",
    "CACHE_SCHEMA_VERSION",
    "SimilarityFilters",
    "hash_embedding_query",
    "hash_similarity_filters",
    "similarity_key",
    "ticket_status_key",
    "ticket_routing_latest_key",
    "ticket_draft_latest_key",
    "ticket_events_key",
    "CachedTicketStatus",
    "CachedRoutingDecision",
    "CachedDraftSuggestion",
    "CachedEventSummaryItem",
    "CachedTicketEventsSummary",
    "CachedSimilarityResult",
    "CachedSimilarityResultItem",
    "CachedSimilarityFilters",
]
