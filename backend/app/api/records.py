# -*- coding: utf-8 -*-
"""Audit-history & economic-memory API router — org-scoped audit records,
Economic States, per-audit decision derivation, and the /api/v1/memory
longitudinal summary. Extracted VERBATIM from main.py (Router Extraction, step 6).
Dependency direction: api -> core + models + schemas + eda_metrics (read-model
builders). No economic math here."""
import json  # noqa: F401
import hashlib  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Request  # noqa: F401
from fastapi.responses import JSONResponse  # noqa: F401

import eda_metrics  # noqa: F401
from app.core.config import SessionLocal  # noqa: F401
from app.core.dependencies import require_user, require_role, require_trial_or_user  # noqa: F401
from app.models import (  # noqa: F401
    AuditRecord, EconomicState, User, TrialLead, Decision, DecisionEvent,
)

router = APIRouter()


@router.get("/api/v1/audits")
async def list_audits(user: User = Depends(require_user)):
    """Org-scoped audit history — newest first, headline Economic State only."""
    db = SessionLocal()
    try:
        rows = (db.query(AuditRecord).filter(AuditRecord.org_id == user.org_id)
                .order_by(AuditRecord.created_at.desc()).limit(100).all())
        return {"audits": [{
            "id": r.id, "created_at": r.created_at.isoformat() + "Z",
            "asset_name": r.asset_name, "asset_type": r.asset_type,
            "filename": r.filename, "input_sha256": r.input_sha256,
            "currency": r.currency,
            "gap_total": r.gap_total, "gap_recoverable": r.gap_recoverable,
            "dqi": r.dqi, "dqi_grade": r.dqi_grade,
            "audit_confidence": r.aei, "confidence_grade": r.aei_grade,
            "top_root_cause": r.top_root_cause,
            "engine_version": r.engine_version,
            "methodology_version": r.methodology_version,
        } for r in rows]}
    finally:
        db.close()


@router.get("/api/v1/audits/{audit_id}")
async def get_audit(audit_id: int, user: User = Depends(require_user)):
    """Reload a past audit's full result (bit-for-bit as originally issued)."""
    db = SessionLocal()
    try:
        r = (db.query(AuditRecord)
             .filter(AuditRecord.id == audit_id, AuditRecord.org_id == user.org_id)
             .first())
        if r is None:
            raise HTTPException(status_code=404, detail={"code": "audit_not_found",
                                "message": "No such audit in your organization."})
        return json.loads(r.result_json)
    finally:
        db.close()


@router.get("/api/v1/audits/{audit_id}/economic-state")
async def audit_economic_state(audit_id: int, user: User = Depends(require_user)):
    """
    EDA-ES-1.0 Economic State for one audit (blueprint Amendment 1, canonical
    object). Derived deterministically from the stored audit result, so it
    works for every audit ever recorded — not only those persisted post-ES.
    Org-scoped; 404 across org boundaries.
    """
    db = SessionLocal()
    try:
        r = (db.query(AuditRecord)
             .filter(AuditRecord.id == audit_id, AuditRecord.org_id == user.org_id)
             .first())
        if r is None:
            raise HTTPException(status_code=404, detail={"code": "audit_not_found",
                                "message": "No such audit in your organization."})
        audit = json.loads(r.result_json)
        state = eda_metrics.build_economic_state(audit)
        state["audit_id"] = r.id
        return state
    finally:
        db.close()


@router.get("/api/v1/economic-states")
async def list_economic_states(user: User = Depends(require_user)):
    """Org-scoped Economic State register (EDA-ES-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(EconomicState).filter(EconomicState.org_id == user.org_id)
                .order_by(EconomicState.created_at.desc()).limit(100).all())
        return {"economic_states": [{
            "id": s.id, "audit_id": s.audit_id, "version": s.version,
            "currency": s.currency, "window_start": s.window_start, "window_end": s.window_end,
            "span_hours": s.span_hours, "captured_value": s.captured_value,
            "economic_potential": s.economic_potential, "leakage_rate": s.leakage_rate,
            "recoverable_value": s.recoverable_value, "dqi": s.dqi,
            "audit_confidence": s.audit_confidence, "economic_health": s.economic_health,
            "economic_health_grade": s.economic_health_grade, "provisional": s.provisional,
            "evidence_sha256": s.evidence_sha256,
            "created_at": s.created_at.isoformat() + "Z",
        } for s in rows]}
    finally:
        db.close()


@router.get("/api/v1/audits/{audit_id}/decisions")
async def audit_decisions(audit_id: int, user: User = Depends(require_user)):
    """
    EDA-DEC-1.0 decisions for one audit — economic commitments derived
    deterministically from the audit's Economic State + ledger. Works for every
    stored audit (derives on the fly). Org-scoped; 404 across org boundaries.
    """
    db = SessionLocal()
    try:
        r = (db.query(AuditRecord)
             .filter(AuditRecord.id == audit_id, AuditRecord.org_id == user.org_id)
             .first())
        if r is None:
            raise HTTPException(status_code=404, detail={"code": "audit_not_found",
                                "message": "No such audit in your organization."})
        audit = json.loads(r.result_json)
        es = eda_metrics.build_economic_state(audit)
        decisions = eda_metrics.build_decisions(audit, es, audit_id=r.id)
        return {"audit_id": r.id, "count": len(decisions), "decisions": decisions}
    finally:
        db.close()

@router.get("/api/v1/memory")
async def economic_memory(user: User = Depends(require_user)):
    """
    Economic Memory v1 (L3, blueprint law 4 — learn from stored Economic
    States). Deterministic aggregations of this organization's audit history;
    every figure states its method. No modelling, no weights, no projections.
    """
    db = SessionLocal()
    try:
        rows = (db.query(AuditRecord).filter(AuditRecord.org_id == user.org_id)
                .order_by(AuditRecord.created_at.asc()).all())
        if not rows:
            return {"audits": 0, "note": "No audit history yet — run an audit while signed in."}
        currencies = sorted({r.currency for r in rows if r.currency})
        single_ccy = currencies[0] if len(currencies) == 1 else None
        dqis = [r.dqi for r in rows if r.dqi is not None]
        rc_counts: Dict[str, int] = {}
        for r in rows:
            if r.top_root_cause:
                rc_counts[r.top_root_cause] = rc_counts.get(r.top_root_cause, 0) + 1
        recurring = max(rc_counts.items(), key=lambda kv: kv[1]) if rc_counts else None
        return {
            "method_note": "All values are deterministic aggregations (count/sum/mean) of stored audit results.",
            "audits": len(rows),
            "first_audit": rows[0].created_at.isoformat() + "Z",
            "last_audit": rows[-1].created_at.isoformat() + "Z",
            "currency": single_ccy,
            # Sums are only meaningful in one currency — never mix units.
            "total_gap_identified": (round(sum(r.gap_total or 0 for r in rows), 2)
                                     if single_ccy else None),
            "total_recoverable_identified": (round(sum(r.gap_recoverable or 0 for r in rows), 2)
                                             if single_ccy else None),
            "mean_dqi": round(sum(dqis) / len(dqis), 4) if dqis else None,
            "latest_dqi": rows[-1].dqi, "latest_dqi_grade": rows[-1].dqi_grade,
            "recurring_top_root_cause": ({"cause": recurring[0], "audits": recurring[1]}
                                         if recurring else None),
            "assets_audited": sorted({r.asset_name for r in rows if r.asset_name}),
            "mixed_currencies": currencies if not single_ccy and currencies else None,
        }
    finally:
        db.close()
