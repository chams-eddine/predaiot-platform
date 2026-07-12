"""Live Reconciliation — reconciliations (EDA-RECON-1.0, certification bridge).

Idempotent like 0002-0009: skips when create_all already made the table.

Revision ID: 0010_reconciliations
Revises: 0009_live_pipeline
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010_reconciliations"
down_revision = "0009_live_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "reconciliations" in inspect(bind).get_table_names():
        return
    op.create_table(
        "reconciliations",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("reconciliation_id", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("stream_id", sa.String, index=True, nullable=False),
        sa.Column("live_state_id", sa.Integer, index=True, nullable=True),
        sa.Column("certified_audit_id", sa.Integer, index=True, nullable=True),
        sa.Column("provisional_hash", sa.String, nullable=True),
        sa.Column("certified_hash", sa.String, nullable=True),
        sa.Column("variance_leakage_abs", sa.Float, nullable=True),
        sa.Column("variance_leakage_pct", sa.Float, nullable=True),
        sa.Column("currency", sa.String, nullable=True),
        sa.Column("reconciliation_status", sa.String, nullable=False),
        sa.Column("verifier_user_id", sa.Integer, nullable=True),
        sa.Column("verifier_email", sa.String, nullable=True),
        sa.Column("verifier_role", sa.String, nullable=True),
        sa.Column("evidence_hash", sa.String, index=True, nullable=True),
        sa.Column("at", sa.DateTime, index=True, nullable=False),
        sa.Column("prev_hash", sa.String, nullable=False),
        sa.Column("row_hash", sa.String, index=True, nullable=False),
        sa.Column("reconciliation_json", sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reconciliations")
