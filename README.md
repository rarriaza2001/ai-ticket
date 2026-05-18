# AI Support Ticket Triage — Phase 2 persistence

Two Python services plus **neutral** shared schemas:

- **`api-service/`** — FastAPI: health/readiness plus **ticket persistence** (intake, embeddings, routing decisions, audit events, similarity search with caller-provided vectors).
- **`ai-worker/`** — Background process: SQLAlchemy + Redis connectivity check, stub idle loop (no job processing in Phase 2).
- **`shared-contracts/`** — `HealthResponse` and `ReadinessResponse` only (ticket HTTP schemas live in api-service).

Postgres is **authoritative** for ticket data. Redis is **non-authoritative** (readiness probe only in Phase 2).

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

## Configuration

Required for both services: **`DATABASE_URL`**, **`REDIS_URL`**.

Optional: `LOG_LEVEL`, `ENV`, `SERVICE_NAME`, and pool tuning `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS` (api-service; see [`app/core/config.py`](api-service/app/core/config.py)).

Examples: [`docker/.env.example`](docker/.env.example), [`infrastructure/env/.env.example`](infrastructure/env/.env.example).

## Migrations (Phase 2 schema)

From `api-service/` (Postgres must be running; default host URL uses published port `5432`):

```bash
cd api-service
uv sync --extra migrations
export DATABASE_URL=postgresql://ticket:ticket@localhost:5433/tickets   # PowerShell: $env:DATABASE_URL=...
uv run alembic upgrade head
```

Head revision **`phase2_ticket_persistence`** creates the `vector` extension and tables: `tickets`, `ticket_embeddings`, `routing_decisions`, `ticket_events`.

## Tests

Integration tests require Postgres with pgvector (same Compose stack):

```bash
cd api-service
uv sync --extra test
export DATABASE_URL=postgresql://ticket:ticket@localhost:5432/tickets
uv run pytest
```

## Phase 2 API smoke (provided vectors only)

Create a ticket:

```bash
curl -sS -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"source":"email","subject":"Login issue","body":"Cannot reset password"}'
```

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

Embedding dimension is fixed at **1536** for Phase 2 (`persistence-placeholder` model name).

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`infrastructure/ecs/README.md`](infrastructure/ecs/README.md) for boundaries and production-oriented notes.
