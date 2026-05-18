from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ticket import Ticket


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        source: str,
        subject: str,
        body: str,
        status: str,
        external_id: str | None = None,
        customer_email: str | None = None,
        priority: str | None = None,
    ) -> Ticket:
        now = datetime.now(UTC)
        ticket = Ticket(
            source=source,
            subject=subject,
            body=body,
            status=status,
            external_id=external_id,
            customer_email=customer_email,
            priority=priority,
            created_at=now,
            updated_at=now,
        )
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        result = await self._session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def get_status(self, ticket_id: uuid.UUID) -> str | None:
        result = await self._session.execute(
            select(Ticket.status).where(Ticket.id == ticket_id)
        )
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
            .order_by(Ticket.created_at.desc())
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
