"""Centralized Redis cache key builders (namespace + hashes). No Redis client logic."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

CACHE_NAMESPACE = "ai-ticket:v1"


@dataclass(frozen=True)
class SimilarityFilters:
    limit: int
    exclude_ticket_id: uuid.UUID | None
    embedding_model: str
    embedding_dimension: int
    max_ticket_age_days: int | None = None


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def hash_embedding_query(vector: list[float], *, precision: int = 8) -> str:
    rounded = [round(float(v), precision) for v in vector]
    payload = _canonical_json(rounded)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_similarity_filters(filters: SimilarityFilters) -> str:
    payload = {
        "limit": filters.limit,
        "exclude_ticket_id": str(filters.exclude_ticket_id)
        if filters.exclude_ticket_id is not None
        else None,
        "embedding_model": filters.embedding_model,
        "embedding_dimension": filters.embedding_dimension,
        "max_ticket_age_days": filters.max_ticket_age_days,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def similarity_key(
    *,
    embedding_model: str,
    embedding_dimension: int,
    query_hash: str,
    filters_hash: str,
) -> str:
    return (
        f"{CACHE_NAMESPACE}:similarity:"
        f"{embedding_model}:{embedding_dimension}:{query_hash}:{filters_hash}"
    )


def ticket_status_key(ticket_id: uuid.UUID) -> str:
    return f"{CACHE_NAMESPACE}:ticket:{ticket_id}:status"


def ticket_routing_latest_key(ticket_id: uuid.UUID) -> str:
    return f"{CACHE_NAMESPACE}:ticket:{ticket_id}:routing:latest"


def ticket_draft_latest_key(ticket_id: uuid.UUID) -> str:
    return f"{CACHE_NAMESPACE}:ticket:{ticket_id}:draft:latest"


def ticket_events_key(ticket_id: uuid.UUID) -> str:
    return f"{CACHE_NAMESPACE}:ticket:{ticket_id}:events"
