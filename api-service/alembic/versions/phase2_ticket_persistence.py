"""Phase 2 ticket persistence: tickets, embeddings, routing, audit.

Revision ID: phase2_ticket_persistence
Revises: phase1_placeholder
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.embedding import EMBEDDING_DIMENSION

revision: str = "phase2_ticket_persistence"
down_revision: str | Sequence[str] | None = "phase1_placeholder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TICKET_STATUSES = (
    "received",
    "pending_embedding",
    "embedded",
    "routing_pending",
    "routed",
    "failed",
)
TICKET_PRIORITIES = ("low", "normal", "high", "urgent")
DECISION_TYPES = ("team", "priority", "escalation")
DECIDED_BY_VALUES = ("worker", "manual", "test_seed")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("customer_email", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in TICKET_STATUSES)})",
            name="ck_tickets_status",
        ),
        sa.CheckConstraint(
            f"priority IS NULL OR priority IN ({', '.join(repr(p) for p in TICKET_PRIORITIES)})",
            name="ck_tickets_priority",
        ),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_index(
        "uq_tickets_source_external_id",
        "tickets",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "ticket_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("source_text_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("embedding_dimension > 0", name="ck_ticket_embeddings_dimension"),
    )
    op.create_index("ix_ticket_embeddings_ticket_id", "ticket_embeddings", ["ticket_id"])
    op.create_index("ix_ticket_embeddings_is_active", "ticket_embeddings", ["is_active"])
    op.create_index(
        "uq_ticket_embeddings_one_active_per_ticket",
        "ticket_embeddings",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )
    op.execute(
        """
        CREATE INDEX ix_ticket_embeddings_embedding_hnsw
        ON ticket_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )

    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("route_to", sa.Text(), nullable=False),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"decision_type IN ({', '.join(repr(d) for d in DECISION_TYPES)})",
            name="ck_routing_decisions_decision_type",
        ),
        sa.CheckConstraint(
            f"decided_by IN ({', '.join(repr(d) for d in DECIDED_BY_VALUES)})",
            name="ck_routing_decisions_decided_by",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_routing_decisions_confidence",
        ),
    )
    op.create_index(
        "ix_routing_decisions_ticket_id_created_at",
        "routing_decisions",
        ["ticket_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_routing_decisions_route_to", "routing_decisions", ["route_to"])

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_events_ticket_id_created_at",
        "ticket_events",
        ["ticket_id", "created_at"],
    )
    op.create_index("ix_ticket_events_event_type", "ticket_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_ticket_events_event_type", table_name="ticket_events")
    op.drop_index("ix_ticket_events_ticket_id_created_at", table_name="ticket_events")
    op.drop_table("ticket_events")

    op.drop_index("ix_routing_decisions_route_to", table_name="routing_decisions")
    op.drop_index("ix_routing_decisions_ticket_id_created_at", table_name="routing_decisions")
    op.drop_table("routing_decisions")

    op.execute("DROP INDEX IF EXISTS ix_ticket_embeddings_embedding_hnsw")
    op.drop_index(
        "uq_ticket_embeddings_one_active_per_ticket",
        table_name="ticket_embeddings",
    )
    op.drop_index("ix_ticket_embeddings_is_active", table_name="ticket_embeddings")
    op.drop_index("ix_ticket_embeddings_ticket_id", table_name="ticket_embeddings")
    op.drop_table("ticket_embeddings")

    op.drop_index("uq_tickets_source_external_id", table_name="tickets")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_table("tickets")

    op.execute("DROP EXTENSION IF EXISTS vector")
