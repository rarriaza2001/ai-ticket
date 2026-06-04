# Phase 4 local cache benchmarks

Manual tooling only — normal `pytest` does not run HTTP benchmarks or large seeds.

## Prerequisites

1. Start stack: `docker compose -f docker/docker-compose.yml --env-file docker/.env.example up --build`
2. Migrations (host): `cd api-service` and `alembic upgrade head` with `DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets`
3. Seed data (from repo root or `api-service/`):

```bash
python ../scripts/seed_phase4_benchmark_data.py --size medium --reset
```

## Seed dataset sizes

| Flag | Tickets |
|------|---------|
| `--size small` | 25 |
| `--size medium` (default) | 250 |
| `--size large` | 1000 |

Legacy numeric sizes (`25`, `250`, `1000`) still work.

### Status bands (documentation labels)

| Label | DB `status` |
|-------|-------------|
| pending_embedding | `pending_embedding` |
| processing | `embedded`, `routing_pending` |
| completed | `routed` |
| failed | `failed` |

Embeddings exist for processing and completed tickets (`text-embedding-3-small`, 1536 dims, deterministic one-hot vectors).

## Clear seed data

```bash
python ../scripts/clear_phase4_benchmark_data.py
```

## Benchmark modes

| Mode | Setup |
|------|--------|
| `baseline` | `make rebuild-api-baseline` then run benchmark (no `X-Cache-Hit` headers) |
| `cold-cache` | `make rebuild-api-cached`; runner flushes `ai-ticket:v1:*` before measure |
| `warm-cache` | `make rebuild-api-cached`; `--warmup 20` then measure |
| `redis-down` | Runner stops the Redis container automatically (use `--no-manage-redis` to skip) |

Aliases: `uncached` → `baseline`, `cold` → `cold-cache`, `warm` → `warm-cache`.

## Run benchmarks

Makefile targets rebuild api-service with the correct cache env, then measure:

```bash
make benchmark-baseline      # CACHE_ENABLED=false, no X-Cache-Hit headers
make benchmark-cold-cache
make benchmark-warm-cache
make benchmark-redis-down    # stops/restarts Redis automatically
```

Or run the script directly (after `make rebuild-api-baseline` or `make rebuild-api-cached`):

```bash
python ../scripts/benchmark_phase4_cache.py --mode baseline --iterations 100
python ../scripts/benchmark_phase4_cache.py --mode cold-cache --iterations 100
python ../scripts/benchmark_phase4_cache.py --mode warm-cache --warmup 20 --iterations 100
python ../scripts/benchmark_phase4_cache.py --mode redis-down --iterations 50
```

Use `--no-manage-redis` with `redis-down` when you stop Redis yourself.

Results are written to `benchmarks/results/phase4_{mode}_{size}_{timestamp}.json` and printed to stdout.

## Interpreting cache headers

Responses include `X-Cache-Hit: 0` (miss) or `1` (hit) when `CACHE_ENABLED=true`. Baseline runs must omit this header entirely (`CACHE_ENABLED=false`). Benchmark JSON aggregates hits/misses per endpoint when headers are present.

## Manifest

`benchmarks/results/last_seed_manifest.json` lists sample ticket IDs for repeatable GET benchmarks. Regenerate with `--reset` seed.
