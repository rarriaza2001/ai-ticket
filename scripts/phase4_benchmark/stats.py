"""Latency aggregation for benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchStats:
    label: str
    latencies_ms: list[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    def record(self, ms: float, *, hit: bool | None = None) -> None:
        self.latencies_ms.append(ms)
        if hit is True:
            self.cache_hits += 1
        elif hit is False:
            self.cache_misses += 1

    def to_report(self) -> dict:
        if not self.latencies_ms:
            return {"label": self.label, "samples": 0}

        sorted_ms = sorted(self.latencies_ms)
        n = len(sorted_ms)

        def pct(p: float) -> float:
            idx = min(int(p * n), n - 1)
            return sorted_ms[idx]

        total_cache = self.cache_hits + self.cache_misses
        return {
            "label": self.label,
            "samples": n,
            "p50_ms": round(pct(0.50), 2),
            "p95_ms": round(pct(0.95), 2),
            "p99_ms": round(pct(0.99), 2),
            "avg_ms": round(sum(sorted_ms) / n, 2),
            "min_ms": round(sorted_ms[0], 2),
            "max_ms": round(sorted_ms[-1], 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hits / total_cache, 4) if total_cache else None,
        }
