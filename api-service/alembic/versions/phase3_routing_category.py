"""Allow category in routing_decisions decision_type.

Revision ID: phase3_routing_category
Revises: phase3_draft_suggestions
"""

from collections.abc import Sequence

from alembic import op

revision: str = "phase3_routing_category"
down_revision: str | Sequence[str] | None = "phase3_draft_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECISION_TYPES = ("team", "priority", "escalation", "category")


def upgrade() -> None:
    op.drop_constraint(
        "ck_routing_decisions_decision_type",
        "routing_decisions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_routing_decisions_decision_type",
        "routing_decisions",
        f"decision_type IN ({', '.join(repr(d) for d in DECISION_TYPES)})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_routing_decisions_decision_type",
        "routing_decisions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_routing_decisions_decision_type",
        "routing_decisions",
        "decision_type IN ('team', 'priority', 'escalation')",
    )
