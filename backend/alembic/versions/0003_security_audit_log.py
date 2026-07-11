"""Sprint 2 Feature 3 — hash-chained security_audit_log (tamper-evident).

Idempotent like 0002: skips when create_all already made the table.

Revision ID: 0003_security_audit_log
Revises: 0002_audit_records
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_security_audit_log"
down_revision = "0002_audit_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "security_audit_log" in inspect(bind).get_table_names():
        return
    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("org_id", sa.Integer, index=True, nullable=True),
        sa.Column("actor", sa.String, nullable=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("object_ref", sa.String, nullable=True),
        sa.Column("at", sa.DateTime, index=True, nullable=False),
        sa.Column("prev_hash", sa.String, nullable=False),
        sa.Column("row_hash", sa.String, nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("security_audit_log")
