from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worker.core.config import Settings
from worker.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from worker.domain.enums import TicketStatus
from worker.providers.mock_provider import MockAiProvider, _hash_embedding
from worker.repositories.draft_suggestion_repository import DraftSuggestionRepository
from worker.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from worker.repositories.ticket_repository import TicketRepository
from worker.services.ai_workflow_service import AiWorkflowService


async def _create_ticket(
    session: AsyncSession,
    *,
    status: str = TicketStatus.PENDING_EMBEDDING.value,
    subject: str = "Billing issue",
    body: str = "I was charged twice for my subscription.",
    created_at: datetime | None = None,
) -> uuid.UUID:
    from worker.db.models.ticket import Ticket

    now = created_at or datetime.now(UTC)
    ticket = Ticket(
        source="email",
        subject=subject,
        body=body,
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(ticket)
    await session.flush()
    return ticket.id


async def _seed_peer_embedding(
    session: AsyncSession,
    *,
    subject: str,
    body: str,
    vector: list[float] | None = None,
    created_at: datetime | None = None,
) -> uuid.UUID:
    peer_id = await _create_ticket(
        session,
        status=TicketStatus.ROUTED.value,
        subject=subject,
        body=body,
        created_at=created_at,
    )
    text = f"{subject}\n{body}"
    vec = vector if vector is not None else _hash_embedding(text)
    repo = TicketEmbeddingRepository(session)
    await repo.create_active_embedding(
        ticket_id=peer_id,
        embedding=vec,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
        source_text_hash="peer-seed",
    )
    return peer_id


def _orthogonal_vector() -> list[float]:
    vec = [0.0] * EMBEDDING_DIMENSION
    vec[1] = 1.0
    return vec


@pytest.mark.asyncio
async def test_happy_path_workflow(
    db_session: AsyncSession,
    worker_settings: Settings,
    mock_provider: MockAiProvider,
) -> None:
    subject = "Billing issue"
    body = "I was charged twice for my subscription."
    await _seed_peer_embedding(db_session, subject=subject, body=body)
    ticket_id = await _create_ticket(db_session, subject=subject, body=body)

    workflow = AiWorkflowService(db_session, worker_settings, provider=mock_provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    tickets = TicketRepository(db_session)
    assert (await tickets.get_by_id(ticket_id)).status == TicketStatus.ROUTED.value

    embeddings = TicketEmbeddingRepository(db_session)
    record = await embeddings.get_active_embedding_record(ticket_id)
    assert record is not None
    assert record.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert record.embedding_dimension == EMBEDDING_DIMENSION

    from worker.db.models.routing_decision import RoutingDecision

    cat = await db_session.execute(
        select(RoutingDecision).where(
            RoutingDecision.ticket_id == ticket_id,
            RoutingDecision.decision_type == "category",
        )
    )
    assert cat.scalars().first() is not None

    drafts = DraftSuggestionRepository(db_session)
    assert await drafts.has_pending_review(ticket_id)
    assert mock_provider.call_counts["embed"] == 1
    assert mock_provider.call_counts["suggest"] == 1

    from worker.db.models.draft_suggestion import DraftSuggestion

    draft_row = await db_session.execute(
        select(DraftSuggestion).where(DraftSuggestion.ticket_id == ticket_id).limit(1)
    )
    draft = draft_row.scalars().first()
    assert draft is not None
    assert "status=" in draft.draft_text
    assert "distance=" in draft.draft_text


@pytest.mark.asyncio
async def test_no_similarity_matches_skips_draft(
    db_session: AsyncSession,
    worker_settings: Settings,
    mock_provider: MockAiProvider,
) -> None:
    ticket_id = await _create_ticket(db_session)

    workflow = AiWorkflowService(db_session, worker_settings, provider=mock_provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    drafts = DraftSuggestionRepository(db_session)
    assert not await drafts.has_pending_review(ticket_id)
    assert mock_provider.call_counts["suggest"] == 0


@pytest.mark.asyncio
async def test_low_confidence_routes_to_unknown_and_triage(
    db_session: AsyncSession,
    worker_settings: Settings,
) -> None:
    provider = MockAiProvider(force_low_confidence=True)
    ticket_id = await _create_ticket(db_session)

    workflow = AiWorkflowService(db_session, worker_settings, provider=provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    from worker.db.models.routing_decision import RoutingDecision

    result = await db_session.execute(
        select(RoutingDecision).where(RoutingDecision.ticket_id == ticket_id)
    )
    rows = {r.decision_type: r for r in result.scalars().all()}
    assert rows["category"].route_to == "unknown"
    assert rows["team"].route_to == "triage"
    assert rows["team"].reason in (
        "low_classification_confidence",
        "human_review_required",
    )


@pytest.mark.asyncio
async def test_low_routing_confidence_forces_triage(
    db_session: AsyncSession,
    worker_settings: Settings,
) -> None:
    provider = MockAiProvider(force_low_routing_confidence=True)
    ticket_id = await _create_ticket(db_session)

    workflow = AiWorkflowService(db_session, worker_settings, provider=provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    from worker.db.models.routing_decision import RoutingDecision

    result = await db_session.execute(
        select(RoutingDecision)
        .where(RoutingDecision.ticket_id == ticket_id)
        .where(RoutingDecision.decision_type == "team")
    )
    team_row = result.scalars().first()
    assert team_row is not None
    assert team_row.route_to == "triage"
    assert team_row.reason == "low_routing_confidence"


@pytest.mark.asyncio
async def test_malformed_classification_fallback_no_crash(
    db_session: AsyncSession,
    worker_settings: Settings,
) -> None:
    provider = MockAiProvider(force_malformed=True)
    ticket_id = await _create_ticket(db_session)

    workflow = AiWorkflowService(db_session, worker_settings, provider=provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    from worker.db.models.routing_decision import RoutingDecision

    result = await db_session.execute(
        select(RoutingDecision)
        .where(RoutingDecision.ticket_id == ticket_id)
        .where(RoutingDecision.decision_type == "team")
    )
    assert result.scalars().first().route_to == "triage"
    assert (await TicketRepository(db_session).get_by_id(ticket_id)).status == (
        TicketStatus.ROUTED.value
    )


@pytest.mark.asyncio
async def test_duplicate_processing_skips_embed_when_hash_unchanged(
    db_session: AsyncSession,
    worker_settings: Settings,
    mock_provider: MockAiProvider,
) -> None:
    subject = "Duplicate test"
    body = "Same body for peer and target."
    await _seed_peer_embedding(db_session, subject=subject, body=body)
    ticket_id = await _create_ticket(db_session, subject=subject, body=body)

    workflow = AiWorkflowService(db_session, worker_settings, provider=mock_provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    embed_after_first = mock_provider.call_counts["embed"]
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    assert mock_provider.call_counts["embed"] == embed_after_first


@pytest.mark.asyncio
async def test_weak_only_peer_skips_draft(
    db_session: AsyncSession,
    worker_settings: Settings,
    mock_provider: MockAiProvider,
) -> None:
    subject = "Weak match test"
    body = "Body text."
    await _seed_peer_embedding(
        db_session,
        subject="Different",
        body="Different body",
        vector=_orthogonal_vector(),
    )
    ticket_id = await _create_ticket(db_session, subject=subject, body=body)

    workflow = AiWorkflowService(db_session, worker_settings, provider=mock_provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    drafts = DraftSuggestionRepository(db_session)
    assert not await drafts.has_pending_review(ticket_id)


@pytest.mark.asyncio
async def test_stale_peer_excluded_from_draft(
    db_session: AsyncSession,
    worker_settings: Settings,
    mock_provider: MockAiProvider,
) -> None:
    subject = "Stale peer test"
    body = "Same text for match."
    stale_time = datetime.now(UTC) - timedelta(days=200)
    await _seed_peer_embedding(
        db_session, subject=subject, body=body, created_at=stale_time
    )
    ticket_id = await _create_ticket(db_session, subject=subject, body=body)

    workflow = AiWorkflowService(db_session, worker_settings, provider=mock_provider)
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    drafts = DraftSuggestionRepository(db_session)
    assert not await drafts.has_pending_review(ticket_id)


@pytest.mark.asyncio
async def test_mock_provider_only_no_external_calls(mock_provider: MockAiProvider) -> None:
    vec = await mock_provider.embed_text("sample")
    assert len(vec.vector) == EMBEDDING_DIMENSION
    assert vec.model_name == DEFAULT_EMBEDDING_MODEL
    assert mock_provider.provider_name == "mock"
