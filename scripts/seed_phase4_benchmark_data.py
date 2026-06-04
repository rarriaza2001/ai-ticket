#!/usr/bin/env python3
"""Deterministic Phase 4 benchmark seed data (dev/local only). No OpenAI, no Redis writes."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from phase4_benchmark.common import DATASET_SIZES, resolve_size  # noqa: E402
from phase4_benchmark.paths import find_repo_root, manifest_path as default_manifest_path  # noqa: E402
from phase4_benchmark.seed import DEFAULT_DATABASE_URL, DEFAULT_REDIS_URL, run_seed  # noqa: E402


async def main() -> None:
    os.environ.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
    os.environ.setdefault("REDIS_URL", DEFAULT_REDIS_URL)
    repo_root = find_repo_root(Path(__file__))
    api_root = repo_root / "api-service"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))

    parser = argparse.ArgumentParser(description="Seed Phase 4 benchmark data")
    parser.add_argument(
        "--size",
        default="medium",
        help=f"Dataset size: small|medium|large or {list(DATASET_SIZES.values())} (default: medium)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--reset", action="store_true", help="Clear prior seed rows first")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Write seed manifest (default: benchmarks/results/last_seed_manifest.json)",
    )
    args = parser.parse_args()

    size_label, ticket_count = resolve_size(args.size)
    manifest_out = (
        args.manifest_path
        if args.manifest_path and args.manifest_path.is_absolute()
        else repo_root / (args.manifest_path or default_manifest_path())
    )

    manifest = await run_seed(
        size_label=size_label,
        ticket_count=ticket_count,
        database_url=args.database_url,
        api_root=api_root,
        reset=args.reset,
        skip_migrations=args.skip_migrations,
        manifest_path=manifest_out,
    )

    if args.reset:
        print("Cleared previous Phase 4 seed data.")
    print(f"Seeded {ticket_count} tickets (source={manifest.seed_source}, size={size_label}).")
    print(f"Status counts: {manifest.status_counts}")
    print(f"Manifest: {manifest_out.resolve()}")
    print(f"Sample ticket: {manifest.sample_ticket_id}")
    print(f"Draft sample ticket: {manifest.sample_ticket_with_draft_id}")
    print("Use similar_query_index=0 one-hot vector for POST /tickets/similar benchmarks.")


if __name__ == "__main__":
    asyncio.run(main())
