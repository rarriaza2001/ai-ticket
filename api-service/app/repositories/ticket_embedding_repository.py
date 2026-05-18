from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ticket import Ticket
from app.db.models.ticket_embedding import TicketEmbedding


class SimilarTicketRow(NamedTuple):
    ticket_id: uuid.UUID
    embedding_id: uuid.UUID
    subject: str
    source: str
    status: str
    distance: float


class TicketEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def deactivate_active_for_ticket(self, ticket_id: uuid.UUID) -> int:
        result = await self._session.execute(
            update(TicketEmbedding)
            .where(
                TicketEmbedding.ticket_id == ticket_id,
                TicketEmbedding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        return result.rowcount

    async def create_active_embedding(
        self,
        *,
        ticket_id: uuid.UUID,
        embedding: list[float],
        embedding_model: str,
        embedding_dimension: int,
        source_text_hash: str,
    ) -> TicketEmbedding:
        now = datetime.now(UTC)
        row = TicketEmbedding(
            ticket_id=ticket_id,
            embedding=embedding,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            source_text_hash=source_text_hash,
            is_active=True,
            embedded_at=now,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def has_active_embedding(self, ticket_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(TicketEmbedding.id)
            .where(
                TicketEmbedding.ticket_id == ticket_id,
                TicketEmbedding.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        exclude_ticket_id: uuid.UUID | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> list[SimilarTicketRow]:
        distance_expr = TicketEmbedding.embedding.cosine_distance(query_embedding).label(
            "distance"
        )
        stmt = (
            select(
                Ticket.id,
                TicketEmbedding.id,
                Ticket.subject,
                Ticket.source,
                Ticket.status,
                distance_expr,
            )
            .join(Ticket, TicketEmbedding.ticket_id == Ticket.id)
            .where(TicketEmbedding.is_active.is_(True))
        )
        if exclude_ticket_id is not None:
            stmt = stmt.where(Ticket.id != exclude_ticket_id)
        if embedding_model is not None:
            stmt = stmt.where(TicketEmbedding.embedding_model == embedding_model)
        if embedding_dimension is not None:
            stmt = stmt.where(TicketEmbedding.embedding_dimension == embedding_dimension)

        stmt = stmt.order_by(distance_expr).limit(limit)
        result = await self._session.execute(stmt)
        return [
            SimilarTicketRow(
                ticket_id=row[0],
                embedding_id=row[1],
                subject=row[2],
                source=row[3],
                status=row[4],
                distance=float(row[5]),
            )
            for row in result.all()
        ]
