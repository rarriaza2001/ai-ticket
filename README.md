# AI Support Ticket Triage — Phase 4 Redis caching

Two Python services plus **neutral** shared schemas:

- **`api-service/`** — FastAPI: health/readiness, **thin ticket intake and reads** (`POST /tickets` stays fast; no AI providers on the API path). Phase 4 adds **fail-open Redis cache-aside** on read endpoints and similarity search.
- **`ai-worker/`** — Background AI workflow: polls `pending_embedding` tickets, embed/classify/retrieve/suggest via provider interface (`mock` default, optional `openai`), persists to Postgres. Invalidates API read-model cache keys after durable writes.
- **`shared-contracts/`** — Health/readiness, taxonomies, AI DTOs, and **cache key helpers + JSON cache DTOs** (`ai-ticket:v1:...`).

Postgres is **authoritative** for ticket data. Redis is **non-authoritative** (readiness + ephemeral read cache; failures fall back to Postgres).

## Local development (Docker Compose)

Prerequisites: Docker Desktop (or Docker Engine) and optionally [uv](https://github.com/astral-sh/uv).

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env.example up --build
```

### If image pull fails (`registry-1.docker.io`, `no such host`)

That is a **host / Docker networking or DNS** problem, not an application bug. Try, in order:

1. Confirm the machine has internet and DNS: `nslookup registry-1.docker.io` (PowerShell).
2. Docker Desktop → **Settings → Network**: try a fixed DNS (for example `8.8.8.8`), or match your corporate/VPN requirements.
3. **Restart Docker Desktop** after VPN or Wi‑Fi changes.
4. Windows: `ipconfig /flushdns` (elevated PowerShell), then retry `docker compose pull`.

If even the Postgres image pull fails, the issue is general Docker Hub access from your environment.

### Postgres + pgvector (Phase 2 default)

[`docker/docker-compose.yml`](docker/docker-compose.yml) uses **`pgvector/pgvector:pg16`** with the init script mounted from [`docker/postgres/init/`](docker/postgres/init/). Postgres is published on **`localhost:5433`** by default (`POSTGRES_PORT` in Compose) for host-run migrations and tests.

**Switching from Phase 1 `postgres:16-bookworm`:** remove the old volume so init scripts run:

```bash
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml --env-file docker/.env.example up --build
```

Verify the extension:

```bash
docker compose -f docker/docker-compose.yml exec postgres \
  psql -U ticket -d tickets -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Containers use Docker DNS hostnames **`postgres`** and **`redis`** (not `localhost`) for `DATABASE_URL` and `REDIS_URL`.

Compose service names are **`api-service`** and **`ai-worker`** (not `api` / `worker`).

API: `http://localhost:8000` — try `GET /health`, `GET /ready`, OpenAPI at `/docs`.

### Smoke tests

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/ready
```

- Healthy stack: `/ready` returns **200** with `postgres: true`, `redis: true`, `degraded: false`.
- Redis down only: **200** with `degraded: true` (Postgres still up).
- Postgres down / bad `DATABASE_URL`: **503** JSON with `code: postgres_unavailable`.

**Phase 3 end-to-end (worker + API):**

```bash
# 1. Create ticket (status pending_embedding)
curl -sS -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"source":"web","subject":"Billing issue","body":"I was charged twice."}'

# 2. Wait ~5–10s for ai-worker poll, then check status (expect routed)
curl -sS http://localhost:8000/tickets/<TICKET_ID>/status

# 3. Reads (human review flags without a new ticket status)
curl -sS http://localhost:8000/tickets/<TICKET_ID>/routing-decision
curl -sS http://localhost:8000/tickets/<TICKET_ID>/draft-suggestion
curl -sS http://localhost:8000/tickets/<TICKET_ID>/events
```

Tickets stay **`routed`** after processing. Use **`requires_human_review`** on draft suggestions, **`human_review_required`** on routing decisions (when `reason` is `human_review_required`), and classification event payloads for review queues.

**Host vs container URLs:** Compose builds in-container `DATABASE_URL` from `POSTGRES_*` (service hostname `postgres`). For host-side Alembic/tests, set `DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets` in your shell — do not export host `localhost` URLs before `docker compose up` or they used to override container env (now ignored by Compose).

## Configuration

Required for both services: **`DATABASE_URL`**, **`REDIS_URL`**.

Optional: `LOG_LEVEL`, `ENV`, `SERVICE_NAME`, pool tuning, and Phase 4 cache TTLs (`CACHE_ENABLED`, `CACHE_TTL_*`; see [`app/core/config.py`](api-service/app/core/config.py)).

Examples: [`docker/.env.example`](docker/.env.example), [`infrastructure/env/.env.example`](infrastructure/env/.env.example).

## Phase 4 cache benchmarks (local, manual)

Full guide: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md). Results land in [`benchmarks/results/`](benchmarks/results/) (gitignored except optional `sample_output.json`).

### 1. Start stack and migrate

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env.example up --build

cd api-service
# PowerShell: $env:DATABASE_URL="postgresql://ticket:ticket@localhost:5433/tickets"
export DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets
alembic upgrade head   # or: uv run alembic upgrade head
```

### 2. Seed benchmark data

```bash
# From api-service/ (or repo root with PYTHONPATH)
python ../scripts/seed_phase4_benchmark_data.py --size small --reset    # 25
python ../scripts/seed_phase4_benchmark_data.py --size medium --reset   # 250 (default)
python ../scripts/seed_phase4_benchmark_data.py --size large --reset    # 1000
```

Makefile: `make seed-phase4-medium`, `make seed-phase4-small`, `make clear-phase4`.

Writes `benchmarks/results/last_seed_manifest.json` for the runner. No OpenAI; Postgres only.

### 3. Run benchmarks (api-service must be up)

Measured JSON only (p50/p95/p99, avg, min, max, cache hits) — no fabricated speedups:

```bash
make benchmark-baseline      # rebuilds api-service with CACHE_ENABLED=false
make benchmark-cold-cache
make benchmark-warm-cache
make benchmark-redis-down    # stops/restarts Redis container automatically
```

Manual equivalent:

```bash
make rebuild-api-baseline
python ../scripts/benchmark_phase4_cache.py --mode baseline --iterations 100

make rebuild-api-cached
python ../scripts/benchmark_phase4_cache.py --mode warm-cache --warmup 20 --iterations 100

python ../scripts/benchmark_phase4_cache.py --mode redis-down --iterations 50
```

Endpoints: `GET .../status`, `routing-decision`, `draft-suggestion`, `events`, `POST /tickets/similar`.

## Migrations (Phase 2 schema)

From `api-service/` (Postgres must be running; host URL uses published port **`5433`**):

```bash
cd api-service
uv sync --extra migrations
export DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets   # PowerShell: $env:DATABASE_URL=...
uv run alembic upgrade head
```

Alembic head includes **`phase2_ticket_persistence`** (tickets, embeddings, routing, events) and **`phase3_draft_suggestions`** (`draft_suggestions` for worker-generated drafts).

## Tests

Integration tests require Postgres with pgvector (same Compose stack):

```bash
cd api-service
uv sync --extra test
export DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets
uv run alembic upgrade head
uv run pytest

cd ../ai-worker
uv sync --extra test
export DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets
export AI_PROVIDER=mock
uv run pytest
```

Phase 3 tests use **`MockAiProvider` only** (`AI_PROVIDER=mock`); no external AI API calls.

## Phase 2 API smoke (provided vectors only)

Create a ticket:

```bash
curl -sS -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"source":"email","subject":"Login issue","body":"Cannot reset password"}'
```

Production embeddings are generated by **ai-worker** only. The endpoint below is **Phase 2 local scaffolding** (not the production path):

Store a **test** embedding (1536 floats — use a JSON file locally; no AI generation in API):

```bash
# Example: generate a placeholder vector in Python, then POST (see OpenAPI /docs)
curl -sS -X POST "http://localhost:8000/tickets/<TICKET_ID>/embeddings/test" \
  -H "Content-Type: application/json" \
  -d @embedding-payload.json
```

Similarity search with a provided query vector:

```bash
curl -sS -X POST http://localhost:8000/tickets/similar \
  -H "Content-Type: application/json" \
  -d @similar-query.json
```

Embedding dimension is fixed at **1536**. Read latest draft suggestion: `GET /tickets/{id}/draft-suggestion`.

**AI worker env (defaults):**

| Variable | Default |
|----------|---------|
| `AI_PROVIDER` | `mock` |
| `OPENAI_API_KEY` | (required when `AI_PROVIDER=openai`) |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `OPENAI_EMBEDDING_DIMENSION` | `1536` |
| `OPENAI_CLASSIFICATION_MODEL` | `gpt-4.1-mini` |
| `OPENAI_SUGGESTION_MODEL` | `gpt-4.1-mini` |
| `RETRIEVAL_TOP_K` | `5` |
| `RETRIEVAL_USABLE_MAX_DISTANCE` | `0.30` |
| `RETRIEVAL_CONTEXT_MAX_AGE_DAYS` | `180` |

Enable OpenAI after setting your key: `AI_PROVIDER=openai` and `OPENAI_API_KEY=...` in `.env` (never commit keys).

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`infrastructure/ecs/README.md`](infrastructure/ecs/README.md) for boundaries and production-oriented notes.
