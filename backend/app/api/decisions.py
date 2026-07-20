# -*- coding: utf-8 -*-
"""Decision-lifecycle API router — the EDA-DEC decision register, state
transitions, outcomes, and governance records incl. hash-chain verification.
Extracted VERBATIM from main.py (Router Extraction, step 6).
Dependency direction: api -> core + models + schemas + eda_metrics/canonical_event."""
import hashlib  # noqa: F401
import hashlib as _hashlib  # noqa: F401  (main.py aliases hashlib; verbatim bodies use it)
import json  # noqa: F401
import os  # noqa: F401
import uuid  # noqa: F401
from datetime import datetime  # noqa: F401
from typing import Optional  # noqa: F401

from fastapi import APIRouter, Body, Depends, HTTPException, Request  # noqa: F401
from fastapi.responses import JSONResponse  # noqa: F401

import eda_metrics  # noqa: F401
import canonical_event  # noqa: F401
from app.core.config import SessionLocal  # noqa: F401
from app.core.dependencies import require_user, require_role  # noqa: F401
from app.core.logging import _security_log  # noqa: F401
from app.models import (  # noqa: F401
    AuditRecord, Decision, DecisionEvent, Outcome, GovernanceRecord, LiveEvent, User,
)
from app.schemas import (  # noqa: F401
    AssetSpecs, DecisionTransitionRequest, GovernanceRequest, OutcomeRequest,
)
from app.services.audit_service import process_calculation  # noqa: F401
from app.services.optimization_service import _MILP_LAST  # noqa: F401

router = APIRouter()


@router.get("/api/v1/decisions")
async def list_decisions(user: User = Depends(require_user)):
    """Org-scoped decision register (EDA-DEC-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(Decision).filter(Decision.org_id == user.org_id)
                .order_by(Decision.created_at.desc()).limit(200).all())
        return {"decisions": [{
            "id": r.id, "decision_id": r.decision_id, "version": r.version,
            "audit_id": r.audit_id, "decision_type": r.decision_type,
            "root_cause_id": r.root_cause_id,
            "expected_value": r.expected_value, "currency": r.currency,
            "decision_mode": r.decision_mode, "status": r.status,
            "governance_owner": {"role": r.governance_owner_role,
                                 "assigned_user_id": r.governance_owner_user_id},
            "decision_evidence_sha256": r.decision_evidence_sha256,
            "created_at": r.created_at.isoformat() + "Z",
        } for r in rows]}
    finally:
        db.close()


# ---- EDA-DEC-LIFE-1.0 — Decision Lifecycle (execution tracking) ------------


def _decision_current_state(db, decision_pk: int) -> str:
    """Authoritative current state = latest lifecycle event's to_state."""
    last = (db.query(DecisionEvent)
            .filter(DecisionEvent.decision_pk == decision_pk)
            .order_by(DecisionEvent.id.desc()).first())
    return last.to_state if last else "proposed"


@router.post("/api/v1/decisions/{decision_id}/transition")
async def decision_transition(decision_id: str, req: DecisionTransitionRequest,
                              user: User = Depends(require_user)):
    """
    Drive a decision through the EDA-DEC-LIFE-1.0 state machine. Appends one
    immutable, hash-chained lifecycle event. Deterministic (state machine),
    role-gated, org-scoped. The lifecycle tracks execution only — it never
    computes realized value (Governance does).
    """
    to_state = (req.to_state or "").strip()
    if to_state not in eda_metrics.LIFECYCLE_STATES:
        raise HTTPException(status_code=422, detail={"code": "invalid_state",
                            "message": f"Unknown state. Valid: {', '.join(eda_metrics.LIFECYCLE_STATES)}."})
    db = SessionLocal()
    try:
        dec = (db.query(Decision)
               .filter(Decision.decision_id == decision_id, Decision.org_id == user.org_id)
               .first())
        if dec is None:
            raise HTTPException(status_code=404, detail={"code": "decision_not_found",
                                "message": "No such decision in your organization."})
        current = _decision_current_state(db, dec.id)
        if not eda_metrics.lifecycle_can_transition(current, to_state):
            raise HTTPException(status_code=409, detail={"code": "invalid_transition",
                                "message": f"Cannot move {current} → {to_state}.",
                                "current_state": current,
                                "allowed": sorted(eda_metrics.LIFECYCLE_TRANSITIONS.get(current, set()))})
        if not eda_metrics.lifecycle_role_allowed(user.role, to_state):
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": f"Your role ({user.role}) may not drive a transition to {to_state}."})
        # Append the immutable, hash-chained lifecycle event.
        last = db.query(DecisionEvent).order_by(DecisionEvent.id.desc()).first()
        prev = last.row_hash if last else "GENESIS"
        at = datetime.utcnow()
        body = (f"{prev}|{user.org_id}|{decision_id}|{current}|{to_state}|"
                f"{user.id}|{at.isoformat()}|{req.note or ''}")
        row_hash = _hashlib.sha256(body.encode()).hexdigest()
        ev = DecisionEvent(
            org_id=user.org_id, decision_pk=dec.id, decision_id=decision_id,
            version=eda_metrics.DECISION_LIFECYCLE_VERSION,
            from_state=current, to_state=to_state,
            actor_user_id=user.id, actor_email=user.email, note=req.note,
            decision_evidence_sha256=dec.decision_evidence_sha256,
            at=at, prev_hash=prev, row_hash=row_hash)
        db.add(ev)
        # Denormalised cache on the decision (source of truth is the event chain).
        dec.status = to_state
        dec.status_by = user.id
        dec.status_at = at
        db.commit()
        db.refresh(ev)
        _security_log("decision.transition", actor=user.email, org_id=user.org_id,
                      object_ref=f"decision:{decision_id}|{current}->{to_state}")
        return {"decision_id": decision_id, "from_state": current, "to_state": to_state,
                "terminal": to_state in eda_metrics.LIFECYCLE_TERMINAL,
                "hands_off_to_governance": to_state == "executed",
                "event_id": ev.id, "row_hash": ev.row_hash, "at": at.isoformat() + "Z",
                "version": eda_metrics.DECISION_LIFECYCLE_VERSION}
    finally:
        db.close()


@router.get("/api/v1/decisions/{decision_id}/lifecycle")
async def decision_lifecycle(decision_id: str, user: User = Depends(require_user)):
    """Immutable lifecycle history for one decision (org-scoped)."""
    db = SessionLocal()
    try:
        dec = (db.query(Decision)
               .filter(Decision.decision_id == decision_id, Decision.org_id == user.org_id)
               .first())
        if dec is None:
            raise HTTPException(status_code=404, detail={"code": "decision_not_found",
                                "message": "No such decision in your organization."})
        evs = (db.query(DecisionEvent)
               .filter(DecisionEvent.decision_pk == dec.id, DecisionEvent.org_id == user.org_id)
               .order_by(DecisionEvent.id.asc()).all())
        return {
            "decision_id": decision_id, "version": eda_metrics.DECISION_LIFECYCLE_VERSION,
            "current_state": _decision_current_state(db, dec.id),
            "events": [{
                "event_id": e.id, "from_state": e.from_state, "to_state": e.to_state,
                "actor_email": e.actor_email, "note": e.note,
                "at": e.at.isoformat() + "Z", "row_hash": e.row_hash[:16],
            } for e in evs],
        }
    finally:
        db.close()


@router.get("/api/v1/decisions/lifecycle/verify")
async def decision_lifecycle_verify():
    """Public, content-free tamper check of the whole lifecycle hash chain."""
    db = SessionLocal()
    try:
        rows = db.query(DecisionEvent).order_by(DecisionEvent.id.asc()).all()
        prev = "GENESIS"
        broken_at = None
        for r in rows:
            body = (f"{r.prev_hash}|{r.org_id}|{r.decision_id}|{r.from_state}|{r.to_state}|"
                    f"{r.actor_user_id}|{r.at.isoformat()}|{r.note or ''}")
            if r.prev_hash != prev or _hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken_at = r.id
                break
            prev = r.row_hash
        return {"entries": len(rows), "chain_valid": broken_at is None,
                "broken_at_id": broken_at, "version": eda_metrics.DECISION_LIFECYCLE_VERSION,
                "head_hash": (rows[-1].row_hash if rows else None)}
    finally:
        db.close()


# ---- EDA-OUT-1.0 — Outcome (measures realized impact; facts only) ----------

_OUTCOME_ROLES = {"owner", "admin", "asset_manager", "finance"}


def _outcome_dict_from_row(o: "Outcome") -> dict:
    return {"id": o.id, "outcome_id": o.outcome_id, "version": o.version,
            "decision_id": o.decision_id, "verification_audit_id": o.verification_audit_id,
            "root_cause_id": o.root_cause_id, "currency": o.currency,
            "realized_value": o.realized_value, "outcome_status": o.outcome_status,
            "confidence": {"audit_confidence": o.confidence_aei, "dqi": o.confidence_dqi},
            "evidence_hash": o.evidence_hash, "created_at": o.created_at.isoformat() + "Z"}


@router.post("/api/v1/decisions/{decision_id}/outcome")
async def record_outcome(decision_id: str, req: OutcomeRequest,
                         user: User = Depends(require_user)):
    """
    Measure the realized impact of an EXECUTED decision from a post-execution
    verification audit. Facts only. Immutable. Precondition: the decision's
    lifecycle state is 'executed'. RBAC: owner/admin/asset_manager/finance.
    """
    if user.role not in _OUTCOME_ROLES and user.role != "owner":
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                            "message": "Recording an Outcome requires owner/admin/asset_manager/finance."})
    db = SessionLocal()
    try:
        dec = (db.query(Decision)
               .filter(Decision.decision_id == decision_id, Decision.org_id == user.org_id)
               .first())
        if dec is None:
            raise HTTPException(status_code=404, detail={"code": "decision_not_found",
                                "message": "No such decision in your organization."})
        # Layer rule: an Outcome measures POST-execution — decision must be 'executed'.
        state = _decision_current_state(db, dec.id)
        if state != "executed":
            raise HTTPException(status_code=409, detail={"code": "not_executed",
                                "message": f"Outcome can only be measured for an executed decision (state: {state})."})
        if req.verification_audit_id == dec.audit_id:
            raise HTTPException(status_code=422, detail={"code": "same_audit",
                                "message": "The verification audit must differ from the decision's baseline audit."})
        base = db.query(AuditRecord).filter(AuditRecord.id == dec.audit_id,
                                            AuditRecord.org_id == user.org_id).first()
        ver = db.query(AuditRecord).filter(AuditRecord.id == req.verification_audit_id,
                                           AuditRecord.org_id == user.org_id).first()
        if base is None or ver is None:
            raise HTTPException(status_code=404, detail={"code": "audit_not_found",
                                "message": "Baseline or verification audit not found in your organization."})
        decision_obj = json.loads(dec.decision_json)
        outcome = eda_metrics.build_outcome(
            decision_obj, json.loads(base.result_json), json.loads(ver.result_json),
            verification_audit_id=ver.id)
        row = Outcome(
            org_id=user.org_id, decision_pk=dec.id, decision_id=decision_id,
            outcome_id=outcome["outcome_id"], version=outcome["version"],
            verification_audit_id=ver.id, root_cause_id=outcome["root_cause_id"],
            currency=outcome["currency"], realized_value=outcome["realized_value"],
            outcome_status=outcome["outcome_status"],
            confidence_aei=outcome["confidence"]["audit_confidence"],
            confidence_dqi=outcome["confidence"]["dqi"],
            evidence_hash=outcome["evidence_hash"], measured_by=user.id,
            outcome_json=json.dumps(outcome, default=str))
        db.add(row)
        db.commit()
        db.refresh(row)
        _security_log("outcome.measure", actor=user.email, org_id=user.org_id,
                      object_ref=f"outcome:{outcome['outcome_id']}|decision:{decision_id}|{outcome['outcome_status']}")
        return outcome
    finally:
        db.close()


@router.get("/api/v1/decisions/{decision_id}/outcomes")
async def decision_outcomes(decision_id: str, user: User = Depends(require_user)):
    """Immutable Outcomes measured for one decision (org-scoped)."""
    db = SessionLocal()
    try:
        dec = (db.query(Decision)
               .filter(Decision.decision_id == decision_id, Decision.org_id == user.org_id)
               .first())
        if dec is None:
            raise HTTPException(status_code=404, detail={"code": "decision_not_found",
                                "message": "No such decision in your organization."})
        rows = (db.query(Outcome).filter(Outcome.decision_pk == dec.id, Outcome.org_id == user.org_id)
                .order_by(Outcome.created_at.desc()).all())
        return {"decision_id": decision_id, "outcomes": [_outcome_dict_from_row(o) for o in rows]}
    finally:
        db.close()


@router.get("/api/v1/outcomes")
async def list_outcomes(user: User = Depends(require_user)):
    """Org-scoped Outcome register (EDA-OUT-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(Outcome).filter(Outcome.org_id == user.org_id)
                .order_by(Outcome.created_at.desc()).limit(200).all())
        return {"outcomes": [_outcome_dict_from_row(o) for o in rows]}
    finally:
        db.close()


# ---- EDA-GOV-1.0 — Governance (immutable verification records) -------------

_GOVERNANCE_ROLES = {"owner", "admin", "finance"}


@router.post("/api/v1/outcomes/{outcome_id}/govern")
async def govern_outcome(outcome_id: str, req: GovernanceRequest,
                         user: User = Depends(require_user)):
    """
    Produce an immutable EDA-GOV-1.0 Governance Record verifying a measured
    Outcome. Append-only — never mutates the Outcome. RBAC: owner/admin/finance
    (segregation from those who proposed/executed/measured). Enforces the
    no-fabrication guardrail (insufficient_evidence cannot be 'confirmed').
    """
    if user.role != "owner" and user.role not in _GOVERNANCE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                            "message": "Recording a Governance verdict requires owner/admin/finance."})
    verdict = (req.verdict or "").strip().lower()
    if verdict not in eda_metrics.GOVERNANCE_VERDICTS:
        raise HTTPException(status_code=422, detail={"code": "invalid_verdict",
                            "message": f"Verdict must be one of: {', '.join(eda_metrics.GOVERNANCE_VERDICTS)}."})
    db = SessionLocal()
    try:
        oc = (db.query(Outcome)
              .filter(Outcome.outcome_id == outcome_id, Outcome.org_id == user.org_id)
              .first())
        if oc is None:
            raise HTTPException(status_code=404, detail={"code": "outcome_not_found",
                                "message": "No such outcome in your organization."})
        if not eda_metrics.governance_verdict_allowed(oc.outcome_status, verdict):
            raise HTTPException(status_code=409, detail={"code": "verdict_not_allowed",
                                "message": f"An outcome with status '{oc.outcome_status}' cannot be '{verdict}'. "
                                           "A value that was never measured cannot be confirmed."})
        # audit ids referenced: baseline (from the decision) + verification.
        dec = db.query(Decision).filter(Decision.decision_id == oc.decision_id,
                                        Decision.org_id == user.org_id).first()
        audit_ids = [dec.audit_id if dec else None, oc.verification_audit_id]
        outcome_obj = json.loads(oc.outcome_json)
        at = datetime.utcnow()
        verifier = {"user_id": user.id, "email": user.email, "role": user.role}
        rec = eda_metrics.build_governance_record(outcome_obj, audit_ids, verdict, verifier,
                                                  at_iso=at.isoformat() + "Z")
        # Append-only + hash chain over ALL material content (tamper-evident):
        # editing any column below breaks the chain from that record forward.
        last = db.query(GovernanceRecord).order_by(GovernanceRecord.id.desc()).first()
        prev = last.row_hash if last else "GENESIS"
        vc = rec["verification_confidence"]
        _body = (f"{prev}|{user.org_id}|{rec['governance_id']}|{outcome_id}|"
                 f"{json.dumps(rec['audit_ids'])}|{verdict}|{vc['audit_confidence']}|"
                 f"{user.id}|{at.isoformat()}|{rec['evidence_hash']}")
        row_hash = _hashlib.sha256(_body.encode()).hexdigest()
        db.add(GovernanceRecord(
            org_id=user.org_id, governance_id=rec["governance_id"], version=rec["version"],
            methodology_version=rec["methodology_version"], outcome_id=outcome_id,
            decision_id=rec["decision_id"], audit_ids=json.dumps(rec["audit_ids"]),
            verdict=verdict, verification_confidence=vc["audit_confidence"],
            verification_confidence_grade=vc["grade"], evidence_hash=rec["evidence_hash"],
            verifier_user_id=user.id, verifier_email=user.email, verifier_role=user.role,
            at=at, prev_hash=prev, row_hash=row_hash,
            record_json=json.dumps(rec, default=str)))
        db.commit()
        _security_log("governance.record", actor=user.email, org_id=user.org_id,
                      object_ref=f"governance:{rec['governance_id']}|outcome:{outcome_id}|{verdict}")
        rec["row_hash"] = row_hash
        return rec
    finally:
        db.close()


def _gov_dict(r: "GovernanceRecord") -> dict:
    return {"governance_id": r.governance_id, "version": r.version,
            "methodology_version": r.methodology_version, "outcome_id": r.outcome_id,
            "decision_id": r.decision_id, "audit_ids": json.loads(r.audit_ids or "[]"),
            "verdict": r.verdict,
            "verification_confidence": {"audit_confidence": r.verification_confidence,
                                        "grade": r.verification_confidence_grade},
            "evidence_hash": r.evidence_hash,
            "verifier": {"user_id": r.verifier_user_id, "email": r.verifier_email, "role": r.verifier_role},
            "timestamp": r.at.isoformat() + "Z", "row_hash": r.row_hash[:16]}


@router.get("/api/v1/outcomes/{outcome_id}/governance")
async def outcome_governance(outcome_id: str, user: User = Depends(require_user)):
    """Immutable Governance Records referencing one Outcome (org-scoped)."""
    db = SessionLocal()
    try:
        oc = (db.query(Outcome)
              .filter(Outcome.outcome_id == outcome_id, Outcome.org_id == user.org_id).first())
        if oc is None:
            raise HTTPException(status_code=404, detail={"code": "outcome_not_found",
                                "message": "No such outcome in your organization."})
        rows = (db.query(GovernanceRecord)
                .filter(GovernanceRecord.outcome_id == outcome_id, GovernanceRecord.org_id == user.org_id)
                .order_by(GovernanceRecord.id.asc()).all())
        return {"outcome_id": outcome_id, "records": [_gov_dict(r) for r in rows]}
    finally:
        db.close()


@router.get("/api/v1/governance")
async def list_governance(user: User = Depends(require_user)):
    """Org-scoped Governance Record register (EDA-GOV-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(GovernanceRecord).filter(GovernanceRecord.org_id == user.org_id)
                .order_by(GovernanceRecord.id.desc()).limit(200).all())
        return {"governance_records": [_gov_dict(r) for r in rows]}
    finally:
        db.close()


@router.get("/api/v1/governance/verify")
async def governance_verify():
    """Public, content-free tamper check of the Governance Record hash chain."""
    db = SessionLocal()
    try:
        rows = db.query(GovernanceRecord).order_by(GovernanceRecord.id.asc()).all()
        prev = "GENESIS"
        broken_at = None
        for r in rows:
            body = (f"{r.prev_hash}|{r.org_id}|{r.governance_id}|{r.outcome_id}|"
                    f"{r.audit_ids}|{r.verdict}|{r.verification_confidence}|"
                    f"{r.verifier_user_id}|{r.at.isoformat()}|{r.evidence_hash}")
            if r.prev_hash != prev or _hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken_at = r.id
                break
            prev = r.row_hash
        return {"entries": len(rows), "chain_valid": broken_at is None,
                "broken_at_id": broken_at, "version": eda_metrics.GOVERNANCE_VERSION,
                "head_hash": (rows[-1].row_hash if rows else None)}
    finally:
        db.close()


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
