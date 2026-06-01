"""Invalidate ticket-scoped read-model cache keys (fail-open)."""

from __future__ import annotations

import uuid

from shared_contracts.cache_keys import (
    ticket_draft_latest_key,
    ticket_events_key,
    ticket_routing_latest_key,
    ticket_status_key,
)

from app.cache.redis_cache_store import RedisCacheStore


class TicketCacheInvalidator:
    def __init__(self, cache: RedisCacheStore) -> None:
        self._cache = cache

    async def invalidate_status(self, ticket_id: uuid.UUID) -> None:
        await self._cache.delete(ticket_status_key(ticket_id))

    async def invalidate_routing(self, ticket_id: uuid.UUID) -> None:
        await self._cache.delete(ticket_routing_latest_key(ticket_id))

    async def invalidate_draft(self, ticket_id: uuid.UUID) -> None:
        await self._cache.delete(ticket_draft_latest_key(ticket_id))

    async def invalidate_events(self, ticket_id: uuid.UUID) -> None:
        await self._cache.delete(ticket_events_key(ticket_id))

    async def invalidate_ticket_read_models(self, ticket_id: uuid.UUID) -> None:
        await self._cache.delete(
            ticket_status_key(ticket_id),
            ticket_routing_latest_key(ticket_id),
            ticket_draft_latest_key(ticket_id),
            ticket_events_key(ticket_id),
        )
