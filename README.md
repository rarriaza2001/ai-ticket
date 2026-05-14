# AI Support Ticket Triage — Phase 1 scaffolding

This repository hosts two Python services plus shared contracts:

- `api-service/` — FastAPI HTTP intake, thin routes, Postgres + Redis connectivity.
- `ai-worker/` — background worker shell (embeddings / routing / retrieval in Phase 2).
- `shared-contracts/` — Pydantic DTOs, enums, and queue-related protocols.

Authoritative state is **PostgreSQL** (with **pgvector** enabled in local Compose). **Redis** is **not** source of truth: cache and coordination only; failure degrades behavior without blocking core intake once Phase 2 exists.

## Local development (Docker Compose)

Prerequisites: Docker Desktop (or Docker Engine) and optionally [uv](https://github.com/astral-sh/uv) for host-side tooling.

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env.example up --build
```

API: `http://localhost:8000` (see `GET /health`, `GET /ready`, OpenAPI at `/docs`).

Ticket routes intentionally return **501 Not Implemented** in Phase 1 while contracts and OpenAPI are wired.

## Configuration

See [`infrastructure/env/.env.example`](infrastructure/env/.env.example) and [`docker/.env.example`](docker/.env.example). Required variables for services: `DATABASE_URL`, `REDIS_URL`.

## Migrations (placeholder)

From `api-service/` after installing migration extras:

```bash
uv sync --extra migrations
uv run alembic upgrade head
```

Phase 1 ships a no-op revision; real DDL lands in Phase 2.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`infrastructure/ecs/README.md`](infrastructure/ecs/README.md) for service boundaries, failure modes, and ECS-oriented deployment assumptions.
