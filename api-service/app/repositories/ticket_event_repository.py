from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ticket_event import TicketEvent


class TicketEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        ticket_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> TicketEvent:
        event = TicketEvent(
            ticket_id=ticket_id,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_for_ticket(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        result = await self._session.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at.asc())
        )
        return list(result.scalars().all())
