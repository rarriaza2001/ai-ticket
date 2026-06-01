"""Fast unit tests for Phase 4 benchmark tooling (no live API, no large seeds)."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from phase4_benchmark.common import (  # noqa: E402
    DATASET_SIZES,
    EMBEDDING_DIMENSION,
    VALID_TICKET_STATUSES,
    deterministic_vector,
    resolve_size,
    status_for_index,
)
from phase4_benchmark.manifest import SeedManifest  # noqa: E402
from phase4_benchmark.runner import normalize_mode  # noqa: E402
from phase4_benchmark.stats import BenchStats  # noqa: E402


@pytest.mark.benchmark_tooling
def test_resolve_size_labels() -> None:
    assert resolve_size("small") == ("small", 25)
    assert resolve_size("medium") == ("medium", 250)
    assert resolve_size("large") == ("large", 1000)
    assert resolve_size("250") == ("medium", 250)


@pytest.mark.benchmark_tooling
def test_resolve_size_invalid() -> None:
    with pytest.raises(ValueError):
        resolve_size("xlarge")


@pytest.mark.benchmark_tooling
def test_deterministic_vector_stable() -> None:
    a = deterministic_vector(7)
    b = deterministic_vector(7)
    assert len(a) == EMBEDDING_DIMENSION
    assert a == b
    assert a[7] == 1.0
    assert sum(1 for x in a if x != 0.0) == 1


@pytest.mark.benchmark_tooling
def test_status_for_index_uses_valid_db_enums() -> None:
    for i in range(100):
        status = status_for_index(i, 100)
        assert status in VALID_TICKET_STATUSES


@pytest.mark.benchmark_tooling
def test_bench_stats_report_percentiles() -> None:
    stats = BenchStats(label="test")
    for ms in [10.0, 20.0, 30.0, 40.0, 50.0]:
        stats.record(ms, hit=True)
    report = stats.to_report()
    assert report["samples"] == 5
    assert report["min_ms"] == 10.0
    assert report["max_ms"] == 50.0
    assert report["avg_ms"] == 30.0
    assert report["p50_ms"] == 30.0
    assert report["cache_hits"] == 5
    assert report["cache_hit_rate"] == 1.0


@pytest.mark.benchmark_tooling
def test_manifest_round_trip(tmp_path: Path) -> None:
    tid = uuid.uuid4()
    draft_id = uuid.uuid4()
    manifest = SeedManifest.build(
        dataset_size_label="small",
        dataset_ticket_count=25,
        sample_ticket_id=tid,
        sample_ticket_with_draft_id=draft_id,
        status_counts={"routed": 15, "pending_embedding": 3},
    )
    path = tmp_path / "manifest.json"
    manifest.write(path)
    loaded = SeedManifest.read(path)
    assert loaded is not None
    assert loaded.dataset_size_label == "small"
    assert loaded.dataset_ticket_count == 25
    assert loaded.sample_ticket_id == str(tid)
    assert loaded.sample_ticket_with_draft_id == str(draft_id)
    assert loaded.status_counts["routed"] == 15


@pytest.mark.benchmark_tooling
def test_normalize_mode_aliases() -> None:
    assert normalize_mode("uncached") == "baseline"
    assert normalize_mode("cold") == "cold-cache"
    assert normalize_mode("warm-cache") == "warm-cache"
    with pytest.raises(ValueError):
        normalize_mode("invalid-mode")


@pytest.mark.benchmark_tooling
def test_dataset_sizes_defaults() -> None:
    assert DATASET_SIZES["medium"] == 250


@pytest.mark.benchmark_tooling
def test_find_repo_root_and_results_dir() -> None:
    from phase4_benchmark.paths import find_repo_root, manifest_path, results_dir

    root = find_repo_root(_SCRIPTS_ROOT)
    assert (root / "api-service").is_dir()
    assert results_dir(root) == root / "benchmarks" / "results"
    assert manifest_path(root).name == "last_seed_manifest.json"


@pytest.mark.benchmark_tooling
def test_cache_analysis_invalid_flag() -> None:
    from phase4_benchmark.runner import _cache_analysis_invalid

    assert _cache_analysis_invalid(
        {"status": {"cache_hits": 0, "cache_misses": 0}}, normalized="warm-cache"
    )
    assert not _cache_analysis_invalid(
        {"status": {"cache_hits": 5, "cache_misses": 1}}, normalized="warm-cache"
    )
    assert _cache_analysis_invalid(
        {"status": {"cache_hits": 5, "cache_misses": 0}}, normalized="cold-cache"
    )
    assert not _cache_analysis_invalid(
        {"status": {"cache_hits": 5, "cache_misses": 1}}, normalized="cold-cache"
    )
    assert not _cache_analysis_invalid(
        {"status": {"cache_hits": 0, "cache_misses": 0}}, normalized="baseline"
    )


@pytest.mark.benchmark_tooling
def test_baseline_and_redis_down_invalid_flags() -> None:
    from phase4_benchmark.runner import _baseline_analysis_invalid

    assert not _baseline_analysis_invalid({"status": {"cache_hits": 0, "cache_misses": 0}})
    assert _baseline_analysis_invalid({"status": {"cache_hits": 1, "cache_misses": 0}})
    assert not _baseline_analysis_invalid({"status": {"cache_hits": 0, "cache_misses": 99}})


@pytest.mark.benchmark_tooling
def test_endpoint_cache_hit_rate_by_endpoint() -> None:
    from phase4_benchmark.runner import build_endpoint_cache_hit_rates

    rates = build_endpoint_cache_hit_rates(
        {
            "status": {"cache_hits": 50, "cache_misses": 0},
            "routing-decision": {"cache_hits": 40, "cache_misses": 10},
        }
    )
    assert rates["status"]["hit_rate"] == 1.0
    assert rates["routing_decision"]["cache_misses"] == 10
    assert rates["routing_decision"]["hit_rate"] == 0.8
