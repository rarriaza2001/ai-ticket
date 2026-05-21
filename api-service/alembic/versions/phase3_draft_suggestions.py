"""Phase 3 draft suggestions for worker-generated AI drafts.

Revision ID: phase3_draft_suggestions
Revises: phase2_ticket_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase3_draft_suggestions"
down_revision: str | Sequence[str] | None = "phase2_ticket_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUGGESTION_STATUSES = ("pending_review", "superseded", "failed")


def upgrade() -> None:
    op.create_table(
        "draft_suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column(
            "requires_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending_review', 'superseded', 'failed')",
            name="ck_draft_suggestions_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_draft_suggestions_confidence_range",
        ),
    )
    op.create_index(
        "ix_draft_suggestions_ticket_id_created_at",
        "draft_suggestions",
        ["ticket_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "uq_draft_suggestions_one_pending_review_per_ticket",
        "draft_suggestions",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending_review'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_draft_suggestions_one_pending_review_per_ticket",
        table_name="draft_suggestions",
    )
    op.drop_index(
        "ix_draft_suggestions_ticket_id_created_at",
        table_name="draft_suggestions",
    )
    op.drop_table("draft_suggestions")
