from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from shared_contracts import SuggestionStatus
from shared_contracts.cache_dtos import CachedTicketStatus
from shared_contracts.cache_keys import (
    SimilarityFilters,
    hash_embedding_query,
    hash_similarity_filters,
    similarity_key,
    ticket_events_key,
    ticket_status_key,
)

from app.cache.redis_cache_store import RedisCacheStore
from app.cache.ticket_cache_invalidator import TicketCacheInvalidator
from app.core.config import Settings, get_settings
from app.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from app.domain.enums import DecidedBy, RoutingDecisionType, TicketEventType
from app.repositories.draft_suggestion_repository import DraftSuggestionRepository
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.ticket_intake_service import TicketIntakeService
from app.services.ticket_query_service import TicketQueryService


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
def cache_store(mock_redis: MagicMock) -> RedisCacheStore:
    return RedisCacheStore(mock_redis, enabled=True, delete_invalid_on_read=True)


@pytest.fixture
def cache_settings(settings_override: Settings) -> Settings:
    return settings_override


def test_similarity_key_changes_with_filters(fake_embedding: list[float]) -> None:
    base = SimilarityFilters(
        limit=10,
        exclude_ticket_id=None,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
    )
    alt = SimilarityFilters(
        limit=5,
        exclude_ticket_id=None,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
    )
    q = hash_embedding_query(fake_embedding)
    k1 = similarity_key(
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
        query_hash=q,
        filters_hash=hash_similarity_filters(base),
    )
    k2 = similarity_key(
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
        query_hash=q,
        filters_hash=hash_similarity_filters(alt),
    )
    assert k1 != k2


def test_similarity_key_changes_with_model_dimension(fake_embedding: list[float]) -> None:
    q = hash_embedding_query(fake_embedding)
    f = hash_similarity_filters(
        SimilarityFilters(
            limit=10,
            exclude_ticket_id=None,
            embedding_model="other-model",
            embedding_dimension=768,
        )
    )
    k_default = similarity_key(
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
        query_hash=q,
        filters_hash=hash_similarity_filters(
            SimilarityFilters(
                limit=10,
                exclude_ticket_id=None,
                embedding_model=DEFAULT_EMBEDDING_MODEL,
                embedding_dimension=EMBEDDING_DIMENSION,
            )
        ),
    )
    k_other = similarity_key(
        embedding_model="other-model",
        embedding_dimension=768,
        query_hash=q,
        filters_hash=f,
    )
    assert k_default != k_other


@pytest.mark.asyncio
async def test_cache_hit_returns_status_without_postgres(
    db_session,
    cache_store: RedisCacheStore,
    cache_settings: Settings,
    fake_embedding: list[float],
) -> None:
    ticket_id = uuid.uuid4()
    key = ticket_status_key(ticket_id)
    dto = CachedTicketStatus(ticket_id=ticket_id, status="routed")
    await cache_store.set_model(key, dto, 60)

    tickets = MagicMock()
    tickets.get_status = AsyncMock()
    service = TicketQueryService(
        tickets,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        cache_store,
        cache_settings,
    )
    status = await service.get_ticket_status(ticket_id)
    assert status == "routed"
    tickets.get_status.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_falls_back_and_sets(
    db_session,
    mock_redis: MagicMock,
    cache_store: RedisCacheStore,
    cache_settings: Settings,
) -> None:
    intake = TicketIntakeService(
        TicketRepository(db_session),
        TicketEventRepository(db_session),
    )
    ticket = await intake.create_ticket(
        source="web", subject="Cache miss", body="Body text for cache test."
    )
    await db_session.commit()

    service = TicketQueryService(
        TicketRepository(db_session),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        cache_store,
        cache_settings,
    )
    status = await service.get_ticket_status(ticket.id)
    assert status == "pending_embedding"
    key = ticket_status_key(ticket.id)
    assert key in mock_redis._store


@pytest.mark.asyncio
async def test_redis_unavailable_treats_as_miss(
    db_session,
    cache_settings: Settings,
) -> None:
    client = MagicMock()
    client.get = AsyncMock(side_effect=ConnectionError("redis down"))
    store = RedisCacheStore(client, enabled=True)

    intake = TicketIntakeService(
        TicketRepository(db_session),
        TicketEventRepository(db_session),
    )
    ticket = await intake.create_ticket(
        source="web", subject="Redis down", body="Fallback to postgres."
    )
    await db_session.commit()

    service = TicketQueryService(
        TicketRepository(db_session),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        store,
        cache_settings,
    )
    status = await service.get_ticket_status(ticket.id)
    assert status == "pending_embedding"


@pytest.mark.asyncio
async def test_malformed_json_treated_as_miss(
    db_session,
    mock_redis: MagicMock,
    cache_store: RedisCacheStore,
    cache_settings: Settings,
) -> None:
    tickets = TicketRepository(db_session)
    intake = TicketIntakeService(tickets, TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web", subject="Malformed", body="Should fall back."
    )
    await db_session.commit()
    mock_redis._store[ticket_status_key(ticket.id)] = "not-json"

    service = TicketQueryService(
        tickets,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        cache_store,
        cache_settings,
    )
    status = await service.get_ticket_status(ticket.id)
    assert status == "pending_embedding"
    # Bad key removed then repopulated with valid cached DTO
    cached_raw = mock_redis._store.get(ticket_status_key(ticket.id), "")
    assert "pending_embedding" in cached_raw


@pytest.mark.asyncio
async def test_invalid_cached_status_treated_as_miss(
    db_session,
    mock_redis: MagicMock,
    cache_store: RedisCacheStore,
    cache_settings: Settings,
) -> None:
    tickets = TicketRepository(db_session)
    intake = TicketIntakeService(tickets, TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web", subject="Invalid enum", body="Fallback expected."
    )
    await db_session.commit()
    mock_redis._store[ticket_status_key(ticket.id)] = json.dumps(
        {
            "schema_version": 1,
            "ticket_id": str(ticket.id),
            "status": "not_a_real_status",
        }
    )

    service = TicketQueryService(
        tickets,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        cache_store,
        cache_settings,
    )
    status = await service.get_ticket_status(ticket.id)
    assert status == "pending_embedding"


@pytest.mark.asyncio
async def test_embedding_persistence_invalidates_status_and_events(
    db_session,
    mock_redis: MagicMock,
    cache_store: RedisCacheStore,
    fake_embedding: list[float],
) -> None:
    tickets = TicketRepository(db_session)
    intake = TicketIntakeService(tickets, TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web", subject="Inv", body="Invalidation test body."
    )
    await db_session.commit()

    inv = TicketCacheInvalidator(cache_store)
    await cache_store.set_model(
        ticket_status_key(ticket.id),
        CachedTicketStatus(ticket_id=ticket.id, status="embedded"),
        60,
    )
    mock_redis._store[ticket_events_key(ticket.id)] = "{}"

    svc = EmbeddingPersistenceService(
        tickets,
        MagicMock(),
        TicketEventRepository(db_session),
        inv,
    )
    embeddings_repo = MagicMock()
    embeddings_repo.deactivate_active_for_ticket = AsyncMock(return_value=0)
    embeddings_repo.create_active_embedding = AsyncMock(
        return_value=MagicMock(id=uuid.uuid4())
    )
    svc._embeddings = embeddings_repo

    await svc.store_ticket_embedding(
        ticket.id,
        embedding=fake_embedding,
        source_text_hash="abc",
    )
    assert ticket_status_key(ticket.id) not in mock_redis._store
    assert ticket_events_key(ticket.id) not in mock_redis._store


@pytest.mark.asyncio
async def test_ticket_creation_succeeds_when_redis_delete_fails(
    db_session,
) -> None:
    client = MagicMock()
    client.delete = AsyncMock(side_effect=ConnectionError("redis down"))
    store = RedisCacheStore(client, enabled=True)
    inv = TicketCacheInvalidator(store)

    ticket = await TicketIntakeService(
        TicketRepository(db_session),
        TicketEventRepository(db_session),
        inv,
    ).create_ticket(source="web", subject="No fail", body="Create must succeed.")
    assert ticket.id is not None


@pytest.mark.asyncio
async def test_x_cache_hit_header_on_status_double_read(
    client: AsyncClient,
    db_session,
) -> None:
    intake = TicketIntakeService(
        TicketRepository(db_session), TicketEventRepository(db_session)
    )
    ticket = await intake.create_ticket(
        source="web", subject="Cache header", body="X-Cache-Hit integration test."
    )
    await db_session.commit()

    first = await client.get(f"/tickets/{ticket.id}/status")
    assert first.status_code == 200
    assert first.headers.get("x-cache-hit") == "0"

    second = await client.get(f"/tickets/{ticket.id}/status")
    assert second.status_code == 200
    assert second.headers.get("x-cache-hit") == "1"


@pytest.mark.asyncio
async def test_similar_request_cache_hit(
    client: AsyncClient,
    db_session,
    mock_redis: MagicMock,
    fake_embedding: list[float],
) -> None:
    from app.repositories.ticket_embedding_repository import TicketEmbeddingRepository

    intake = TicketIntakeService(
        TicketRepository(db_session), TicketEventRepository(db_session)
    )
    ticket = await intake.create_ticket(
        source="web", subject="Similar", body="Peer ticket body."
    )
    embeddings = TicketEmbeddingRepository(db_session)
    await embeddings.create_active_embedding(
        ticket_id=ticket.id,
        embedding=fake_embedding,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
        source_text_hash="hash-a",
    )
    await db_session.commit()

    body = {"embedding": fake_embedding, "limit": 10}
    r1 = await client.post("/tickets/similar", json=body)
    assert r1.status_code == 200
    assert r1.headers.get("x-cache-hit") == "0"
    r2 = await client.post("/tickets/similar", json=body)
    assert r2.status_code == 200
    assert r2.headers.get("x-cache-hit") == "1"
    assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_get_status_endpoint(
    client: AsyncClient,
    db_session,
) -> None:
    intake = TicketIntakeService(
        TicketRepository(db_session), TicketEventRepository(db_session)
    )
    ticket = await intake.create_ticket(
        source="web", subject="Status", body="Status endpoint test."
    )
    await db_session.commit()
    response = await client.get(f"/tickets/{ticket.id}/status")
    assert response.status_code == 200
    assert response.json()["status"] == "pending_embedding"


@pytest.mark.asyncio
async def test_routing_cache_invalidated_after_persist(
    db_session,
    mock_redis: MagicMock,
    cache_store: RedisCacheStore,
) -> None:
    from shared_contracts.cache_keys import ticket_routing_latest_key

    tickets = TicketRepository(db_session)
    intake = TicketIntakeService(tickets, TicketEventRepository(db_session))
    ticket = await intake.create_ticket(
        source="web", subject="Route", body="Routing invalidation."
    )
    await db_session.commit()
    inv = TicketCacheInvalidator(cache_store)
    mock_redis._store[ticket_routing_latest_key(ticket.id)] = "{}"

    from app.services.routing_persistence_service import RoutingPersistenceService

    await RoutingPersistenceService(
        tickets,
        RoutingDecisionRepository(db_session),
        TicketEventRepository(db_session),
        inv,
    ).store_routing_decision(
        ticket.id,
        route_to="billing",
        decision_type=RoutingDecisionType.TEAM.value,
        decided_by=DecidedBy.MANUAL.value,
    )
    assert ticket_routing_latest_key(ticket.id) not in mock_redis._store
