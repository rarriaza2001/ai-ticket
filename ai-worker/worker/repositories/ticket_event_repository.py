from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from worker.db.models.ticket_event import TicketEvent


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
