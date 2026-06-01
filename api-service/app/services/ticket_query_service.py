from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared_contracts.cache_dtos import (
    CachedDraftSuggestion,
    CachedEventSummaryItem,
    CachedRoutingDecision,
    CachedSimilarityFilters,
    CachedSimilarityResult,
    CachedSimilarityResultItem,
    CachedTicketEventsSummary,
    CachedTicketStatus,
)
from shared_contracts.cache_keys import (
    SimilarityFilters,
    hash_embedding_query,
    hash_similarity_filters,
    similarity_key,
    ticket_draft_latest_key,
    ticket_events_key,
    ticket_routing_latest_key,
    ticket_status_key,
)

from app.cache.redis_cache_store import RedisCacheStore
from app.core.config import Settings
from app.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from app.core.errors import TicketNotFound
from app.db.models.draft_suggestion import DraftSuggestion
from app.db.models.routing_decision import RoutingDecision
from app.db.models.ticket import Ticket
from app.db.models.ticket_event import TicketEvent
from app.repositories.draft_suggestion_repository import DraftSuggestionRepository
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_embedding_repository import (
    SimilarTicketRow,
    TicketEmbeddingRepository,
)
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository


class TicketQueryService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        ticket_embedding_repository: TicketEmbeddingRepository,
        routing_decision_repository: RoutingDecisionRepository,
        ticket_event_repository: TicketEventRepository,
        draft_suggestion_repository: DraftSuggestionRepository,
        cache_store: RedisCacheStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._tickets = ticket_repository
        self._embeddings = ticket_embedding_repository
        self._routing = routing_decision_repository
        self._events = ticket_event_repository
        self._drafts = draft_suggestion_repository
        self._cache = cache_store
        self._settings = settings

    async def get_ticket(self, ticket_id: uuid.UUID) -> Ticket:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        return ticket

    async def get_ticket_status(self, ticket_id: uuid.UUID) -> str:
        if self._cache and self._settings:
            key = ticket_status_key(ticket_id)
            cached = await self._cache.get_model(key, CachedTicketStatus)
            if cached is not None:
                return cached.status

        status = await self._tickets.get_status(ticket_id)
        if status is None:
            raise TicketNotFound(ticket_id)

        if self._cache and self._settings:
            await self._cache.set_model(
                ticket_status_key(ticket_id),
                CachedTicketStatus(ticket_id=ticket_id, status=status),
                self._settings.cache_ttl_status_seconds,
            )
        return status

    async def list_tickets_by_status(
        self,
        status: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        return await self._tickets.list_by_status(status, limit=limit, offset=offset)

    async def is_ticket_searchable(self, ticket_id: uuid.UUID) -> bool:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)
        return await self._embeddings.has_active_embedding(ticket_id)

    async def get_latest_routing_decision(
        self, ticket_id: uuid.UUID
    ) -> RoutingDecision | None:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)

        if self._cache and self._settings:
            key = ticket_routing_latest_key(ticket_id)
            cached = await self._cache.get_model(key, CachedRoutingDecision)
            if cached is not None:
                return _routing_from_cached(cached)

        decision = await self._routing.get_latest_for_ticket(ticket_id)
        if decision is not None and self._cache and self._settings:
            await self._cache.set_model(
                ticket_routing_latest_key(ticket_id),
                _routing_to_cached(decision),
                self._settings.cache_ttl_routing_seconds,
            )
        return decision

    async def get_latest_draft_suggestion(
        self, ticket_id: uuid.UUID
    ) -> DraftSuggestion | None:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)

        if self._cache and self._settings:
            key = ticket_draft_latest_key(ticket_id)
            cached = await self._cache.get_model(key, CachedDraftSuggestion)
            if cached is not None:
                return _draft_from_cached(cached)

        draft = await self._drafts.get_latest_for_ticket(ticket_id)
        if draft is not None and self._cache and self._settings:
            await self._cache.set_model(
                ticket_draft_latest_key(ticket_id),
                _draft_to_cached(draft),
                self._settings.cache_ttl_draft_seconds,
            )
        return draft

    async def get_audit_trail(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)

        max_items = self._settings.cache_events_max_items if self._settings else 50

        if self._cache and self._settings:
            key = ticket_events_key(ticket_id)
            cached = await self._cache.get_model(key, CachedTicketEventsSummary)
            if cached is not None:
                return [_event_from_summary(ticket_id, item) for item in cached.events]

        events = await self._events.list_for_ticket(ticket_id)
        summary_items = [
            CachedEventSummaryItem(
                id=e.id,
                event_type=e.event_type,
                created_at=e.created_at,
            )
            for e in events[:max_items]
        ]
        if self._cache and self._settings:
            await self._cache.set_model(
                ticket_events_key(ticket_id),
                CachedTicketEventsSummary(ticket_id=ticket_id, events=summary_items),
                self._settings.cache_ttl_events_seconds,
            )
        return events

    async def search_similar_tickets(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        exclude_ticket_id: uuid.UUID | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        max_ticket_age_days: int | None = None,
    ) -> list[SimilarTicketRow]:
        model = embedding_model or DEFAULT_EMBEDDING_MODEL
        dimension = embedding_dimension or EMBEDDING_DIMENSION
        filters = SimilarityFilters(
            limit=limit,
            exclude_ticket_id=exclude_ticket_id,
            embedding_model=model,
            embedding_dimension=dimension,
            max_ticket_age_days=max_ticket_age_days,
        )
        query_hash = hash_embedding_query(query_embedding)
        filters_hash = hash_similarity_filters(filters)
        cache_key = similarity_key(
            embedding_model=model,
            embedding_dimension=dimension,
            query_hash=query_hash,
            filters_hash=filters_hash,
        )

        if self._cache and self._settings:
            cached = await self._cache.get_model(cache_key, CachedSimilarityResult)
            if cached is not None:
                return [_similar_row_from_cached(item) for item in cached.results]

        rows = await self._embeddings.search_similar(
            query_embedding,
            limit=limit,
            exclude_ticket_id=exclude_ticket_id,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            max_ticket_age_days=max_ticket_age_days,
        )

        if self._cache and self._settings:
            await self._cache.set_model(
                cache_key,
                CachedSimilarityResult(
                    embedding_model=model,
                    embedding_dimension=dimension,
                    query_hash=query_hash,
                    filters_hash=filters_hash,
                    filters=CachedSimilarityFilters.from_similarity_filters(filters),
                    results=[_similar_row_to_cached(row) for row in rows],
                    cached_at=datetime.now(UTC),
                ),
                self._settings.cache_ttl_similarity_seconds,
            )
        return rows


def _routing_to_cached(decision: RoutingDecision) -> CachedRoutingDecision:
    return CachedRoutingDecision(
        id=decision.id,
        ticket_id=decision.ticket_id,
        route_to=decision.route_to,
        decision_type=decision.decision_type,
        confidence=decision.confidence,
        reason=decision.reason,
        decided_by=decision.decided_by,
        created_at=decision.created_at,
        human_review_required=decision.reason == "human_review_required",
    )


def _routing_from_cached(cached: CachedRoutingDecision) -> RoutingDecision:
    return RoutingDecision(
        id=cached.id,
        ticket_id=cached.ticket_id,
        route_to=cached.route_to,
        decision_type=cached.decision_type,
        confidence=cached.confidence,
        reason=cached.reason,
        decided_by=cached.decided_by,
        created_at=cached.created_at,
    )


def _draft_to_cached(draft: DraftSuggestion) -> CachedDraftSuggestion:
    return CachedDraftSuggestion(
        id=draft.id,
        ticket_id=draft.ticket_id,
        draft_text=draft.draft_text,
        provider_name=draft.provider_name,
        model_name=draft.model_name,
        prompt_version=draft.prompt_version,
        status=draft.status,
        confidence=draft.confidence,
        requires_human_review=draft.requires_human_review,
        created_at=draft.created_at,
    )


def _draft_from_cached(cached: CachedDraftSuggestion) -> DraftSuggestion:
    return DraftSuggestion(
        id=cached.id,
        ticket_id=cached.ticket_id,
        draft_text=cached.draft_text,
        provider_name=cached.provider_name,
        model_name=cached.model_name,
        prompt_version=cached.prompt_version,
        status=cached.status,
        confidence=cached.confidence,
        requires_human_review=cached.requires_human_review,
        created_at=cached.created_at,
    )


def _event_from_summary(ticket_id: uuid.UUID, item: CachedEventSummaryItem) -> TicketEvent:
    return TicketEvent(
        id=item.id,
        ticket_id=ticket_id,
        event_type=item.event_type,
        payload=None,
        created_at=item.created_at,
    )


def _similar_row_to_cached(row: SimilarTicketRow) -> CachedSimilarityResultItem:
    return CachedSimilarityResultItem(
        ticket_id=row.ticket_id,
        embedding_id=row.embedding_id,
        subject=row.subject,
        source=row.source,
        status=row.status,
        distance=row.distance,
    )


def _similar_row_from_cached(item: CachedSimilarityResultItem) -> SimilarTicketRow:
    return SimilarTicketRow(
        ticket_id=item.ticket_id,
        embedding_id=item.embedding_id,
        subject=item.subject,
        source=item.source,
        status=item.status,
        distance=item.distance,
    )
