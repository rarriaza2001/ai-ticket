"""Seed manifest read/write for benchmark runner ticket selection."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SeedManifest:
    dataset_size_label: str
    dataset_ticket_count: int
    seeded_at_utc: str
    sample_ticket_id: str
    sample_ticket_with_draft_id: str | None
    similar_query_index: int = 0
    seed_source: str = "test_seed_phase4"
    status_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SeedManifest:
        return cls(
            dataset_size_label=data["dataset_size_label"],
            dataset_ticket_count=int(data["dataset_ticket_count"]),
            seeded_at_utc=data["seeded_at_utc"],
            sample_ticket_id=data["sample_ticket_id"],
            sample_ticket_with_draft_id=data.get("sample_ticket_with_draft_id"),
            similar_query_index=int(data.get("similar_query_index", 0)),
            seed_source=data.get("seed_source", "test_seed_phase4"),
            status_counts=dict(data.get("status_counts", {})),
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> SeedManifest | None:
        if not path.is_file():
            return None
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def build(
        cls,
        *,
        dataset_size_label: str,
        dataset_ticket_count: int,
        sample_ticket_id: uuid.UUID,
        sample_ticket_with_draft_id: uuid.UUID | None,
        status_counts: dict[str, int],
        similar_query_index: int = 0,
        seed_source: str = "test_seed_phase4",
    ) -> SeedManifest:
        return cls(
            dataset_size_label=dataset_size_label,
            dataset_ticket_count=dataset_ticket_count,
            seeded_at_utc=datetime.now(UTC).isoformat(),
            sample_ticket_id=str(sample_ticket_id),
            sample_ticket_with_draft_id=(
                str(sample_ticket_with_draft_id) if sample_ticket_with_draft_id else None
            ),
            similar_query_index=similar_query_index,
            seed_source=seed_source,
            status_counts=status_counts,
        )
