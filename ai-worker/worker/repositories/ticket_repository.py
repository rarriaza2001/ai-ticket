from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from worker.db.models.ticket import Ticket


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        result = await self._session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        result = await self._session.execute(
            select(Ticket)
            .where(Ticket.status == status)
            .order_by(Ticket.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(self, ticket_id: uuid.UUID, status: str) -> bool:
        result = await self._session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status=status, updated_at=datetime.now(UTC))
        )
        return result.rowcount > 0
