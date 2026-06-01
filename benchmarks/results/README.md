# Phase 4 benchmark results

This directory stores **locally generated** benchmark JSON files. Measured runs are gitignored.

## Generated files

| File | Description |
|------|-------------|
| `last_seed_manifest.json` | Written by `scripts/seed_phase4_benchmark_data.py` (ticket IDs for runner) |
| `phase4_{mode}_{size}_{timestamp}.json` | Written by `scripts/benchmark_phase4_cache.py` |

## Sample output

`sample_output.json` is optional. To create it from a real run (do not hand-edit latencies):

```bash
# After seed + warm-cache benchmark
cp benchmarks/results/phase4_warm-cache_medium_*.json benchmarks/results/sample_output.json
```

Only commit `sample_output.json` if it came from an actual local measurement.
