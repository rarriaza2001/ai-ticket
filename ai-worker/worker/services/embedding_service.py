from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from worker.core.config import Settings
from worker.core.embedding import DEFAULT_EMBEDDING_MODEL
from worker.domain.enums import TicketEventType, TicketStatus
from worker.providers.base import AiProvider
from worker.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from worker.repositories.ticket_event_repository import TicketEventRepository
from worker.repositories.ticket_repository import TicketRepository

if TYPE_CHECKING:
    from worker.db.models.ticket import Ticket


def _ticket_text(ticket: Ticket) -> str:
    return f"{ticket.subject}\n{ticket.body}"


def _source_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _with_retries(coro_factory, *, max_retries: int):
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
    raise last_exc  # pragma: no cover


class EmbeddingService:
    def __init__(
        self,
        *,
        provider: AiProvider,
        settings: Settings,
        tickets: TicketRepository,
        embeddings: TicketEmbeddingRepository,
        events: TicketEventRepository,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._tickets = tickets
        self._embeddings = embeddings
        self._events = events

    async def ensure_embedding(
        self, ticket: Ticket
    ) -> tuple[list[float], str, int, str, float]:
        """Return (vector, model_name, dimension, provider_name, latency_ms)."""
        text = _ticket_text(ticket)
        text_hash = _source_text_hash(text)

        if not self._settings.force_regenerate_embeddings:
            active = await self._embeddings.get_active_embedding_record(ticket.id)
            if active is not None and active.source_text_hash == text_hash:
                return (
                    active.vector,
                    active.embedding_model,
                    active.embedding_dimension,
                    self._provider.provider_name,
                    0.0,
                )
            if active is not None:
                await self._embeddings.deactivate_active_for_ticket(ticket.id)

        started = time.perf_counter()

        async def _embed():
            return await self._provider.embed_text(text)

        result = await _with_retries(_embed, max_retries=self._settings.embedding_max_retries)
        latency_ms = (time.perf_counter() - started) * 1000

        model_name = result.model_name or self._settings.openai_embedding_model
        dimension = result.embedding_dimension or self._settings.openai_embedding_dimension

        await self._embeddings.deactivate_active_for_ticket(ticket.id)
        await self._embeddings.create_active_embedding(
            ticket_id=ticket.id,
            embedding=result.vector,
            embedding_model=model_name,
            embedding_dimension=dimension,
            source_text_hash=text_hash,
        )
        await self._tickets.update_status(ticket.id, TicketStatus.EMBEDDED.value)
        await self._events.append(
            ticket.id,
            TicketEventType.EMBEDDING_STORED.value,
            payload={
                "embedding_model": model_name,
                "embedding_dimension": dimension,
                "provider": result.provider_name,
                "source_text_hash": text_hash,
            },
        )
        return (
            result.vector,
            model_name,
            dimension,
            result.provider_name,
            latency_ms,
        )
