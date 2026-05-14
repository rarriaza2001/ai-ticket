"""Database access uses `asyncpg` pool stored on `app.state.db_pool` (see `app.main` lifespan).

Alembic migrations use the synchronous SQLAlchemy URL derived from `Settings.sqlalchemy_sync_url`.
"""
