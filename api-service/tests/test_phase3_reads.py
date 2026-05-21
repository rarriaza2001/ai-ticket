from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.draft_suggestion_repository import DraftSuggestionRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_intake_service import TicketIntakeService
from shared_contracts import SuggestionStatus


@pytest.mark.asyncio
async def test_migration_includes_draft_suggestions(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'draft_suggestions'"
        )
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_get_draft_suggestion_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    intake = TicketIntakeService(TicketRepository(db_session), TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web",
        subject="Need help",
        body="Please assist with my order.",
    )
    drafts = DraftSuggestionRepository(db_session)
    await drafts.create(
        ticket_id=ticket.id,
        draft_text="Suggested reply for human review.",
        provider_name="mock",
        model_name="mock-suggestion-v1",
        prompt_version="phase3-scaffold-v1",
        status=SuggestionStatus.PENDING_REVIEW.value,
        confidence=Decimal("0.75"),
        requires_human_review=True,
    )
    await db_session.commit()

    response = await client.get(f"/tickets/{ticket.id}/draft-suggestion")
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["draft_text"] == "Suggested reply for human review."
    assert data["requires_human_review"] is True


@pytest.mark.asyncio
async def test_get_draft_suggestion_returns_null_when_missing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    intake = TicketIntakeService(TicketRepository(db_session), TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web",
        subject="No draft yet",
        body="Body",
    )
    await db_session.commit()

    response = await client.get(f"/tickets/{ticket.id}/draft-suggestion")
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_post_tickets_does_not_import_ai_providers() -> None:
    import app.services.ticket_intake_service as intake_module

    source = open(intake_module.__file__, encoding="utf-8").read()
    assert "providers" not in source
    assert "openai" not in source.lower()
