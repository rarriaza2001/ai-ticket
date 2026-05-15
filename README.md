# AI Support Ticket Triage — Phase 1 foundation

Two Python services plus **neutral** shared schemas:

- **`api-service/`** — FastAPI: `/health`, `/ready`, SQLAlchemy async sessions, Redis client, structured logging, centralized errors, access middleware.
- **`ai-worker/`** — Background process: SQLAlchemy + Redis connectivity check, stub idle loop.
- **`shared-contracts/`** — `HealthResponse` and `ReadinessResponse` only (no ticket/queue/AI contracts yet).

Postgres is **authoritative** for future data. Redis is **non-authoritative** (wired for readiness and future cache only).

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

The default Compose file uses **`postgres:16-bookworm`** so you only pull the official Postgres image (same registry as `redis:7-alpine`). If even that fails, the issue is general Docker Hub access from your environment.

### Postgres image variants

- **Default** in [`docker/docker-compose.yml`](docker/docker-compose.yml): `postgres:16-bookworm` — enough for Phase 1 (`/ready` runs `SELECT 1` only).
- **Optional pgvector** (when Docker Hub works): change the `postgres` service to `image: pgvector/pgvector:pg16` and add a read-only volume mount for [`docker/postgres/init/`](docker/postgres/init/) so `CREATE EXTENSION vector` runs on first init. Use a **fresh** named volume if you switch images so init scripts run again.

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

## Migrations (tooling only)

From `api-service/`:

```bash
uv sync --extra migrations
uv run alembic upgrade head
```

Phase 1 keeps a **no-op** revision; application tables arrive in Phase 2.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`infrastructure/ecs/README.md`](infrastructure/ecs/README.md) for boundaries and production-oriented notes (ECS is documentation-only in Phase 1).
