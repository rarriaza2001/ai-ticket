#!/usr/bin/env python3
"""Remove Phase 4 benchmark seed rows from Postgres."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from phase4_benchmark.paths import find_repo_root  # noqa: E402
from phase4_benchmark.seed import DEFAULT_DATABASE_URL, async_url, clear_seed_data  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    args = parser.parse_args()

    engine = create_async_engine(async_url(args.database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await clear_seed_data(session)
        await session.commit()
    await engine.dispose()
    print("Phase 4 benchmark seed data cleared.")


if __name__ == "__main__":
    asyncio.run(main())
