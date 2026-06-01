"""Shared constants and pure helpers for Phase 4 benchmarks."""

from __future__ import annotations

import hashlib

DATASET_SIZES: dict[str, int] = {
    "small": 25,
    "medium": 250,
    "large": 1000,
}

SIZE_ALIASES: dict[str, str] = {
    "25": "small",
    "250": "medium",
    "1000": "large",
}

SEED_SOURCE = "test_seed_phase4"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536

# Valid DB ticket statuses (api-service domain enums).
VALID_TICKET_STATUSES = frozenset(
    {
        "pending_embedding",
        "embedded",
        "routing_pending",
        "routed",
        "failed",
    }
)


def resolve_size(size_arg: str) -> tuple[str, int]:
    """Return (label, count) for CLI --size (small|medium|large or legacy int)."""
    key = size_arg.strip().lower()
    if key in DATASET_SIZES:
        return key, DATASET_SIZES[key]
    if key in SIZE_ALIASES:
        label = SIZE_ALIASES[key]
        return label, DATASET_SIZES[label]
    if key.isdigit() and int(key) in DATASET_SIZES.values():
        count = int(key)
        label = next(name for name, n in DATASET_SIZES.items() if n == count)
        return label, count
    valid = ", ".join([*DATASET_SIZES.keys(), *SIZE_ALIASES.keys()])
    msg = f"Invalid --size {size_arg!r}; expected one of: {valid}"
    raise ValueError(msg)


def deterministic_vector(index: int) -> list[float]:
    vec = [0.0] * EMBEDDING_DIMENSION
    vec[index % EMBEDDING_DIMENSION] = 1.0
    return vec


def text_hash(subject: str, body: str) -> str:
    return hashlib.sha256(f"{subject}\n{body}".encode()).hexdigest()


def status_for_index(index: int, total: int) -> str:
    """
    Map index to DB status using benchmark bands:
    - pending_embedding ~10%
    - processing (embedded / routing_pending) ~25%
    - completed (routed) ~60%
    - failed ~5%
    """
    pct = index / max(total, 1)
    if pct < 0.10:
        return "pending_embedding"
    if pct < 0.35:
        # processing: alternate embedded vs routing_pending
        return "embedded" if index % 2 == 0 else "routing_pending"
    if pct < 0.95:
        return "routed"
    return "failed"


def benchmark_label_for_status(status: str) -> str:
    """Human-readable benchmark label for manifest/docs."""
    if status == "pending_embedding":
        return "pending_embedding"
    if status in ("embedded", "routing_pending"):
        return "processing"
    if status == "routed":
        return "completed"
    if status == "failed":
        return "failed"
    return status
