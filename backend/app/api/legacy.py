# -*- coding: utf-8 -*-
"""Legacy/compat API router — pre-v1 endpoints kept for frontend compatibility:
/api/historical (30-day gap history), /api/latest (caller's most recent audit,
tenant-scoped). Extracted VERBATIM from main.py (Router Extraction, step 6).

Dependency direction: api -> core (config, state, dependencies) + models +
schemas. NOTE: /api/v1/integrations/mqtt/status intentionally NOT here — it reads
the MQTT bridge's rebound module globals and stays with the bridge in main until
that cluster moves as a whole.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.config import DATABASE_URL, SessionLocal
from app.core.dependencies import require_trial_or_user
from app.core.state import _EMPTY_LATEST, _latest_by_token
from app.models import TrialLead
from app.schemas import DecisionRecord, HistoricalResponse

router = APIRouter()


@router.get("/api/historical", response_model=HistoricalResponse)
async def get_historical_data():
    db = SessionLocal()
    try:
        if "sqlite" in DATABASE_URL:
            return HistoricalResponse(history_log=[])
        result = db.execute(text(
            "SELECT DATE(timestamp) AS day, SUM(economic_gap) as daily_gap "
            "FROM audit_logs WHERE timestamp > NOW() - INTERVAL '30 days' "
            "GROUP BY DATE(timestamp) ORDER BY day DESC"
        ))
        return HistoricalResponse(history_log=[
            DecisionRecord(day=row.day.strftime("%Y-%m-%d"), daily_gap=round(row.daily_gap, 2))
            for row in result if row.daily_gap
        ])
    finally:
        db.close()


@router.get("/api/latest")
async def get_latest_live_data(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Returns the caller's most recent audit result. Gated on the trial token
    per the tenant-isolation fix — previously this endpoint returned the
    process-global `latest_live_result` and leaked between callers.
    """
    return _latest_by_token.get(lead.token, _EMPTY_LATEST)
