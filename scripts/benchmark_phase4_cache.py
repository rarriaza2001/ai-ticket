#!/usr/bin/env python3
"""
Phase 4 cache benchmark (measured values only).

Modes: baseline, cold-cache, warm-cache, redis-down (alias: uncached, cold, warm).
Requires seeded data and running api-service. See docs/BENCHMARKS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from phase4_benchmark.paths import find_repo_root, manifest_path as default_manifest_path  # noqa: E402
from phase4_benchmark.runner import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_REDIS_CONTAINER,
    normalize_mode,
    run_benchmark,
)

DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def main() -> None:
    repo_root = find_repo_root(Path(__file__))

    parser = argparse.ArgumentParser(description="Run Phase 4 cache benchmarks")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--mode",
        default="warm-cache",
        help="baseline | cold-cache | warm-cache | redis-down (aliases: uncached, cold, warm)",
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--redis-url", default=DEFAULT_REDIS_URL)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Seed manifest (default: benchmarks/results/last_seed_manifest.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON output under benchmarks/results/",
    )
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--docker-redis-container",
        default=DEFAULT_REDIS_CONTAINER,
        help="Container name for redis-cli when host cannot reach REDIS_URL",
    )
    parser.add_argument(
        "--no-manage-redis",
        action="store_true",
        help="Do not stop/start the Redis container for redis-down mode",
    )
    args = parser.parse_args()

    manifest_file = args.manifest_path
    if manifest_file is not None and not manifest_file.is_absolute():
        manifest_file = repo_root / manifest_file

    output_path = args.output
    if output_path is not None and not output_path.is_absolute():
        output_path = repo_root / output_path

    normalize_mode(args.mode)

    asyncio.run(
        run_benchmark(
            base_url=args.base_url,
            mode=args.mode,
            iterations=args.iterations,
            warmup=args.warmup,
            redis_url=args.redis_url,
            manifest_file_path=manifest_file,
            output_path=output_path,
            skip_preflight=args.skip_preflight,
            docker_redis_container=args.docker_redis_container,
            manage_redis=not args.no_manage_redis,
        )
    )


if __name__ == "__main__":
    main()
