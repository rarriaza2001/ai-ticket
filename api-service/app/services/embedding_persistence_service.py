from __future__ import annotations

import uuid

from app.cache.ticket_cache_invalidator import TicketCacheInvalidator
from app.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from app.core.errors import TicketNotFound
from app.db.models.ticket_embedding import TicketEmbedding
from app.domain.enums import TicketEventType, TicketStatus
from app.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository


class EmbeddingPersistenceService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        ticket_embedding_repository: TicketEmbeddingRepository,
        ticket_event_repository: TicketEventRepository,
        cache_invalidator: TicketCacheInvalidator | None = None,
    ) -> None:
        self._tickets = ticket_repository
        self._embeddings = ticket_embedding_repository
        self._events = ticket_event_repository
        self._cache_invalidator = cache_invalidator

    async def store_ticket_embedding(
        self,
        ticket_id: uuid.UUID,
        *,
        embedding: list[float],
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_dimension: int = EMBEDDING_DIMENSION,
        source_text_hash: str,
    ) -> TicketEmbedding:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)

        await self._embeddings.deactivate_active_for_ticket(ticket_id)
        row = await self._embeddings.create_active_embedding(
            ticket_id=ticket_id,
            embedding=embedding,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            source_text_hash=source_text_hash,
        )
        await self._tickets.update_status(ticket_id, TicketStatus.EMBEDDED.value)
        await self._events.append(
            ticket_id,
            TicketEventType.EMBEDDING_STORED.value,
            payload={
                "embedding_id": str(row.id),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            },
        )
        if self._cache_invalidator is not None:
            await self._cache_invalidator.invalidate_status(ticket_id)
            await self._cache_invalidator.invalidate_events(ticket_id)
        return row
