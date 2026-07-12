"""Live Economic Pipeline — live_events + live_states (RT-2..RT-5).

Idempotent like 0002-0008: skips tables create_all already made.

Revision ID: 0009_live_pipeline
Revises: 0008_governance_records
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_live_pipeline"
down_revision = "0008_governance_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "live_events" not in tables:
        op.create_table(
            "live_events",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("org_id", sa.Integer, index=True, nullable=False),
            sa.Column("stream_id", sa.String, index=True, nullable=False),
            sa.Column("event_id", sa.String, index=True, nullable=False),
            sa.Column("source", sa.String, nullable=True),
            sa.Column("timestamp", sa.String, nullable=True),
            sa.Column("spot_price", sa.Float, nullable=True),
            sa.Column("actual_charge", sa.Float, nullable=True),
            sa.Column("actual_discharge", sa.Float, nullable=True),
            sa.Column("soc_percent", sa.Float, nullable=True),
            sa.Column("forecast_price", sa.Float, nullable=True),
            sa.Column("currency", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, index=True, nullable=False),
        )
    if "live_states" not in tables:
        op.create_table(
            "live_states",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("org_id", sa.Integer, index=True, nullable=False),
            sa.Column("stream_id", sa.String, index=True, unique=True, nullable=False),
            sa.Column("updated_at", sa.DateTime, index=True, nullable=False),
            sa.Column("n_events", sa.Integer, nullable=True),
            sa.Column("state_json", sa.String, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("live_states")
    op.drop_table("live_events")
