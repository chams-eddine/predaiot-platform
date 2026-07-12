"""Sprint 3 — outcomes (EDA-OUT-1.0, measured realized impact).

Idempotent like 0002-0006: skips when create_all already made the table.

Revision ID: 0007_outcomes
Revises: 0006_decision_events
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_outcomes"
down_revision = "0006_decision_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "outcomes" in inspect(bind).get_table_names():
        return
    op.create_table(
        "outcomes",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("decision_pk", sa.Integer, index=True, nullable=False),
        sa.Column("decision_id", sa.String, index=True, nullable=False),
        sa.Column("outcome_id", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("verification_audit_id", sa.Integer, index=True, nullable=True),
        sa.Column("root_cause_id", sa.String, nullable=True),
        sa.Column("currency", sa.String, nullable=True),
        sa.Column("realized_value", sa.Float, nullable=True),
        sa.Column("outcome_status", sa.String, nullable=False),
        sa.Column("confidence_aei", sa.Float, nullable=True),
        sa.Column("confidence_dqi", sa.Float, nullable=True),
        sa.Column("evidence_hash", sa.String, index=True, nullable=True),
        sa.Column("measured_by", sa.Integer, nullable=True),
        sa.Column("outcome_json", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outcomes")
