"""Reconcile Alembic to the models — fix the historic baseline drift.

Historic drift (proven 2026-07-23): `0001_baseline` was intentionally EMPTY and
the core tables (users, organizations, assets, certificate_registry, trial_leads,
facility_memberships, api_access_log, audit_logs) plus two additive columns
(trial_leads.user_id, assets.flexibility_factor) were only ever created by
`create_all()` + `_apply_additive_migrations`, never captured as revisions. So
`alembic upgrade head` on a fresh database built 10 of 18 tables — Alembic was
decorative.

This revision makes Alembic AUTHORITATIVE by reconciling ANY database to the full
models schema, idempotently:
  1. `Base.metadata.create_all()` creates any missing TABLES (no-op on an existing
     / production DB — create_all never drops or alters, only creates-if-absent);
  2. inspector-guarded `add_column` adds the additive columns to tables that
     pre-existed the column.

Safety: additive + non-destructive ONLY. It never drops or alters an existing
column and never touches data. On the live production DB (already complete, stamped
0010) running this is a pure no-op that advances the stamp to 0011. `downgrade` is a
deliberate no-op — we never auto-drop customer tables or columns.

Revision ID: 0011_reconcile_models
Revises: 0010_reconciliations
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_reconcile_models"
down_revision = "0010_reconciliations"
branch_labels = None
depends_on = None

# Additive columns historically applied outside Alembic (main._apply_additive_migrations).
# Now captured here so a from-scratch `alembic upgrade head` matches the models.
_ADDITIVE = {
    "certificate_registry": [("dqi_grade", sa.String()), ("confidence_grade", sa.String())],
    "trial_leads": [("user_id", sa.Integer())],
    "assets": [("flexibility_factor", sa.Float())],
}


def upgrade() -> None:
    bind = op.get_bind()
    # 1) Create any missing tables straight from the models (single source of
    #    truth). Idempotent: create_all only creates tables that do not exist.
    import main  # exposes Base.metadata; already imported by alembic/env.py
    main.Base.metadata.create_all(bind=bind)

    # 2) Additive columns on tables that pre-existed the column (guarded so this
    #    is a no-op wherever the column already exists — e.g. production).
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table, cols in _ADDITIVE.items():
        if table not in tables:
            continue  # create_all above will have made it with all columns
        have = {c["name"] for c in insp.get_columns(table)}
        for name, coltype in cols:
            if name not in have:
                op.add_column(table, sa.Column(name, coltype, nullable=True))


def downgrade() -> None:
    # Deliberate no-op: reconciliation is forward-only and non-destructive. We
    # never auto-drop customer tables or columns (Production-Readiness rule).
    pass
