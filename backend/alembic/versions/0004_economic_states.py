"""Sprint 3 — economic_states (EDA-ES-1.0, canonical business object).

Idempotent like 0002/0003: skips when create_all already made the table.

Revision ID: 0004_economic_states
Revises: 0003_security_audit_log
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_economic_states"
down_revision = "0003_security_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "economic_states" in inspect(bind).get_table_names():
        return
    op.create_table(
        "economic_states",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("audit_id", sa.Integer, index=True, nullable=True),
        sa.Column("asset_id", sa.Integer, index=True, nullable=True),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("currency", sa.String, nullable=True),
        sa.Column("window_start", sa.String, nullable=True),
        sa.Column("window_end", sa.String, nullable=True),
        sa.Column("span_hours", sa.Float, nullable=True),
        sa.Column("captured_value", sa.Float, nullable=True),
        sa.Column("economic_potential", sa.Float, nullable=True),
        sa.Column("leakage_rate", sa.Float, nullable=True),
        sa.Column("recoverable_value", sa.Float, nullable=True),
        sa.Column("dqi", sa.Float, nullable=True),
        sa.Column("audit_confidence", sa.Float, nullable=True),
        sa.Column("economic_health", sa.Float, nullable=True),
        sa.Column("economic_health_grade", sa.String, nullable=True),
        sa.Column("provisional", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("evidence_sha256", sa.String, index=True, nullable=True),
        sa.Column("state_json", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("economic_states")
