from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worker.db.models.draft_suggestion import DraftSuggestion


class DraftSuggestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        draft_text: str,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        status: str,
        confidence: Decimal | None = None,
        requires_human_review: bool = True,
    ) -> DraftSuggestion:
        row = DraftSuggestion(
            ticket_id=ticket_id,
            draft_text=draft_text,
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            status=status,
            confidence=confidence,
            requires_human_review=requires_human_review,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def has_pending_review(self, ticket_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(DraftSuggestion.id)
            .where(
                DraftSuggestion.ticket_id == ticket_id,
                DraftSuggestion.status == "pending_review",
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
