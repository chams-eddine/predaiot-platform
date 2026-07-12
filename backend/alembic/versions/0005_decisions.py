"""Sprint 3 — decisions (EDA-DEC-1.0, economic commitments).

Idempotent like 0002-0004: skips when create_all already made the table.

Revision ID: 0005_decisions
Revises: 0004_economic_states
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_decisions"
down_revision = "0004_economic_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "decisions" in inspect(bind).get_table_names():
        return
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("audit_id", sa.Integer, index=True, nullable=True),
        sa.Column("asset_id", sa.Integer, index=True, nullable=True),
        sa.Column("decision_id", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("decision_type", sa.String, nullable=True),
        sa.Column("root_cause_id", sa.String, nullable=True),
        sa.Column("economic_state_version", sa.String, nullable=True),
        sa.Column("expected_value", sa.Float, nullable=True),
        sa.Column("currency", sa.String, nullable=True),
        sa.Column("decision_mode", sa.String, nullable=True),
        sa.Column("governance_owner_role", sa.String, nullable=True),
        sa.Column("governance_owner_user_id", sa.Integer, nullable=True),
        sa.Column("decision_evidence_sha256", sa.String, index=True, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="proposed"),
        sa.Column("status_by", sa.Integer, nullable=True),
        sa.Column("status_at", sa.DateTime, nullable=True),
        sa.Column("decision_json", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("decisions")
