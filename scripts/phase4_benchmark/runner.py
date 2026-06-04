"""HTTP benchmark runner for Phase 4 cache reads."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from collections.abc import Callable
from pathlib import Path

import httpx

from phase4_benchmark.common import deterministic_vector, wait_for_api
from phase4_benchmark.manifest import SeedManifest
from phase4_benchmark.paths import (
    find_repo_root,
    manifest_path as default_manifest_path,
    results_dir,
    resolve_output_path,
)
from phase4_benchmark.preflight import run_cache_preflight
from phase4_benchmark.redis_util import (
    docker_container_running,
    docker_start_container,
    docker_stop_container,
    flush_cache_keys_with_fallback,
    ping_redis,
)
from phase4_benchmark.stats import BenchStats

MODE_ALIASES = {
    "uncached": "baseline",
    "baseline": "baseline",
    "cold": "cold-cache",
    "cold-cache": "cold-cache",
    "warm": "warm-cache",
    "warm-cache": "warm-cache",
    "redis-down": "redis-down",
}

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_REDIS_CONTAINER = "docker-redis-1"


def normalize_mode(mode: str) -> str:
    key = mode.strip().lower()
    if key not in MODE_ALIASES:
        valid = ", ".join(sorted(set(MODE_ALIASES.keys())))
        msg = f"Invalid mode {mode!r}; expected one of: {valid}"
        raise ValueError(msg)
    return MODE_ALIASES[key]


def default_output_path(mode: str, size_label: str, repo_root: Path | None = None) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return results_dir(repo_root) / f"phase4_{mode}_{size_label}_{ts}.json"


def resolve_ticket_ids(manifest: SeedManifest | None) -> tuple[uuid.UUID, uuid.UUID]:
    if manifest is not None:
        sample = uuid.UUID(manifest.sample_ticket_id)
        draft_raw = manifest.sample_ticket_with_draft_id
        draft = uuid.UUID(draft_raw) if draft_raw else sample
        return sample, draft
    raise ValueError("manifest required")


async def discover_ticket_via_similar(client: httpx.AsyncClient, query_index: int) -> uuid.UUID:
    body = {"embedding": deterministic_vector(query_index), "limit": 1}
    resp = await client.post("/tickets/similar", json=body)
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        msg = "No similar tickets found. Run seed_phase4_benchmark_data.py first."
        raise RuntimeError(msg)
    return uuid.UUID(results[0]["ticket_id"])


async def bench_get(
    client: httpx.AsyncClient,
    path: str,
    stats: BenchStats,
) -> None:
    started = time.perf_counter()
    resp = await client.get(path)
    elapsed = (time.perf_counter() - started) * 1000
    if resp.status_code == 404:
        msg = (
            f"GET {path} returned 404. Seed benchmark data first: "
            "make seed-phase4-medium"
        )
        raise RuntimeError(msg)
    resp.raise_for_status()
    hit = resp.headers.get("x-cache-hit")
    stats.record(elapsed, hit=(hit == "1") if hit else None)


async def bench_similar(
    client: httpx.AsyncClient,
    stats: BenchStats,
    query_index: int,
) -> None:
    body = {"embedding": deterministic_vector(query_index), "limit": 10}
    started = time.perf_counter()
    resp = await client.post("/tickets/similar", json=body)
    elapsed = (time.perf_counter() - started) * 1000
    resp.raise_for_status()
    hit = resp.headers.get("x-cache-hit")
    stats.record(elapsed, hit=(hit == "1") if hit else None)


def build_endpoint_fns(
    client: httpx.AsyncClient,
    ticket_id: uuid.UUID,
    draft_ticket_id: uuid.UUID,
    query_index: int,
) -> dict[str, Callable[[BenchStats], object]]:
    tid = str(ticket_id)
    draft_tid = str(draft_ticket_id)
    return {
        "status": lambda s: bench_get(client, f"/tickets/{tid}/status", s),
        "routing-decision": lambda s: bench_get(client, f"/tickets/{tid}/routing-decision", s),
        "draft-suggestion": lambda s: bench_get(client, f"/tickets/{draft_tid}/draft-suggestion", s),
        "events": lambda s: bench_get(client, f"/tickets/{tid}/events", s),
        "similar": lambda s: bench_similar(client, s, query_index),
    }


def build_endpoint_cache_hit_rates(endpoint_results: dict) -> dict[str, dict]:
    """Per-endpoint cache hit/miss counts and hit_rate (not a single global average)."""
    rates: dict[str, dict] = {}
    for name, report in endpoint_results.items():
        hits = report.get("cache_hits") or 0
        misses = report.get("cache_misses") or 0
        total = hits + misses
        key = name.replace("-", "_")
        rates[key] = {
            "cache_hits": hits,
            "cache_misses": misses,
            "hit_rate": round(hits / total, 4) if total else None,
        }
    return rates


def _baseline_analysis_invalid(endpoint_results: dict) -> bool:
    """Baseline must run with CACHE_ENABLED=false (no X-Cache-Hit headers at all)."""
    for report in endpoint_results.values():
        hits = report.get("cache_hits") or 0
        misses = report.get("cache_misses") or 0
        if hits > 0 or misses > 0:
            return True
    return False


async def _redis_down_analysis_invalid_async(
    *,
    redis_url: str,
    docker_redis_container: str,
) -> bool:
    """Invalid when Redis is still reachable after redis-down setup."""
    if docker_container_running(docker_redis_container):
        return True
    return await ping_redis(redis_url)


def _cache_analysis_invalid(endpoint_results: dict, *, normalized: str) -> bool:
    if normalized in ("baseline", "redis-down"):
        return False
    rates = build_endpoint_cache_hit_rates(endpoint_results)
    if not rates:
        return True
    if normalized == "warm-cache":
        return not any(r["cache_hits"] > 0 for r in rates.values())
    if normalized == "cold-cache":
        return not any(r["cache_misses"] > 0 for r in rates.values())
    return True


async def run_benchmark(
    *,
    base_url: str,
    mode: str,
    iterations: int,
    warmup: int,
    redis_url: str,
    manifest_file_path: Path | None = None,
    output_path: Path | None = None,
    skip_preflight: bool = False,
    docker_redis_container: str = DEFAULT_REDIS_CONTAINER,
    manage_redis: bool = True,
) -> dict:
    repo_root = find_repo_root()
    normalized = normalize_mode(mode)
    manifest_file = resolve_output_path(
        manifest_file_path or default_manifest_path(repo_root), repo_root
    )
    manifest = SeedManifest.read(manifest_file)
    if manifest is None:
        msg = f"Seed manifest not found: {manifest_file}. Run seed_phase4_benchmark_data.py first."
        raise FileNotFoundError(msg)

    redis_stopped_by_runner = False
    if normalized == "redis-down" and manage_redis:
        if docker_container_running(docker_redis_container):
            print(f"Stopping {docker_redis_container} for redis-down benchmark...")
            redis_stopped_by_runner = docker_stop_container(docker_redis_container)

    try:
        return await _run_benchmark_body(
            repo_root=repo_root,
            normalized=normalized,
            manifest_file=manifest_file,
            manifest=manifest,
            base_url=base_url,
            iterations=iterations,
            warmup=warmup,
            redis_url=redis_url,
            output_path=output_path,
            skip_preflight=skip_preflight,
            docker_redis_container=docker_redis_container,
            redis_stopped_by_runner=redis_stopped_by_runner,
        )
    finally:
        if redis_stopped_by_runner:
            print(f"Restarting {docker_redis_container}...")
            if not docker_start_container(docker_redis_container):
                print(
                    f"*** WARNING: failed to restart {docker_redis_container}; "
                    "run `docker compose -f docker/docker-compose.yml start redis` manually. ***"
                )


async def _run_benchmark_body(
    *,
    repo_root: Path,
    normalized: str,
    manifest_file: Path,
    manifest: SeedManifest,
    base_url: str,
    iterations: int,
    warmup: int,
    redis_url: str,
    output_path: Path | None,
    skip_preflight: bool,
    docker_redis_container: str,
    redis_stopped_by_runner: bool,
) -> dict:
    print(f"Waiting for API at {base_url}...")
    await wait_for_api(base_url)

    preflight_summary: dict | None = None
    if normalized in ("cold-cache", "warm-cache") and not skip_preflight:
        print("Running cache preflight (double-read + Redis key check)...")
        preflight = await run_cache_preflight(
            base_url=base_url,
            manifest=manifest,
            redis_url=redis_url,
            docker_redis_container=docker_redis_container,
        )
        preflight_summary = {
            "ok": preflight.ok,
            "redis_reachable": preflight.redis_reachable,
            "redis_keys_after_warmup": preflight.redis_keys_after_warmup,
            "status_miss": preflight.status_miss_header,
            "status_hit": preflight.status_hit_header,
            "similar_miss": preflight.similar_miss_header,
            "similar_hit": preflight.similar_hit_header,
            "warnings": preflight.warnings,
            "errors": preflight.errors,
        }
        if warning := preflight.loud_warning():
            if not preflight.ok:
                print(f"\n*** {warning} ***\n")

    if normalized == "cold-cache":
        deleted = await flush_cache_keys_with_fallback(
            redis_url, docker_container=docker_redis_container
        )
        print(f"Flushed {deleted} Redis keys matching ai-ticket:v1:*")

    redis_down_invalid = False
    if normalized == "redis-down":
        redis_down_invalid = await _redis_down_analysis_invalid_async(
            redis_url=redis_url,
            docker_redis_container=docker_redis_container,
        )
        if redis_down_invalid:
            hint = (
                f"Allow the runner to manage Redis (default) or stop {docker_redis_container} manually."
                if not redis_stopped_by_runner
                else "Redis is still reachable via REDIS_URL or another instance."
            )
            print(
                "\n*** WARNING: redis-down mode did not actually run with Redis unavailable. "
                f"{hint} "
                "Result will be marked invalid_for_redis_down_analysis=true. ***\n"
            )
        else:
            print("Redis unavailable for redis-down mode (expected).")

    if normalized == "baseline":
        print("Baseline expects api-service with CACHE_ENABLED=false (no X-Cache-Hit headers).")

    size_label = manifest.dataset_size_label if manifest else "unknown"
    ticket_count = manifest.dataset_ticket_count if manifest else 0
    query_index = manifest.similar_query_index if manifest else 0

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            ticket_id, draft_ticket_id = resolve_ticket_ids(manifest)
        except ValueError:
            ticket_id = await discover_ticket_via_similar(client, query_index)
            draft_ticket_id = ticket_id

        endpoints = build_endpoint_fns(client, ticket_id, draft_ticket_id, query_index)

        if warmup > 0 and normalized == "warm-cache":
            print(f"Warmup: {warmup} iterations per endpoint...")
            for _ in range(warmup):
                for fn in endpoints.values():
                    await fn(BenchStats(label="warmup"))

        endpoint_results = {}
        for name, fn in endpoints.items():
            stats = BenchStats(label=f"{normalized}:{name}")
            for _ in range(iterations):
                await fn(stats)
            endpoint_results[name] = stats.to_report()

    invalid_for_cache = _cache_analysis_invalid(endpoint_results, normalized=normalized)
    if preflight_summary is not None and not preflight_summary.get("ok", False):
        invalid_for_cache = True

    baseline_invalid = (
        _baseline_analysis_invalid(endpoint_results) if normalized == "baseline" else False
    )
    if baseline_invalid:
        print(
            "\n*** WARNING: baseline was run with cache enabled (X-Cache-Hit / cache counters observed). "
            "Recreate api-service with CACHE_ENABLED=false. "
            "Result marked invalid_for_baseline_analysis=true. ***\n"
        )

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "mode": normalized,
        "dataset_size": size_label,
        "dataset_ticket_count": ticket_count,
        "iterations": iterations,
        "warmup": warmup if normalized == "warm-cache" else 0,
        "base_url": base_url,
        "manifest_path": str(manifest_file.resolve()),
        "invalid_for_cache_analysis": invalid_for_cache,
        "invalid_for_baseline_analysis": baseline_invalid if normalized == "baseline" else None,
        "invalid_for_redis_down_analysis": redis_down_invalid if normalized == "redis-down" else None,
        "endpoint_cache_hit_rate_by_endpoint": build_endpoint_cache_hit_rates(endpoint_results),
        "preflight": preflight_summary,
        "endpoints": endpoint_results,
    }
    if invalid_for_cache and normalized in ("cold-cache", "warm-cache"):
        report["cache_analysis_note"] = (
            "Do not treat warm-cache or cold-cache latency as Redis evidence: "
            "no cache hits were recorded (X-Cache-Hit / cache counters)."
        )
    if baseline_invalid:
        report["baseline_analysis_note"] = (
            "Baseline must use CACHE_ENABLED=false; cache headers or counters were observed."
        )
    if normalized == "redis-down" and redis_down_invalid:
        report["redis_down_analysis_note"] = (
            "Redis-down requires the benchmark Redis container to be stopped; Redis was still reachable."
        )

    out = (
        resolve_output_path(output_path, repo_root)
        if output_path
        else default_output_path(normalized, size_label, repo_root)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote benchmark results to {out.resolve()}")
    return report
