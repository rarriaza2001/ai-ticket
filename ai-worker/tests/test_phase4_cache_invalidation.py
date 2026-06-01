from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared_contracts import SuggestionStatus
from shared_contracts.cache_keys import (
    ticket_draft_latest_key,
    ticket_events_key,
    ticket_routing_latest_key,
    ticket_status_key,
)

from worker.cache.redis_cache_store import RedisCacheStore
from worker.cache.ticket_cache_invalidator import TicketCacheInvalidator
from worker.core.config import get_settings
from worker.domain.enums import TicketStatus
from worker.providers.mock_provider import MockAiProvider
from worker.repositories.draft_suggestion_repository import DraftSuggestionRepository
from worker.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from worker.repositories.ticket_event_repository import TicketEventRepository
from worker.repositories.ticket_repository import TicketRepository
from worker.services.ai_workflow_service import AiWorkflowService


@pytest.fixture
def mock_redis() -> MagicMock:
    store: dict[str, str] = {}
    client = MagicMock()

    async def _get(key: str):
        return store.get(key)

    async def _set(key: str, value: str, ex: int | None = None):
        store[key] = value
        return True

    async def _delete(*keys: str):
        for key in keys:
            store.pop(key, None)
        return len(keys)

    client.get = AsyncMock(side_effect=_get)
    client.set = AsyncMock(side_effect=_set)
    client.delete = AsyncMock(side_effect=_delete)
    client._store = store
    return client


@pytest.fixture
def cache_invalidator(mock_redis: MagicMock) -> TicketCacheInvalidator:
    store = RedisCacheStore(mock_redis, enabled=True)
    return TicketCacheInvalidator(store)


async def _create_ticket(db_session, *, subject: str = "Worker cache test") -> uuid.UUID:
    from datetime import UTC, datetime

    from worker.db.models.ticket import Ticket

    now = datetime.now(UTC)
    ticket = Ticket(
        source="web",
        subject=subject,
        body="Body for worker invalidation tests.",
        status=TicketStatus.PENDING_EMBEDDING.value,
        created_at=now,
        updated_at=now,
    )
    db_session.add(ticket)
    await db_session.flush()
    return ticket.id


@pytest.mark.asyncio
async def test_workflow_invalidates_read_models_on_completion(
    db_session,
    mock_redis: MagicMock,
    cache_invalidator: TicketCacheInvalidator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "mock")
    settings = get_settings()

    ticket_id = await _create_ticket(db_session)
    await db_session.commit()

    for key_fn in (
        ticket_status_key,
        ticket_routing_latest_key,
        ticket_draft_latest_key,
        ticket_events_key,
    ):
        mock_redis._store[key_fn(ticket_id)] = '{"schema_version":1}'

    provider = MockAiProvider()
    workflow = AiWorkflowService(
        db_session,
        settings,
        provider=provider,
        cache_invalidator=cache_invalidator,
    )
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    assert ticket_status_key(ticket_id) not in mock_redis._store
    assert ticket_routing_latest_key(ticket_id) not in mock_redis._store
    assert ticket_events_key(ticket_id) not in mock_redis._store


@pytest.mark.asyncio
async def test_workflow_completes_when_redis_delete_fails(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "mock")
    settings = get_settings()

    client = MagicMock()
    client.delete = AsyncMock(side_effect=ConnectionError("redis down"))
    store = RedisCacheStore(client, enabled=True)
    inv = TicketCacheInvalidator(store)

    ticket_id = await _create_ticket(db_session)
    await db_session.commit()

    workflow = AiWorkflowService(
        db_session,
        settings,
        provider=MockAiProvider(),
        cache_invalidator=inv,
    )
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    tickets = TicketRepository(db_session)
    ticket = await tickets.get_by_id(ticket_id)
    assert ticket is not None
    assert ticket.status == TicketStatus.ROUTED.value


@pytest.mark.asyncio
async def test_workflow_failure_invalidates_status_and_events(
    db_session,
    mock_redis: MagicMock,
    cache_invalidator: TicketCacheInvalidator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "mock")
    settings = get_settings()

    ticket_id = await _create_ticket(db_session)
    await db_session.commit()

    mock_redis._store[ticket_status_key(ticket_id)] = "{}"
    mock_redis._store[ticket_events_key(ticket_id)] = "{}"

    class FailingProvider(MockAiProvider):
        async def embed_text(self, text: str):
            raise RuntimeError("forced failure")

    workflow = AiWorkflowService(
        db_session,
        settings,
        provider=FailingProvider(),
        cache_invalidator=cache_invalidator,
    )
    await workflow.process_ticket(ticket_id)
    await db_session.commit()

    assert ticket_status_key(ticket_id) not in mock_redis._store
    assert ticket_events_key(ticket_id) not in mock_redis._store

    tickets = TicketRepository(db_session)
    ticket = await tickets.get_by_id(ticket_id)
    assert ticket is not None
    assert ticket.status == TicketStatus.FAILED.value
