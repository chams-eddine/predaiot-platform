"""Sprint 3 — governance_records (EDA-GOV-1.0, immutable verification artifacts).

Idempotent like 0002-0007: skips when create_all already made the table.

Revision ID: 0008_governance_records
Revises: 0007_outcomes
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_governance_records"
down_revision = "0007_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "governance_records" in inspect(bind).get_table_names():
        return
    op.create_table(
        "governance_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("governance_id", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("methodology_version", sa.String, nullable=False),
        sa.Column("outcome_id", sa.String, index=True, nullable=True),
        sa.Column("decision_id", sa.String, index=True, nullable=True),
        sa.Column("audit_ids", sa.String, nullable=True),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("verification_confidence", sa.Float, nullable=True),
        sa.Column("verification_confidence_grade", sa.String, nullable=True),
        sa.Column("evidence_hash", sa.String, index=True, nullable=True),
        sa.Column("verifier_user_id", sa.Integer, nullable=True),
        sa.Column("verifier_email", sa.String, nullable=True),
        sa.Column("verifier_role", sa.String, nullable=True),
        sa.Column("at", sa.DateTime, index=True, nullable=False),
        sa.Column("prev_hash", sa.String, nullable=False),
        sa.Column("row_hash", sa.String, index=True, nullable=False),
        sa.Column("record_json", sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("governance_records")
