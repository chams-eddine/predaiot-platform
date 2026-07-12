"""Sprint 3 — decision_events (EDA-DEC-LIFE-1.0, immutable lifecycle log).

Idempotent like 0002-0005: skips when create_all already made the table.

Revision ID: 0006_decision_events
Revises: 0005_decisions
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_decision_events"
down_revision = "0005_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "decision_events" in inspect(bind).get_table_names():
        return
    op.create_table(
        "decision_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("decision_pk", sa.Integer, index=True, nullable=False),
        sa.Column("decision_id", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("from_state", sa.String, nullable=True),
        sa.Column("to_state", sa.String, nullable=False),
        sa.Column("actor_user_id", sa.Integer, nullable=True),
        sa.Column("actor_email", sa.String, nullable=True),
        sa.Column("note", sa.String, nullable=True),
        sa.Column("decision_evidence_sha256", sa.String, nullable=True),
        sa.Column("at", sa.DateTime, index=True, nullable=False),
        sa.Column("prev_hash", sa.String, nullable=False),
        sa.Column("row_hash", sa.String, index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("decision_events")
