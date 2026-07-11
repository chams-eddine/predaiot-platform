"""Sprint 2 Feature 1 — audit_records (L3 Economic Knowledge Layer).

Idempotent: production creates tables via Base.metadata.create_all() at
startup, so this revision only creates the table when it is absent (fresh
environments running `alembic upgrade head` get it here instead).

Revision ID: 0002_audit_records
Revises: 0001_baseline
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_audit_records"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "audit_records" in inspect(bind).get_table_names():
        return
    op.create_table(
        "audit_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=False),
        sa.Column("user_id", sa.Integer, index=True, nullable=False),
        sa.Column("asset_id", sa.Integer, index=True, nullable=True),
        sa.Column("asset_name", sa.String, nullable=True),
        sa.Column("asset_type", sa.String, nullable=True),
        sa.Column("input_sha256", sa.String, index=True, nullable=False),
        sa.Column("filename", sa.String, nullable=True),
        sa.Column("engine_version", sa.String, nullable=True),
        sa.Column("methodology_version", sa.String, nullable=True),
        sa.Column("currency", sa.String, nullable=True),
        sa.Column("gap_total", sa.Float, nullable=True),
        sa.Column("gap_recoverable", sa.Float, nullable=True),
        sa.Column("dqi", sa.Float, nullable=True),
        sa.Column("dqi_grade", sa.String, nullable=True),
        sa.Column("aei", sa.Float, nullable=True),
        sa.Column("aei_grade", sa.String, nullable=True),
        sa.Column("top_root_cause", sa.String, nullable=True),
        sa.Column("result_json", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_records")
