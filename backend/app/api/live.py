# -*- coding: utf-8 -*-
"""Live-pipeline REST API router — telemetry ingest, windowed live state,
reconciliation (create/list/verify), certified state. Extracted VERBATIM from
main.py (Router Extraction, step 6). NOTE: /ws/live + /api/v1/live/step +
the MQTT bridge stay in main (they share the simulator's rebound module state;
they move together later).
Dependency direction: api -> core + models + schemas + services + canonical_event."""
import hashlib  # noqa: F401
import hashlib as _hashlib  # noqa: F401  (main.py aliases hashlib; verbatim bodies use it)
import json  # noqa: F401
import os  # noqa: F401
from datetime import datetime  # noqa: F401
from typing import Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Request  # noqa: F401
from fastapi.responses import JSONResponse  # noqa: F401

import canonical_event  # noqa: F401
import eda_metrics  # noqa: F401
from app.core.config import SessionLocal  # noqa: F401
from app.core.dependencies import (  # noqa: F401
    require_audit_runner, require_role, require_trial_or_user, require_user,
)
from app.repositories.security_log import _security_log  # noqa: F401
from app.core.ratelimit import limiter  # noqa: F401
from app.models import (  # noqa: F401
    AuditRecord, LiveEvent, LiveState, Reconciliation, TrialLead, User,
)
from app.schemas import AssetSpecs, LiveIngestRequest, ReconcileRequest  # noqa: F401
from app.services.audit_service import process_calculation  # noqa: F401
from app.services.optimization_service import _MILP_LAST  # noqa: F401
from app.services.telemetry_service import _live_decision_core  # noqa: F401

router = APIRouter()


# ==========================================================================
# LIVE ECONOMIC PIPELINE (RT-2 … RT-5) — ONE engine, reused. No parallel audit.
#   Canonical Events → Window Builder → DQ Gate → EXISTING Layer-2 engine →
#   provisional Economic State → refreshed live Decisions.
# Every live state is provisional=true until a certified batch audit confirms.
# ==========================================================================


_LIVE_WINDOW = int(os.environ.get("PREDAIOT_LIVE_WINDOW", "48"))


def _recompute_live_state(db, org_id: int, stream_id: str,
                          asset_id: Optional[int], currency: str) -> dict:
    """
    Rolling-window recompute through the EXISTING certified Layer-2 engine.
    Returns the new PROVISIONAL Economic State (+ top live decision). This
    function performs NO economics of its own — it only assembles the window
    and calls process_calculation() + eda_metrics, the same code the CSV audit
    path uses.
    """
    rows = (db.query(LiveEvent)
            .filter(LiveEvent.org_id == org_id, LiveEvent.stream_id == stream_id)
            .order_by(LiveEvent.id.desc()).limit(_LIVE_WINDOW * 3).all())
    events = [{"event_id": r.event_id, "timestamp": r.timestamp, "spot_price": r.spot_price,
               "actual_charge": r.actual_charge, "actual_discharge": r.actual_discharge,
               "soc_percent": r.soc_percent, "forecast_price": r.forecast_price} for r in rows]
    window = canonical_event.build_window(events, max_len=_LIVE_WINDOW)
    manifest = canonical_event.window_manifest(window)

    # DQ gate — do not fabricate economics from too little evidence.
    if len(window) < 2:
        state = {"stream_id": stream_id, "provisional": True,
                 "status": "INSUFFICIENT_EVIDENCE", "n_events": len(window),
                 "evidence_sha256": manifest["evidence_sha256"],
                 "window_start": manifest["window_start"], "window_end": manifest["window_end"],
                 "message": "Awaiting sufficient events for a live economic state."}
        return state

    # Build the engine time-series from canonical events (the ONLY bridge to L2).
    time_series = [canonical_event.to_time_step(ev, i) for i, ev in enumerate(window)]
    asset = AssetSpecs(asset_type="storage", asset_name=f"stream:{stream_id}")
    # SAME certified engine as the CSV path — no duplicated calculation.
    result = process_calculation(asset, time_series, save_to_db=False,
                                 dt_hours=1.0, currency=currency)
    audit = result.dict()
    # Attach DQI + Audit Confidence by REUSING the same eda_metrics functions the
    # CSV path uses (no duplicated math). Live windows exclude 'completeness'
    # (N/A — a stream's expected-step count is unknown without the batch interval
    # contract); it is measured honestly on the certified batch audit.
    n_rows = len(window)
    n_forecast = sum(1 for ev in window if ev.get("forecast_price") is not None)
    _components = {
        "completeness": None,
        "timestamp_integrity": eda_metrics.timestamp_integrity(n_rows, 0, 0),
        "sensor_validity": None,
        "telemetry_health": None,
        "price_integrity": eda_metrics.price_integrity(n_rows, 0),
        "forecast_availability": eda_metrics.forecast_availability(
            n_rows if n_forecast else None, n_forecast),
    }
    dqi_obj = eda_metrics.build_dqi(_components)
    _M = eda_metrics.model_consistency(audit.get("dq_score_raw"))
    _solver_proven = (_MILP_LAST.get("status") == "Optimal")
    audit["data_quality_index"] = dqi_obj
    audit["audit_confidence"] = eda_metrics.audit_confidence(dqi_obj.get("value"), _M, _solver_proven)
    es = eda_metrics.build_economic_state(audit)
    es["provisional"] = True                                   # live is always provisional
    es["evidence_sha256"] = manifest["evidence_sha256"]        # window evidence hash
    es["window_start"] = manifest["window_start"]
    es["window_end"] = manifest["window_end"]
    es["n_events"] = manifest["n_events"]
    es["status"] = "PROVISIONAL"
    # Live decision refresh — reuse build_decisions on the live window.
    decisions = eda_metrics.build_decisions(audit, es, audit_id=f"live:{stream_id}")
    top = decisions[0] if decisions else None
    state = {
        "stream_id": stream_id, "provisional": True, "status": "PROVISIONAL",
        "currency": es.get("currency"),
        "live_leakage": audit.get("total_gap_usd"),            # window economic gap
        "leakage_rate": es.get("leakage_rate"),                # currency/hour
        "live_recoverable": es.get("recoverable_value"),
        "economic_health": es.get("economic_health"),
        "dqi": es.get("dqi"), "audit_confidence": es.get("audit_confidence"),
        "confidence_grade": (audit.get("audit_confidence") or {}).get("grade"),
        "n_events": manifest["n_events"],
        "window_start": manifest["window_start"], "window_end": manifest["window_end"],
        "evidence_sha256": manifest["evidence_sha256"],
        "evidence_status": "provisional — not yet certified by a batch audit",
        "top_action": ({"decision_type": top["decision_type"],
                        "statement": top["recommended_action"]["statement"],
                        "value_at_stake": top["expected_value_impact"]["value_at_stake"]}
                       if top else None),
        "economic_state": es,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    return state




@router.post("/api/v1/live/ingest")
async def live_ingest(req: LiveIngestRequest, user: User = Depends(require_audit_runner)):
    """
    Ingest Canonical Economic Events for a stream, persist (deduped), and
    recompute the provisional live Economic State via the EXISTING engine.
    Gated like audit runs (viewer read-only). Trial tokens also accepted for
    demos; account users are org-scoped.
    """
    # Resolve org: account leads carry user_id → org; trial leads → demo bucket 0.
    db = SessionLocal()
    try:
        acct = db.query(User).filter(User.id == user.user_id).first() if getattr(user, "user_id", None) else None
        org_id = acct.org_id if acct else 0
        norm = [canonical_event.normalize_event(e, req.stream_id, req.source, req.currency)
                for e in req.events]
        valid = [e for e in norm if canonical_event.event_is_valid(e)]
        # Persist deduped (skip event_ids already stored for this stream+org).
        existing = {r.event_id for r in db.query(LiveEvent.event_id)
                    .filter(LiveEvent.org_id == org_id, LiveEvent.stream_id == req.stream_id)
                    .order_by(LiveEvent.id.desc()).limit(_LIVE_WINDOW * 3).all()}
        added = 0
        for e in valid:
            if e["event_id"] in existing:
                continue
            db.add(LiveEvent(org_id=org_id, stream_id=req.stream_id, event_id=e["event_id"],
                             source=e["source"], timestamp=e["timestamp"], spot_price=e["spot_price"],
                             actual_charge=e["actual_charge"], actual_discharge=e["actual_discharge"],
                             soc_percent=e["soc_percent"], forecast_price=e["forecast_price"],
                             currency=e["currency"]))
            added += 1
        db.commit()
        state = _recompute_live_state(db, org_id, req.stream_id, req.asset_id, req.currency)
        # Upsert the current live state for the stream.
        ls = db.query(LiveState).filter(LiveState.org_id == org_id,
                                        LiveState.stream_id == req.stream_id).first()
        if ls is None:
            ls = LiveState(org_id=org_id, stream_id=req.stream_id)
            db.add(ls)
        ls.updated_at = datetime.utcnow()
        ls.n_events = state.get("n_events")
        ls.state_json = json.dumps(state, default=str)
        db.commit()
        return {"accepted": len(valid), "persisted": added, "state": state}
    finally:
        db.close()


@router.get("/api/v1/live/state")
async def live_state(stream_id: str, user: User = Depends(require_trial_or_user)):
    """Current provisional live Economic State for a stream (the dashboard polls this)."""
    db = SessionLocal()
    try:
        acct = db.query(User).filter(User.id == user.user_id).first() if getattr(user, "user_id", None) else None
        org_id = acct.org_id if acct else 0
        ls = db.query(LiveState).filter(LiveState.org_id == org_id,
                                        LiveState.stream_id == stream_id).first()
        if ls is None:
            return {"stream_id": stream_id, "status": "NO_STREAM",
                    "message": "No live state yet for this stream."}
        return json.loads(ls.state_json)
    finally:
        db.close()


# ---- EDA-RECON-1.0 — Live Reconciliation (certification bridge) -------------

_RECON_ROLES = {"owner", "admin", "asset_manager"}


def _recon_dict(r: "Reconciliation") -> dict:
    return json.loads(r.reconciliation_json)


@router.post("/api/v1/live/{stream_id}/reconcile")
async def reconcile_live(stream_id: str, req: ReconcileRequest,
                         user: User = Depends(require_user)):
    """
    Certification bridge: bind the stream's provisional live Economic State to a
    CERTIFIED batch audit, disclosing the variance. Append-only; no
    recomputation; certified stays authoritative. RBAC owner/admin/asset_manager.
    """
    if user.role != "owner" and user.role not in _RECON_ROLES:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                            "message": "Reconciliation requires owner/admin/asset_manager."})
    db = SessionLocal()
    try:
        ls = db.query(LiveState).filter(LiveState.org_id == user.org_id,
                                        LiveState.stream_id == stream_id).first()
        if ls is None:
            raise HTTPException(status_code=404, detail={"code": "no_live_state",
                                "message": "No live state for this stream."})
        cert = db.query(AuditRecord).filter(AuditRecord.id == req.certified_audit_id,
                                            AuditRecord.org_id == user.org_id).first()
        if cert is None:
            raise HTTPException(status_code=404, detail={"code": "audit_not_found",
                                "message": "Certified audit not found in your organization."})
        live_state = json.loads(ls.state_json)
        certified_audit = json.loads(cert.result_json)
        certified_es = eda_metrics.build_economic_state(certified_audit)
        at = datetime.utcnow()
        verifier = {"user_id": user.id, "email": user.email, "role": user.role}
        rec = eda_metrics.build_reconciliation(
            live_state, certified_audit, certified_es,
            live_state_id=ls.id, certified_audit_id=cert.id, stream_id=stream_id,
            verifier_identity=verifier, at_iso=at.isoformat() + "Z")
        # Append-only + hash chain (tamper-evident) over material content.
        last = db.query(Reconciliation).order_by(Reconciliation.id.desc()).first()
        prev = last.row_hash if last else "GENESIS"
        vp = (rec["variance"]["primary"] if rec.get("variance") else {})
        body = (f"{prev}|{user.org_id}|{rec['reconciliation_id']}|{ls.id}|{cert.id}|"
                f"{rec['reconciliation_status']}|{vp.get('absolute')}|{rec['evidence_hash']}|{at.isoformat()}")
        row_hash = _hashlib.sha256(body.encode()).hexdigest()
        db.add(Reconciliation(
            org_id=user.org_id, reconciliation_id=rec["reconciliation_id"], version=rec["version"],
            stream_id=stream_id, live_state_id=ls.id, certified_audit_id=cert.id,
            provisional_hash=rec["provisional_hash"], certified_hash=rec["certified_hash"],
            variance_leakage_abs=(vp.get("absolute")), variance_leakage_pct=(vp.get("relative_pct")),
            currency=live_state.get("currency"), reconciliation_status=rec["reconciliation_status"],
            verifier_user_id=user.id, verifier_email=user.email, verifier_role=user.role,
            evidence_hash=rec["evidence_hash"], at=at, prev_hash=prev, row_hash=row_hash,
            reconciliation_json=json.dumps(rec, default=str)))
        db.commit()
        _security_log("live.reconcile", actor=user.email, org_id=user.org_id,
                      object_ref=f"recon:{rec['reconciliation_id']}|stream:{stream_id}|{rec['reconciliation_status']}")
        return rec
    finally:
        db.close()


@router.get("/api/v1/live/{stream_id}/reconciliations")
async def stream_reconciliations(stream_id: str, user: User = Depends(require_user)):
    """Immutable reconciliation history for a stream (org-scoped)."""
    db = SessionLocal()
    try:
        rows = (db.query(Reconciliation)
                .filter(Reconciliation.stream_id == stream_id, Reconciliation.org_id == user.org_id)
                .order_by(Reconciliation.id.desc()).all())
        return {"stream_id": stream_id, "reconciliations": [_recon_dict(r) for r in rows]}
    finally:
        db.close()


@router.get("/api/v1/live/{stream_id}/certified-state")
async def stream_certified_state(stream_id: str, user: User = Depends(require_user)):
    """
    The AUTHORITATIVE (certified) Economic State for a stream = the certified
    audit from the latest reconciliation. Returns provisional=false. If never
    reconciled, the stream has no certified authority yet.
    """
    db = SessionLocal()
    try:
        last = (db.query(Reconciliation)
                .filter(Reconciliation.stream_id == stream_id, Reconciliation.org_id == user.org_id)
                .order_by(Reconciliation.id.desc()).first())
        if last is None:
            return {"stream_id": stream_id, "status": "NOT_RECONCILED",
                    "message": "No certified authority yet — run a batch audit and reconcile."}
        cert = db.query(AuditRecord).filter(AuditRecord.id == last.certified_audit_id,
                                            AuditRecord.org_id == user.org_id).first()
        es = eda_metrics.build_economic_state(json.loads(cert.result_json)) if cert else None
        return {"stream_id": stream_id, "authority": "certified", "provisional": False,
                "certified_audit_id": last.certified_audit_id,
                "reconciliation_id": last.reconciliation_id,
                "economic_state": es}
    finally:
        db.close()


@router.get("/api/v1/reconciliations")
async def list_reconciliations(user: User = Depends(require_user)):
    """Org-scoped reconciliation register (EDA-RECON-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(Reconciliation).filter(Reconciliation.org_id == user.org_id)
                .order_by(Reconciliation.id.desc()).limit(200).all())
        return {"reconciliations": [_recon_dict(r) for r in rows]}
    finally:
        db.close()


@router.get("/api/v1/reconciliations/verify")
async def reconciliations_verify():
    """Public, content-free tamper check of the reconciliation hash chain."""
    db = SessionLocal()
    try:
        rows = db.query(Reconciliation).order_by(Reconciliation.id.asc()).all()
        prev = "GENESIS"
        broken_at = None
        for r in rows:
            body = (f"{r.prev_hash}|{r.org_id}|{r.reconciliation_id}|{r.live_state_id}|"
                    f"{r.certified_audit_id}|{r.reconciliation_status}|{r.variance_leakage_abs}|"
                    f"{r.evidence_hash}|{r.at.isoformat()}")
            if r.prev_hash != prev or _hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken_at = r.id
                break
            prev = r.row_hash
        return {"entries": len(rows), "chain_valid": broken_at is None,
                "broken_at_id": broken_at, "version": eda_metrics.RECONCILIATION_VERSION,
                "head_hash": (rows[-1].row_hash if rows else None)}
    finally:
        db.close()
