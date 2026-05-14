"""Phase 1 placeholder revision (no DDL).

Tables, pgvector columns, and indexes arrive in Phase 2.

"""

from collections.abc import Sequence

revision: str = "phase1_placeholder"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
