"""Baseline — schema as created by Base.metadata.create_all() at Sprint 1.

The v1 schema (audit_logs, trial_leads, api_access_log, certificate_registry,
organizations, users, assets) is created by create_all() on startup plus the
idempotent additive-column migration in main._apply_additive_migrations.
This revision exists so every FUTURE schema change is an Alembic revision;
`alembic stamp 0001_baseline` marks an existing database as current.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-11

"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally empty: baseline of the pre-Alembic schema.
    pass


def downgrade() -> None:
    pass
