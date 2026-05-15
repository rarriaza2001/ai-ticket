-- Used when the Postgres image includes pgvector (e.g. pgvector/pgvector:pg16) and this
-- directory is mounted to /docker-entrypoint-initdb.d. Not used by the default postgres:16-bookworm service.
-- pgvector extension for embedding columns (Phase 2 schema).
CREATE EXTENSION IF NOT EXISTS vector;
