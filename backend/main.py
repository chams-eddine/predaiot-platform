import os
import re
import uuid
import json
import asyncio
import secrets
import urllib.request
import urllib.error
import pandas as pd
from io import BytesIO, StringIO
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Body, Header, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pulp
import hashlib as _hashlib
import base64 as _base64
import eda_metrics  # versioned, asset-agnostic DQI / Audit Confidence (pure module)
import canonical_event  # EDA-EVENT-1.0 — the single normalization contract (pure)
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta

# ── Version identity (chain of custody, C2) → app/core/versions.py (refactor 3).
from app.core.versions import (  # noqa: E402
    ENGINE_VERSION, METHODOLOGY_VERSION, PARSER_VERSION, SOLVER_NAME, SOLVER_VERSION,
)

# ==========================================
# 1. Database Setup  (CORE LOGIC UNCHANGED — connection made fault-tolerant)
# ==========================================
# DB engine / session / URL now live in app/core/config.py (refactor step 2A).
# Imported back so every `engine` / `SessionLocal` / `DATABASE_URL` call site and
# the fault-tolerant startup handler remain unchanged.
from app.core.config import DATABASE_URL, engine, SessionLocal, CONSULTATION_BOOKING_URL  # noqa: E402
# ORM models + Base now live in app/models/tables.py (refactor step 2B).
from app.models import (  # noqa: E402
    Base, DecisionAuditLog, TrialLead, Organization, User, Asset, AuditRecord,
    EconomicState, Decision, DecisionEvent, Outcome, GovernanceRecord,
    LiveEvent, LiveState, Reconciliation, SecurityAuditLog, APIAccessLog,
    CertificateRecord,
)

# Pure literal constants now live in app/core/constants.py (refactor step 2A).
from app.core.constants import (  # noqa: E402
    _STANDARD_INTERVALS, _MAX_UPLOAD_BYTES, _RATING_WITHDRAWN_LABEL,
    _COMMS_STATUS_ALIASES, _COMMS_OK_VALUES,
)



# _security_log → app/core/logging.py (refactor step 3; shared by certificate_service)




TRIAL_DURATION_DAYS = 7

# NOTE: Base.metadata.create_all() is intentionally NOT called here at import time.
# It is registered as a FastAPI startup event below (after `app` is created), so that
# uvicorn binds the port FIRST and Render's port scan succeeds, regardless of how long
# the DB connection takes. See the @app.on_event("startup") handler near the FastAPI setup.

# ==========================================
# 2. Data Models  (UNCHANGED CORE + NEW FIELDS)
# ==========================================
# Pydantic schemas now live in app/schemas/ (refactor step 3, schemas-first).
from app.schemas import (  # noqa: E402
    AssetSpecs, TimeStepData, AuditRequest, DecisionRecord,
    RootCauseItem, OpportunityItem, HeatMapCell, EDAMetrics,
    FinancialLeakage, AuditResponse, HistoricalResponse, TrialStartRequest,
    TrialStartResponse, TrialStatusResponse, RegisterRequest, LoginRequest,
    AssetCreateRequest, MemberCreateRequest, MemberRoleRequest, DecisionTransitionRequest,
    OutcomeRequest, GovernanceRequest, LiveIngestRequest, ReconcileRequest,
)




# ==========================================
# NEW: Extended EDA Metrics Model
# ==========================================








# ==========================================
# 2.5  Trial Gate & Lead Capture
# ==========================================
# Commercial model (per PREDAIOT v2 brief): Free 7-day diagnostic → paid audit.
# This block turns anonymous /api/v1/audit usage into captured leads. A real
# multi-tenant auth layer (Clerk + Stripe) is deferred until first paying customer.







# Set via env. mailto fallback so the CTA always resolves to *something*.
# CONSULTATION_BOOKING_URL → app/core/config.py (refactor step 2B)

_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _push_lead_to_airtable(token: str) -> bool:
    """
    Fire-and-forget CRM sync, designed to run inside FastAPI BackgroundTasks.
    Re-fetches the lead by token (so we get fresh field values + can mark
    crm_synced on success without sharing a session with the request handler).

    Env: AIRTABLE_API_KEY required; AIRTABLE_BASE_ID defaults to the brief's
    base (appeUbnHpGamghy8q); AIRTABLE_LEADS_TABLE defaults to "Leads".
    Expected table fields: Email, Asset Name, Token, Trial Started, Source.

    CRM down must never block trial creation — this returns False rather than
    raising on any failure.
    """
    api_key = os.environ.get("AIRTABLE_API_KEY")
    if not api_key:
        return False

    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == token).first()
        if lead is None:
            return False

        base_id = os.environ.get("AIRTABLE_BASE_ID", "appeUbnHpGamghy8q")
        table   = os.environ.get("AIRTABLE_LEADS_TABLE", "Leads")
        payload = json.dumps({
            "fields": {
                "Email":         lead.email,
                "Asset Name":    lead.asset_name or "",
                "Token":         lead.token,
                "Trial Started": lead.created_at.isoformat() + "Z",
                "Source":        "PREDAIOT diagnostic trial",
            }
        }).encode("utf-8")

        url = f"https://api.airtable.com/v0/{base_id}/{urllib.request.quote(table)}"
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                ok = 200 <= resp.status < 300
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"[trial] Airtable sync failed (non-fatal): {type(e).__name__}: {e}")
            return False

        if ok:
            lead.crm_synced = True
            db.commit()
        return ok
    finally:
        db.close()


def _create_trial_lead(email: str, asset_name: Optional[str]) -> TrialLead:
    """Persist a new trial token (does not push to Airtable — caller decides)."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        lead = TrialLead(
            token=secrets.token_urlsafe(24),
            email=email.strip().lower(),
            asset_name=(asset_name or "").strip() or None,
            created_at=now,
            expires_at=now + timedelta(days=TRIAL_DURATION_DAYS),
            audit_run_count=0,
            crm_synced=False,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    finally:
        db.close()


# Auth DI dependencies now live in app/core/dependencies.py (refactor step 2B).
from app.core.dependencies import (  # noqa: E402
    require_trial_token, require_user, require_role, _lead_for_user,
    require_audit_runner, require_trial_or_user,
)


def _bump_audit_count(token: str) -> None:
    """Background-task helper. Increments audit_run_count after a successful audit."""
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == token).first()
        if lead is not None:
            lead.audit_run_count = (lead.audit_run_count or 0) + 1
            db.commit()
    finally:
        db.close()


# ==========================================
# Sprint 1: Account auth (COMMODITY per blueprint §0 — minimal robust
# JWT + bcrypt, org-scoped; no external IdP so on-prem/sovereign works).
# Existing trial-token funnel is untouched; account users are dual-accepted
# on every audit endpoint via a linked TrialLead row ("acct-<user_id>").
# ==========================================
# Auth primitives (JWT + bcrypt) now live in app/core/security.py (refactor 2A).
from app.core.security import (  # noqa: E402
    _AUTH_SECRET, _JWT_TTL_HOURS, _ROLES,
    _hash_password, _verify_password, _issue_jwt, _decode_jwt,
)








def _persist_audit_record(lead: TrialLead, result: "AuditResponse",
                          input_sha256: str, filename: Optional[str]) -> None:
    """Store the audit's Economic State for the account's organization (L3)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == lead.user_id).first()
        if user is None:
            return
        d = result.dict()
        dqi = d.get("data_quality_index") or {}
        aei = d.get("audit_confidence") or {}
        attribution = d.get("gap_attribution") or {}
        rcs = d.get("root_causes") or []
        top_rc = max(rcs, key=lambda r: r.get("contribution_pct") or 0)["category"] if rcs else None
        manifest = d.get("audit_manifest") or {}
        rec = AuditRecord(
            org_id=user.org_id, user_id=user.id,
            asset_name=d.get("asset_name"), asset_type=d.get("asset_type"),
            input_sha256=input_sha256, filename=filename,
            engine_version=manifest.get("audit_engine_version"),
            methodology_version=manifest.get("methodology_version"),
            currency=d.get("currency"),
            gap_total=d.get("total_gap_usd"),
            gap_recoverable=attribution.get("execution_gap"),
            dqi=dqi.get("value"), dqi_grade=dqi.get("grade"),
            aei=aei.get("value"), aei_grade=aei.get("grade"),
            top_root_cause=top_rc,
            result_json=json.dumps(_json_safe(d), default=str),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        _security_log("audit.run", actor=user.email, org_id=user.org_id,
                      object_ref=f"audit:{rec.id}|sha:{input_sha256[:12]}")
        # EDA-ES-1.0: materialise the canonical Economic State from this audit.
        es = eda_metrics.build_economic_state(d)
        db.add(EconomicState(
            org_id=user.org_id, audit_id=rec.id, asset_id=rec.asset_id,
            version=es["version"], currency=es["currency"],
            window_start=es["window_start"], window_end=es["window_end"],
            span_hours=es["span_hours"], captured_value=es["captured_value"],
            economic_potential=es["economic_potential"], leakage_rate=es["leakage_rate"],
            recoverable_value=es["recoverable_value"], dqi=es["dqi"],
            audit_confidence=es["audit_confidence"], economic_health=es["economic_health"],
            economic_health_grade=es["economic_health_grade"],
            provisional=es["provisional"], evidence_sha256=es["evidence_sha256"],
            state_json=json.dumps(es, default=str),
        ))
        db.commit()
        # EDA-DEC-1.0: materialise decisions (economic commitments) from the
        # Economic State + audit ledger. Deterministic; consumes, never mutates.
        for dec in eda_metrics.build_decisions(d, es, audit_id=rec.id):
            evi = dec["expected_value_impact"]
            db.add(Decision(
                org_id=user.org_id, audit_id=rec.id, asset_id=rec.asset_id,
                decision_id=dec["decision_id"], version=dec["version"],
                decision_type=dec["decision_type"], root_cause_id=dec["root_cause_id"],
                economic_state_version=dec["economic_state_version"],
                expected_value=evi["value_at_stake"], currency=evi["currency"],
                decision_mode=dec["decision_mode"],
                governance_owner_role=dec["governance_owner"]["role"],
                governance_owner_user_id=dec["governance_owner"]["assigned_user_id"],
                decision_evidence_sha256=dec["evidence_reference"]["decision_evidence_sha256"],
                status=dec["status"],
                decision_json=json.dumps(dec, default=str),
            ))
        db.commit()
    finally:
        db.close()






# ==========================================
# 3. FastAPI Setup  (safety hardening applied)
# ==========================================
# Rate limiter — lazy-imported so a deploy without slowapi still boots and
# the endpoints just aren't rate-limited (fail-open, not fail-closed —
# availability > perfect throttling on a pre-seed platform).
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    _HAS_SLOWAPI = True
except ImportError:
    _HAS_SLOWAPI = False


# Access-log middleware + _client_ip helper now live in app/core/logging.py (2B).
from app.core.logging import _client_ip, _api_access_log, _security_log  # noqa: E402


def _rate_limit_key(request) -> str:
    """
    Rate-limit key: prefer the trial token (per-user) with the real client IP
    as fallback. Falls back to a stable string if the request context is
    unusual so slowapi never explodes.
    """
    try:
        token = request.headers.get("X-Trial-Token") if hasattr(request, "headers") else None
        if token:
            return f"tok:{token[:16]}"
        return f"ip:{_client_ip(request)}"
    except Exception:
        return "unknown"


app = FastAPI(title="PREDAIOT Engine")

# Boot marker — captured once at import. Changes iff the process restarts, so
# restart-recovery can be verified by OBSERVED evidence, not deploy inference.
_BOOT_ID = secrets.token_hex(8)
_BOOT_TIME = datetime.utcnow()

if _HAS_SLOWAPI:
    limiter = Limiter(key_func=_rate_limit_key)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # Null-object shim so the @limiter.limit(...) decorators below are no-ops
    # when slowapi isn't installed. Keeps the audit code path identical.
    class _NullLimiter:
        def limit(self, *_args, **_kwargs):
            def _wrap(fn): return fn
            return _wrap
    limiter = _NullLimiter()


# CORS — allow_origins is now an explicit list from ALLOWED_ORIGINS env
# (comma-separated). Defaults cover the live domain + the Render subdomain.
# Setting it to "*" is still possible via env override but no longer default.
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "https://platform.preda-iot.com,https://predaiot-platform.onrender.com,http://localhost:5173,http://localhost:8000"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Security headers — cheap browser-side hardening. HSTS assumes Render terminates
# TLS in front of us (it does). X-Frame-Options DENY blocks clickjacking of the
# audit UI. Referrer-Policy limits leakage of the trial token via HTTP referer.
@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["Referrer-Policy"]           = "same-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
    return response


# API access-log middleware (one row per /api/v1/* request). Implementation in
# app/core/logging.py; registered HERE to preserve middleware order (refactor 2B).
app.middleware("http")(_api_access_log)

def _alembic_stamp_head():
    """
    Record the current Alembic head in alembic_version after create_all +
    additive migrations have brought the schema to head state. Keeps the
    production DB's declared revision in lockstep with the codebase without
    requiring an external `alembic upgrade` step. Never fatal.
    """
    try:
        from alembic.config import Config as _AlembicConfig
        from alembic import command as _alembic_command
        base = os.path.dirname(os.path.abspath(__file__))
        cfg = _AlembicConfig(os.path.join(base, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(base, "alembic"))
        _alembic_command.stamp(cfg, "head")
        print("[startup] Alembic version stamped to head.")
    except Exception as e:
        print(f"[startup] WARNING: alembic stamp failed (non-fatal): {e}")


def _apply_additive_migrations(bind_engine):
    """
    Idempotent additive-column migration. create_all() creates missing TABLES
    but never adds new COLUMNS to a table that already exists, so a deployment
    upgrading over a persistent DB would 500 on the new columns. This adds any
    missing nullable columns via ALTER TABLE (safe on SQLite + Postgres).
    Additive-only: never drops or alters existing columns.
    """
    # {table: [(column, SQL type)]} — extend as the schema grows.
    _EXPECTED = {
        "certificate_registry": [
            ("dqi_grade", "VARCHAR"),
            ("confidence_grade", "VARCHAR"),
        ],
        "trial_leads": [
            ("user_id", "INTEGER"),
        ],
    }
    insp_sql_existing = {}
    with bind_engine.connect() as conn:
        for table, cols in _EXPECTED.items():
            try:
                rows = conn.exec_driver_sql(
                    f"SELECT * FROM {table} LIMIT 0")
                existing = set(rows.keys())
            except Exception:
                continue  # table not present yet (create_all will have made it)
            for name, sqltype in cols:
                if name not in existing:
                    try:
                        conn.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}")
                        conn.commit()
                        print(f"[startup] migration: added {table}.{name}")
                    except Exception as e:
                        print(f"[startup] migration WARN {table}.{name}: {e}")


@app.on_event("startup")
async def init_database_tables():
    """
    Runs AFTER uvicorn has already bound to $PORT and started accepting connections.
    This guarantees Render's port scan succeeds even if the DB is slow/unreachable —
    the table creation no longer blocks process startup. Run in a thread so a slow/
    hanging DB connection can never block the asyncio event loop either.
    """
    def _create_tables():
        try:
            Base.metadata.create_all(bind=engine)
            _apply_additive_migrations(engine)
            _alembic_stamp_head()
            print("[startup] Database tables ready.")
        except Exception as e:
            print(f"[startup] WARNING: could not initialize database tables: {e}")
            print("[startup] App is live. DB-dependent endpoints may fail until DB is reachable.")
    await asyncio.to_thread(_create_tables)

# Per-trial-token cache for the most recent audit each trial ran. Replaces
# the process-global `latest_live_result` which leaked between trial holders
# (any caller could see whichever audit ran most recently). Now indexed by
# lead.token so /api/latest, /api/v1/certificate, /api/v1/audit/pdf/latest
# only return the caller's own data.
_latest_by_token: Dict[str, dict] = {}
_EMPTY_LATEST = {
    "edv_optimal_total": 0, "edv_actual_total": 0,
    "dq_score": 0, "total_gap_usd": 0, "decision_log": [],
}
shared_audits = {}

# ==========================================
# 4. Optimizer  (multi-asset router)
# ==========================================
# PREDAIOT operates across the energy sector, not just BESS. Each asset class
# has a different optimal-dispatch shape:
#
#   storage      — BESS / Pumped Hydro / H₂ with storage. MILP over time
#                  (charge, discharge, SOC). Time-coupled.
#   intermittent — Solar / Wind / Tidal. Generation is exogenous; the only
#                  decision is whether to export or curtail. Per-step.
#   dispatchable — Gas / Thermal / Hydro-no-storage / Nuclear / Geothermal.
#                  Generator runs at p_max when price > marginal cost; idle
#                  otherwise. Per-step (no time coupling without UC).
#   load         — Electrolyzer / Desalination. When-to-run problem. Not yet
#                  in v1; falls through to storage with safe defaults.
#
# The reduced-form EDV (price − marginal_cost) · dispatch is the same across
# all three modes; `deg_cost` is interpreted as the per-MWh marginal cost.

_STORAGE_TYPES      = {"bess", "battery", "storage", "pumped hydro", "pumpedhydro", "phs"}
# Dispatch optimizers now live in app/services/optimization_service.py (step 3).
# ECONOMIC ENGINE FROZEN — moved byte-for-byte; imported back where referenced.
from app.services.optimization_service import (  # noqa: E402
    _dispatch_mode, _MILP_LAST, _run_optimizer_storage,
    run_optimizer, run_optimizer_full,
)

# ==========================================
# 5. NEW: EDA Intelligence Engine
# ==========================================
# _classify_decision -> optimization_service (economic leaf); _live_decision_core
# -> telemetry_service (refactor step 3, service 4).
from app.services.optimization_service import _classify_decision  # noqa: E402
from app.services.telemetry_service import _live_decision_core  # noqa: E402

# Economic-narrative builders now in app/domain/economics.py (first domain module;
# refactor step 3, service 5 part 2). Internal helpers stay private to the module.
from app.domain.economics import (  # noqa: E402
    _build_root_causes, _build_opportunities, _build_heat_map,
    _build_eda_metrics, _build_ai_commentary, _risk_level,
)

# ==========================================
# 6. Central Calculation Engine  (CORE UNCHANGED + EDA LAYER)
# ==========================================
def process_calculation(asset: AssetSpecs, time_series_list: list, save_to_db: bool = True,
                        dt_hours: float = 1.0, currency: str = "USD"):
    """
    Runs the MILP + EDV + EDA pipeline. Does NOT touch the per-token cache —
    the endpoint handler is responsible for caching the result under its
    trial token. Keeping the tenant-scoping outside this function preserves
    it as a pure calc engine (no auth coupling).

    dt_hours = duration of one time step. All monetary EDV terms are
    price × MW × dt (money = energy × price, not power × price), and the
    storage MILP's SoC balance uses the same dt. Default 1.0 keeps every
    pre-existing hourly audit byte-identical.
    """
    dt_hours = float(dt_hours) if dt_hours and dt_hours > 0 else 1.0
    optimal_actions, optimal_charges = run_optimizer_full(asset, time_series_list, dt_hours=dt_hours)
    total_edv_opt, total_edv_act = 0.0, 0.0
    decision_log = []
    db = SessionLocal() if save_to_db else None

    # Dispatch-mode-dependent EDV computation. For generation modes (storage,
    # intermittent, dispatchable) EDV = (price − marginal_cost) × dispatch —
    # positive = value captured, negative = uneconomic dispatch. For LOAD mode
    # the asset consumes, so EDV = (peak_price − price) × consumption —
    # positive = "savings vs the worst-price hour of the day." Same-signed,
    # comparable, and the gap arithmetic downstream (edv_opt − edv_act) still
    # reads as "recoverable value."
    mode = _dispatch_mode(asset.asset_type)
    is_load = (mode == "load")
    is_storage = (mode == "storage")
    peak_price = max((float(ts.get("price", 0) or 0) for ts in time_series_list), default=0.0)

    try:
        for i, ts in enumerate(time_series_list):
            opt_dis  = optimal_actions.get(i, 0.0)
            opt_ch   = optimal_charges.get(i, 0.0)
            # Load-class inputs may put consumption in actual_charge; other
            # modes use actual_discharge. Fall back if the caller only filled one.
            if is_load:
                act_dis = float(ts.get("actual_charge", 0) or 0) or float(ts.get("actual_discharge", 0) or 0)
            else:
                act_dis = float(ts.get("actual_discharge", 0) or 0)
            price    = float(ts.get("price", 0))
            curtail  = float(ts.get("curtailment_mw", 0))
            override = bool(ts.get("operator_override", False))
            fc_price = ts.get("forecast_price", None)
            soc_val  = ts.get("soc", None)
            demand   = ts.get("grid_demand", None)

            if is_load:
                edv_opt_step = (peak_price - price) * opt_dis * dt_hours
                edv_act_step = (peak_price - price) * act_dis * dt_hours
            elif is_storage:
                # Reference Manual Vol II Ch 3: J = [P·P_dis − P·P_ch]·Δt − C_deg.
                # Charging is paid for at the market price — omitting it (the
                # old formula) reported gross discharge margin, overstating the
                # optimal by the whole charge bill (observed: 536 vs ~209 OMR
                # on the Ibri2 reference file).
                act_ch = float(ts.get("actual_charge", 0) or 0)
                edv_opt_step = ((price - asset.deg_cost) * opt_dis - price * opt_ch) * dt_hours
                edv_act_step = ((price - asset.deg_cost) * act_dis - price * act_ch) * dt_hours
            else:
                edv_opt_step = ((price * opt_dis) - (asset.deg_cost * opt_dis)) * dt_hours
                edv_act_step = ((price * act_dis) - (asset.deg_cost * act_dis)) * dt_hours
            gap_step     = edv_opt_step - edv_act_step
            total_edv_opt += edv_opt_step
            total_edv_act += edv_act_step

            dec_type, confidence = _classify_decision(opt_dis, act_dis, price)

            if db:
                db.add(DecisionAuditLog(
                    asset_id=asset.asset_id,
                    timestamp=datetime.utcnow(),
                    market_price=price,
                    optimal_action=opt_dis,
                    actual_action=act_dis,
                    economic_gap=gap_step
                ))

            decision_log.append(DecisionRecord(
                hour=ts.get("hour", i),
                price=price,
                optimal_action=round(opt_dis, 2),
                actual_action=round(act_dis, 2),
                edv_optimal_step=round(edv_opt_step, 2),
                edv_actual_step=round(edv_act_step, 2),
                gap_step=round(gap_step, 2),
                decision_type=dec_type,
                confidence=confidence,
                operator_override=override,
                curtailment_mw=curtail,
                soc=soc_val,
                grid_demand=demand,
                forecast_price=fc_price
            ))
        if db:
            db.commit()
    finally:
        if db:
            db.close()

    # DQ Score per Reference Manual Ch. 4.2: when no arbitrage opportunity
    # existed (EDV_opt ≈ 0) and the operator correctly captured none
    # (EDV_act ≈ 0), nothing was missed — DQ is 1.0, not 0. Falling through
    # to 0 here was scoring flat-price periods as "Severe risk".
    _EDV_EPS = 1e-9
    if total_edv_opt > _EDV_EPS:
        dq_score = total_edv_act / total_edv_opt
    elif abs(total_edv_act) <= _EDV_EPS:
        dq_score = 1.0
    else:
        dq_score = 0.0
    # DQ is a ratio against a modeled UPPER BOUND, so raw > 1.0 means the
    # model disagrees with reality — wrong column mapping, wrong asset specs,
    # or actual dispatch exceeding p_max. Clamp for display (Ch. 4.2 defines
    # DQ ∈ [0,1]) but keep the raw value so ingestion can flag the mismatch
    # instead of silently reporting a perfect score.
    dq_score_raw = dq_score
    dq_score = max(0.0, min(1.0, dq_score))
    total_gap = total_edv_opt - total_edv_act

    # ── Gap Attribution per Reference Manual Ch 8.2 ─────────────────────
    # G_total = G_forecast + G_execution. d_rec = what the MILP recommends
    # using the FORECAST prices; evaluating d_rec under realized prices
    # telescopes the gap exactly:
    #   G_forecast  = J(d*|P_act) − J(d_rec|P_act)  (forecast imperfection)
    #   G_execution = J(d_rec|P_act) − J(d_act|P_act) (not following the rec)
    # Storage-only (the MILP mode) and only when a forecast column exists.
    gap_attribution = None
    if is_storage and time_series_list:
        fc_raw = [ts.get("forecast_price") for ts in time_series_list]
        n_ok = sum(1 for f in fc_raw if f is not None and f == f)
        if n_ok >= 0.9 * len(time_series_list):
            try:
                fc_prices = [float(f) if (f is not None and f == f) else 0.0 for f in fc_raw]
                rec_dis, rec_ch = _run_optimizer_storage(asset, fc_prices, dt_hours=dt_hours,
                                                         return_charge=True)
                j_rec_actual = sum(
                    ((float(ts.get("price", 0)) - asset.deg_cost) * rec_dis.get(i, 0.0)
                     - float(ts.get("price", 0)) * rec_ch.get(i, 0.0)) * dt_hours
                    for i, ts in enumerate(time_series_list)
                )
                gap_attribution = {
                    "forecast_gap":  round(total_edv_opt - j_rec_actual, 2),
                    "execution_gap": round(j_rec_actual - total_edv_act, 2),
                    "recommended_value": round(j_rec_actual, 2),
                    "method": ("Ch 8.2 telescoping split under realized prices: "
                               "G = [J(d*|P) - J(d_rec|P)] + [J(d_rec|P) - J(d_act|P)]"),
                }
            except Exception:
                gap_attribution = None  # attribution is enrichment, never fatal

    # Build EDA intelligence layers. Annualisation uses the span actually
    # audited (8760 / span_hours) — for a 24h hourly file this is exactly the
    # legacy ×365, for a 5-minute SCADA day it stops over-scaling 12×.
    span_hours_eda = len(time_series_list) * dt_hours
    annual_factor = (8760.0 / span_hours_eda) if span_hours_eda > 0 else 365.0
    eda_metrics  = _build_eda_metrics(decision_log, total_edv_opt, total_edv_act, asset.asset_type,
                                      dt_hours=dt_hours)
    root_causes  = _build_root_causes(decision_log, total_gap, total_edv_opt)
    opportunities = _build_opportunities(total_gap, asset.asset_type, decision_log,
                                         annual_factor=annual_factor, currency=currency)
    heat_map     = _build_heat_map(decision_log)
    ai_commentary = _build_ai_commentary(
        asset.asset_name, total_gap, total_edv_opt, decision_log, dq_score,
        eda_metrics=eda_metrics, opportunities=opportunities, root_causes=root_causes,
        annual_factor=annual_factor, currency=currency, gap_attribution=gap_attribution,
    )
    if gap_attribution:
        ai_commentary += (
            "\n\nGAP ATTRIBUTION (Ref. Manual Ch 8.2)\n"
            f"Theoretical Ceiling Gap    {_fmt_money(total_gap, currency)}"
            "  — vs the perfect-foresight upper-bound benchmark.\n"
            f"  Forecast-Unreachable     {_fmt_money(gap_attribution['forecast_gap'], currency)}"
            "  — capturable only with perfect price foresight (not operator-attributable).\n"
            f"  Recoverable Execution    {_fmt_money(gap_attribution['execution_gap'], currency)}"
            "  — achievable with information available at decision time "
            "(operator / automation attributable)."
        )

    top_sources = []
    for rc in root_causes[:5]:
        top_sources.append({"name": rc.category, "usd": rc.loss_usd, "pct": rc.contribution_pct})

    # Annualise from the actual span covered, not "×365 days" — a 5-minute
    # file covering 24h and an hourly file covering 48h both scale correctly.
    span_hours = span_hours_eda
    projection_12m = total_gap * annual_factor if span_hours > 0 else 0.0
    financial_leakage = FinancialLeakage(
        period_24h=round(total_gap, 2),
        projection_12m=round(projection_12m, 2),
        top_sources=top_sources
    )

    result = AuditResponse(
        # UNCHANGED core fields
        edv_optimal_total=round(total_edv_opt, 2),
        edv_actual_total=round(total_edv_act, 2),
        dq_score=round(dq_score, 4),
        dq_score_raw=round(dq_score_raw, 4),
        gap_attribution=gap_attribution,
        total_gap_usd=round(total_gap, 2),
        # Presentation hierarchy: same verified numbers under honest names.
        theoretical_ceiling_gap=round(total_gap, 2),
        recoverable_execution_gap=(round(gap_attribution["execution_gap"], 2)
                                   if gap_attribution else None),
        headline_gap_basis=("execution" if gap_attribution else "ceiling"),
        decision_log=decision_log,
        # Extended EDA
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        audit_period_label=f"{len(time_series_list)} Steps ({span_hours:g}h)",
        risk_level=_risk_level(dq_score),
        eda_metrics=eda_metrics,
        root_causes=root_causes,
        opportunities=opportunities,
        heat_map=heat_map,
        financial_leakage=financial_leakage,
        ai_commentary=ai_commentary,
        currency=(currency or "USD").upper(),
        counterfactual_summary=(
            f"Against the Theoretical Economic Ceiling (perfect-foresight upper-bound "
            f"benchmark), {asset.asset_name} could have captured {_fmt_money(total_edv_opt, currency)} "
            f"vs actual {_fmt_money(total_edv_act, currency)} — a ceiling gap of "
            f"{_fmt_money(total_gap, currency)}. "
            + (
                f"Of this, the Recoverable Execution Gap — value achievable using information "
                f"available at decision time — is {_fmt_money(gap_attribution['execution_gap'], currency)}; "
                f"the remaining {_fmt_money(gap_attribution['forecast_gap'], currency)} was reachable "
                f"only with perfect price foresight."
                if gap_attribution else
                "The ceiling gap is an upper bound: it includes value reachable only with perfect "
                "price foresight. A day-ahead forecast column is required to isolate the "
                "operationally recoverable portion."
            )
        ),
        # Echo ISSUED TO fields from AssetSpecs
        asset_id=asset.asset_id,
        asset_location=asset.location,
        client_name=asset.client_name,
        client_company=asset.client_company,
    )
    return result

# ==========================================
# 7. API Endpoints  (UNCHANGED CORE + universal file parser + trial gate)
# ==========================================

# ---- Trial Gate endpoints --------------------------------------------------
from fastapi import BackgroundTasks  # local import keeps the imports block tidy

@app.post("/api/v1/trial/start", response_model=TrialStartResponse)
@limiter.limit("20/hour")
async def start_trial(request: Request, req: TrialStartRequest, background: BackgroundTasks):
    """
    Start a 7-day free diagnostic. Returns a trial_token that the frontend
    sends as X-Trial-Token on subsequent /api/v1/audit calls.
    Lead is pushed to Airtable in the background (best-effort).
    """
    email = (req.email or "").strip().lower()
    if not _EMAIL_SHAPE.match(email):
        raise HTTPException(status_code=400, detail="Please provide a valid work email.")
    lead = _create_trial_lead(email, req.asset_name)
    background.add_task(_push_lead_to_airtable, lead.token)
    return TrialStartResponse(
        token=lead.token,
        expires_at=lead.expires_at.isoformat() + "Z",
        booking_url=CONSULTATION_BOOKING_URL,
    )


@app.get("/api/v1/trial/status", response_model=TrialStatusResponse)
async def trial_status(lead: TrialLead = Depends(require_trial_token)):
    """Lightweight token-validity check for the frontend on page load."""
    return TrialStatusResponse(
        email=lead.email,
        asset_name=lead.asset_name,
        expires_at=lead.expires_at.isoformat() + "Z",
        audit_run_count=lead.audit_run_count,
        is_expired=lead.expires_at < datetime.utcnow(),
    )


# ---- Sprint 1: account + organization + asset registry ---------------------






def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return s[:40]


@app.post("/api/v1/auth/register")
@limiter.limit("5/minute")
async def auth_register(request: Request, req: RegisterRequest):  # noqa: ARG001
    email = req.email.strip().lower()
    if "@" not in email or len(req.password) < 8:
        raise HTTPException(status_code=422, detail={"code": "invalid_input",
                            "message": "Valid email and a password of at least 8 characters are required."})
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail={"code": "email_taken",
                                "message": "An account with this email already exists. Sign in instead."})
        base = _slugify(req.organization)
        slug = base
        n = 1
        while db.query(Organization).filter(Organization.slug == slug).first():
            n += 1
            slug = f"{base}-{n}"
        org = Organization(name=req.organization.strip() or email, slug=slug)
        db.add(org)
        db.flush()
        user = User(org_id=org.id, email=email,
                    password_hash=_hash_password(req.password), role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
        _security_log("auth.register", actor=email, org_id=org.id,
                      object_ref=f"org:{org.slug}")
        return {"token": _issue_jwt(user), "email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug}}
    finally:
        db.close()


@app.post("/api/v1/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request, req: LoginRequest):  # noqa: ARG001
    email = req.email.strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not _verify_password(req.password, user.password_hash):
            _security_log("auth.login.failed", actor=email)
            raise HTTPException(status_code=401, detail={"code": "bad_credentials",
                                "message": "Email or password is incorrect."})
        _security_log("auth.login.ok", actor=email, org_id=user.org_id)
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        return {"token": _issue_jwt(user), "email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug} if org else None}
    finally:
        db.close()


@app.get("/api/v1/auth/me")
async def auth_me(user: User = Depends(require_user)):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        n_assets = db.query(Asset).filter(Asset.org_id == user.org_id).count()
        return {"email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug} if org else None,
                "assets": n_assets}
    finally:
        db.close()


def _asset_dict(a: "Asset") -> dict:
    return {"id": a.id, "name": a.name, "asset_type": a.asset_type,
            "capacity_mw": a.capacity_mw, "currency": a.currency,
            "specs": (json.loads(a.specs_json) if a.specs_json else None),
            "created_at": a.created_at.isoformat() + "Z"}


@app.post("/api/v1/assets")
async def create_asset(req: AssetCreateRequest,
                       user: User = Depends(require_role("admin", "asset_manager"))):
    db = SessionLocal()
    try:
        a = Asset(org_id=user.org_id, name=req.name.strip(),
                  asset_type=req.asset_type, capacity_mw=req.capacity_mw,
                  currency=req.currency,
                  specs_json=(json.dumps(req.specs) if req.specs else None))
        db.add(a)
        db.commit()
        db.refresh(a)
        _security_log("asset.create", actor=user.email, org_id=user.org_id,
                      object_ref=f"asset:{a.id}")
        return _asset_dict(a)
    finally:
        db.close()


@app.get("/api/v1/assets")
async def list_assets(user: User = Depends(require_user)):
    db = SessionLocal()
    try:
        rows = (db.query(Asset).filter(Asset.org_id == user.org_id)
                .order_by(Asset.created_at.desc()).all())
        return {"assets": [_asset_dict(a) for a in rows]}
    finally:
        db.close()


# ---- Sprint 2: RBAC — org user management ----------------------------------




@app.post("/api/v1/org/users")
async def org_add_member(req: MemberCreateRequest,
                         user: User = Depends(require_role("admin"))):
    """Owner/admin adds an org member. The password is returned ONCE."""
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail={"code": "invalid_email",
                            "message": "A valid email is required."})
    if req.role not in _ROLES:
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": f"Role must be one of: {', '.join(_ROLES)}."})
    if req.role == "owner":
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": "Ownership is transferred, not granted at creation."})
    pw = req.password or secrets.token_urlsafe(12)
    if len(pw) < 8:
        raise HTTPException(status_code=422, detail={"code": "weak_password",
                            "message": "Password must be at least 8 characters."})
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail={"code": "email_taken",
                                "message": "An account with this email already exists."})
        member = User(org_id=user.org_id, email=email,
                      password_hash=_hash_password(pw), role=req.role)
        db.add(member)
        db.commit()
        db.refresh(member)
        _security_log("org.member.create", actor=user.email, org_id=user.org_id,
                      object_ref=f"user:{member.id}|role:{member.role}")
        return {"email": member.email, "role": member.role,
                "temporary_password": (None if req.password else pw),
                "note": "Share the temporary password securely; it is not stored in clear and cannot be shown again."}
    finally:
        db.close()


@app.get("/api/v1/org/users")
async def org_list_members(user: User = Depends(require_user)):
    db = SessionLocal()
    try:
        rows = (db.query(User).filter(User.org_id == user.org_id)
                .order_by(User.created_at.asc()).all())
        return {"users": [{"id": u.id, "email": u.email, "role": u.role,
                           "created_at": u.created_at.isoformat() + "Z"} for u in rows]}
    finally:
        db.close()


@app.patch("/api/v1/org/users/{member_id}")
async def org_change_role(member_id: int, req: MemberRoleRequest,
                          user: User = Depends(require_role("admin"))):
    if req.role not in _ROLES or req.role == "owner":
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": "Role must be a non-owner role."})
    db = SessionLocal()
    try:
        m = (db.query(User).filter(User.id == member_id,
                                   User.org_id == user.org_id).first())
        if m is None:
            raise HTTPException(status_code=404, detail={"code": "member_not_found",
                                "message": "No such member in your organization."})
        if m.role == "owner":
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": "The owner role cannot be changed here."})
        old_role = m.role
        m.role = req.role
        db.commit()
        _security_log("org.member.role_change", actor=user.email, org_id=user.org_id,
                      object_ref=f"user:{m.id}|{old_role}->{req.role}")
        return {"id": m.id, "email": m.email, "role": m.role}
    finally:
        db.close()


# ---- Sprint 2: Audit History + Economic Memory (L3, blueprint §3) ----------
@app.get("/api/v1/audits")
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


@app.get("/api/v1/audits/{audit_id}")
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


@app.get("/api/v1/audits/{audit_id}/economic-state")
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


@app.get("/api/v1/economic-states")
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


@app.get("/api/v1/audits/{audit_id}/decisions")
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


@app.get("/api/v1/decisions")
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


@app.post("/api/v1/decisions/{decision_id}/transition")
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


@app.get("/api/v1/decisions/{decision_id}/lifecycle")
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


@app.get("/api/v1/decisions/lifecycle/verify")
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


@app.post("/api/v1/decisions/{decision_id}/outcome")
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


@app.get("/api/v1/decisions/{decision_id}/outcomes")
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


@app.get("/api/v1/outcomes")
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


@app.post("/api/v1/outcomes/{outcome_id}/govern")
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


@app.get("/api/v1/outcomes/{outcome_id}/governance")
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


@app.get("/api/v1/governance")
async def list_governance(user: User = Depends(require_user)):
    """Org-scoped Governance Record register (EDA-GOV-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(GovernanceRecord).filter(GovernanceRecord.org_id == user.org_id)
                .order_by(GovernanceRecord.id.desc()).limit(200).all())
        return {"governance_records": [_gov_dict(r) for r in rows]}
    finally:
        db.close()


@app.get("/api/v1/governance/verify")
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


@app.post("/api/v1/live/ingest")
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


@app.get("/api/v1/live/state")
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


@app.post("/api/v1/live/{stream_id}/reconcile")
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


@app.get("/api/v1/live/{stream_id}/reconciliations")
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


@app.get("/api/v1/live/{stream_id}/certified-state")
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


@app.get("/api/v1/reconciliations")
async def list_reconciliations(user: User = Depends(require_user)):
    """Org-scoped reconciliation register (EDA-RECON-1.0), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(Reconciliation).filter(Reconciliation.org_id == user.org_id)
                .order_by(Reconciliation.id.desc()).limit(200).all())
        return {"reconciliations": [_recon_dict(r) for r in rows]}
    finally:
        db.close()


@app.get("/api/v1/reconciliations/verify")
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


@app.get("/api/v1/memory")
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


@app.get("/api/v1/security/log/verify")
async def security_log_verify():
    """Public tamper-evidence check: recomputes the whole hash chain.
    Returns validity + counts only — no event content."""
    db = SessionLocal()
    try:
        rows = db.query(SecurityAuditLog).order_by(SecurityAuditLog.id.asc()).all()
        prev = "GENESIS"
        broken_at = None
        for r in rows:
            body = f"{r.prev_hash}|{r.org_id}|{r.actor}|{r.action}|{r.object_ref}|{r.at.isoformat()}"
            if r.prev_hash != prev or _hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken_at = r.id
                break
            prev = r.row_hash
        return {"entries": len(rows), "chain_valid": broken_at is None,
                "broken_at_id": broken_at,
                "head_hash": (rows[-1].row_hash if rows else None)}
    finally:
        db.close()


@app.get("/api/v1/security/log")
async def security_log_view(user: User = Depends(require_role("admin"))):
    """Org-scoped security events (owner/admin only), newest first."""
    db = SessionLocal()
    try:
        rows = (db.query(SecurityAuditLog)
                .filter(SecurityAuditLog.org_id == user.org_id)
                .order_by(SecurityAuditLog.id.desc()).limit(200).all())
        return {"events": [{
            "id": r.id, "at": r.at.isoformat() + "Z", "actor": r.actor,
            "action": r.action, "object": r.object_ref, "row_hash": r.row_hash[:16],
        } for r in rows]}
    finally:
        db.close()


# ---- Audit endpoints (gated by trial token) --------------------------------
@app.post("/api/v1/audit", response_model=AuditResponse)
@limiter.limit("10/minute")
async def calculate_gap(
    request: Request,   # noqa: ARG001 — used by rate limiter
    audit_req: AuditRequest,
    background: BackgroundTasks,
    lead: TrialLead = Depends(require_audit_runner),
):
    result = process_calculation(audit_req.asset, [ts.dict() for ts in audit_req.time_series],
                                 dt_hours=audit_req.dt_hours or 1.0)
    _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
    background.add_task(_bump_audit_count, lead.token)
    return result

# ==========================================
# COLUMN ALIAS MAP — fuzzy resolver
# Maps any real-world column name variant → internal name
# ==========================================
# Ingestion + data-quality service now in app/services/ingestion.py (svc 5 pt 1).
from app.services.ingestion import (  # noqa: E402
    COLUMN_ALIASES, ASSET_META_ALIASES, _normalise_col, _FUZZY_THRESHOLD,
    _resolve_columns_verbose, _resolve_columns, _detect_and_apply_units, _detect_excel_serial_timestamps,
    _TIMESTAMP_FORMAT_ATTEMPTS, _parse_timestamps, _fill_ts_bounds, _detect_and_resample,
    _dq, _order_and_dedupe_timestamps, _coerce_numeric_columns, _build_sensor_quality_flags,
    _collect_data_quality_counts, _dqi_components_from_manifest, _forecast_reliability_from_snapshot, _detect_currency,
    _looks_numeric, _fix_banner_header, _parse_file_bytes, _parse_file_bytes_raw,
)

# Asset spec meta-columns that can optionally appear as file columns









# Suggested fallbacks for missing fields — used in the inspect response so
# users know exactly what will happen if they proceed without a given column.
_MISSING_FIELD_FALLBACKS = {
    "actual_charge":     "assumed 0 MW throughout — charging events won't be detected.",
    "soc":               "not required for the audit; SOC constraints won't gate the optimiser.",
    "curtailment_mw":    "assumed 0 MW — curtailment recovery attribution will be zero.",
    "forecast_price":    "not required; forecast-utilisation score defaults to 0%.",
    "operator_override": "assumed False — override-governance opportunity won't fire.",
    "grid_demand":       "advisory only; the audit engine doesn't use it.",
    "hour":              "auto-generated as 0..N-1 ordered index.",
}






# Order matters: try the strictest / most-informative parses first. ISO 8601
# (including Z-suffixed and offset-suffixed variants) parses cleanly with just
# `utc=True`; only fall through to Gulf/US slash-date if ISO fails.






# Standard energy-market resolutions we snap to (seconds)
# _STANDARD_INTERVALS → app/core/constants.py (refactor step 2A)




# ==========================================
# DATA QUALITY & CLEANING LAYER
# "Trust of result is everything" — every silent auto-correction the pipeline
# makes gets a named flag the operator can read before quoting the audit.
# Severity: "warning" = affects result trust, "info" = cosmetic / advisory.
# ==========================================



# _fmt_money / _json_safe now live in app/utils/formatting.py (refactor step 1).
# Imported at module top; re-exported here so every existing `_fmt_money(...)`
# / `_json_safe(...)` call site in this file is unchanged.
from app.utils.formatting import _fmt_money, _json_safe  # noqa: E402,F401






# Column names that carry a comms / link health status in SCADA exports
# _COMMS_STATUS_ALIASES / _COMMS_OK_VALUES → app/core/constants.py (refactor step 2A)










# _CURRENCY_HINTS → app/services/ingestion.py (refactor step 3, service 5 part 1)




# Upload ceiling: a year of 1-minute data for one asset is ~40 MB of CSV;
# anything past this is either the wrong export or a memory-exhaustion attempt.
# _MAX_UPLOAD_BYTES → app/core/constants.py (refactor step 2A)










@app.post("/api/v1/audit/file", response_model=AuditResponse)
@limiter.limit("10/minute")
async def audit_from_file(
    request: Request,   # noqa: ARG001 — used by rate limiter
    background: BackgroundTasks,
    file: UploadFile = File(...),
    lead: TrialLead = Depends(require_audit_runner),
):
    """
    Universal file ingestion. Accepts real-world exports from any SCADA / EMS /
    historian with a two-tier column resolver, JSON support, unit auto-detection,
    and Excel-serial timestamp recovery.

    Accepted formats: .csv  .tsv  .txt  .xlsx  .xls  .xlsm  .json
    """
    try:
        contents = await file.read()
        if len(contents) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={
                "detail": f"File is {len(contents) / 1e6:.0f} MB — the upload limit is "
                          f"{_MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Split the export or "
                          "resample to a coarser interval."})
        df = _parse_file_bytes(contents, file.filename or "")
        if len(df) == 0:
            return JSONResponse(status_code=400, content={
                "detail": "The file parsed but contains no data rows (header only?)."})
        raw_shape = df.shape  # provenance: as-parsed dimensions (C2 manifest)

        # Resolve column aliases (exact → fuzzy)
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Check required fields resolved. Load-class assets (electrolyzers,
        # desalination) report CONSUMPTION, not output — actual_charge alone
        # is a valid audit input for them (the engine falls back internally).
        has_output = ("actual_discharge" in col_map) or ("actual_charge" in col_map)
        if "price" not in col_map or not has_output:
            missing = [r for r in ("price",) if r not in col_map]
            if not has_output:
                missing.append("actual_discharge (or a consumption column like actual_charge)")
            return JSONResponse(status_code=400, content={
                "detail": (
                    f"Could not find required column(s): {missing}. "
                    f"Your file has columns: {list(df.columns)}. "
                    f"Use /api/v1/audit/inspect to see the full mapping attempt."
                )
            })

        # Rename resolved columns to internal names
        rename_map = {v: k for k, v in col_map.items() if v in df.columns}
        df = df.rename(columns=rename_map)

        # Add missing optional columns with defaults. actual_discharge is
        # optional too since load-class files carry only consumption.
        defaults = {
            'hour': None, 'actual_discharge': 0.0, 'actual_charge': 0.0, 'soc': None,
            'grid_demand': None, 'curtailment_mw': 0.0,
            'operator_override': False, 'forecast_price': None,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        # Excel-serial timestamp recovery, then full timestamp matrix.
        df, ts_corrections = _detect_excel_serial_timestamps(df)
        df, ts_format = _parse_timestamps(df)

        # Read-only snapshot for the Data Quality Manifest: taken AFTER
        # timestamp parsing but BEFORE the mutating pipeline (dedupe / coerce /
        # resample), so DQI describes the dataset the customer actually
        # supplied. Never mutated.
        dq_snapshot = df.copy()

        # Clean: drop unparseable timestamps, sort out-of-order, dedupe.
        # Parse-stage flags (banner-header recovery) come first.
        parse_flags = list(df.attrs.get("ingest_flags", []))
        df, dq_flags = _order_and_dedupe_timestamps(df)
        dq_flags = parse_flags + dq_flags

        # If we still have no usable "hour", fall back to a 0..N-1 index. The
        # audit engine only needs ordering; wall-clock time is a nice-to-have
        # for the resolution detector.
        if 'hour' not in df.columns or df['hour'].isnull().all():
            df['hour'] = range(len(df))

        # Coerce numeric columns — tolerates strings like "12.5 MW"; missing
        # prices interpolate (never fake $0), missing power → 0 MW, each with
        # a named flag.
        df, coerce_flags = _coerce_numeric_columns(df)
        dq_flags.extend(coerce_flags)

        # Unit auto-detection (kW→MW, $/kWh→$/MWh)
        df, unit_corrections = _detect_and_apply_units(df)

        # Time-resolution auto-detect + optional resample (only when hour is a
        # real datetime, so this is a no-op for CSV/JSON without a timestamp).
        df, resolution_notes = _detect_and_resample(df)

        # Step duration for the audit engine. Detected from timestamps when
        # available; otherwise the legacy hourly assumption (dt = 1.0).
        res_sec = resolution_notes.get("detected_resolution_sec")
        dt_hours = (res_sec / 3600.0) if res_sec else 1.0
        resolution_notes["dt_hours_used"] = round(dt_hours, 6)

        # Asset specs from meta-columns — first NON-NULL value, because real
        # SCADA exports fill metadata on row 1 only (or on a random row after
        # a historian merge).
        asset_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in df.columns:
                non_null = df[key].dropna()
                if len(non_null):
                    val = non_null.iloc[0]
                    asset_kwargs[key] = val.strip() if isinstance(val, str) else val

        # Initial SoC from the file's first reading when not given explicitly —
        # the MILP's arbitrage budget depends on where the battery started.
        if "soc_init" not in asset_kwargs and "soc" in df.columns:
            soc_series = pd.to_numeric(df["soc"], errors="coerce").dropna()
            if len(soc_series):
                v = float(soc_series.iloc[0])
                v = v / 100.0 if v > 1.5 else v
                asset_kwargs["soc_init"] = min(0.95, max(0.1, v))
                dq_flags.append(_dq("info", "soc_init_from_data",
                                    f"Initial state of charge taken from the file's first reading: "
                                    f"{asset_kwargs['soc_init'] * 100:.0f}%."))
        asset = AssetSpecs(**asset_kwargs)

        # Read-only sensor plausibility checks (comms dropouts, SoC physics,
        # frozen price feed) — run while "hour" is still a datetime.
        dq_flags.extend(_build_sensor_quality_flags(df, dt_hours, asset.p_max, asset.e_max))
        currency = _detect_currency(list(rename_map.keys()) + list(df.columns))

        # Collapse "hour" back to an ordered integer for the audit engine
        if 'hour' in df.columns and pd.api.types.is_datetime64_any_dtype(df['hour']):
            df['hour'] = range(len(df))

        # NaN → None before records: resampling turns absent optional columns
        # (forecast_price, soc, grid_demand) into all-NaN floats, and NaN is
        # not JSON-compliant — it must become null, not poison the response.
        sub = df[[
            'hour', 'price', 'actual_discharge', 'actual_charge',
            'soc', 'grid_demand', 'curtailment_mw', 'operator_override', 'forecast_price'
        ]]
        time_series = sub.astype(object).where(pd.notna(sub), None).to_dict('records')

        result = process_calculation(asset, time_series, dt_hours=dt_hours,
                                     currency=currency or "USD")

        input_sha256 = _hashlib.sha256(contents).hexdigest()

        # ── W1–W4: Data Quality Index + Audit Confidence ────────────────────
        # Data Quality Manifest: read-only integer evidence from the supplied
        # dataset (before any mutation). DQI is the geometric mean of the
        # applicable, asset-agnostic components; absent dimensions are N/A.
        dq_manifest = _collect_data_quality_counts(
            dq_snapshot, asset.p_max, asset.e_max, dt_hours,
            has_forecast_col=("forecast_price" in col_map), col_map=col_map)
        dq_manifest["dataset_sha256"] = input_sha256
        dq_components = _dqi_components_from_manifest(dq_manifest)
        dqi_obj = eda_metrics.build_dqi(dq_components)
        # Audit Confidence — solver-gated, independent of Forecast Reliability.
        solver_proven = not (_dispatch_mode(asset.asset_type) == "storage"
                             and _MILP_LAST.get("status") not in ("Optimal",))
        m_consistency = eda_metrics.model_consistency(result.dq_score_raw)
        ac_obj = eda_metrics.audit_confidence(dqi_obj["value"], m_consistency, solver_proven)
        fr_obj = _forecast_reliability_from_snapshot(dq_snapshot, "forecast_price" in col_map)

        result.data_quality_index = dqi_obj
        result.audit_confidence = ac_obj
        result.forecast_reliability = fr_obj
        result.data_quality_manifest = dq_manifest

        # C2 — chain of custody. Every figure in this audit can be re-derived
        # from the file identified by input_sha256 using the versions below.
        result.audit_manifest = {
            "manifest_version":   "1.0",
            "input_sha256":       input_sha256,
            "original_filename":  file.filename,
            "file_size_bytes":    len(contents),
            "rows_parsed":        int(raw_shape[0]),
            "columns_parsed":     int(raw_shape[1]),
            "steps_audited":      len(time_series),
            "timestamp_range":    {"first": ts_format.get("first_ts"),
                                   "last":  ts_format.get("last_ts")},
            "uploaded_at_utc":    datetime.utcnow().isoformat() + "Z",
            "uploaded_by":        lead.email,
            "parser_version":     PARSER_VERSION,
            "audit_engine_version": ENGINE_VERSION,
            "methodology_version":  METHODOLOGY_VERSION,
            "solver": {
                "name":            SOLVER_NAME,
                "library_version": SOLVER_VERSION,
                "time_limit_s":    45,
                "status":          _MILP_LAST.get("status"),
                # CBC "Optimal" = proven optimal at its default tolerance; a
                # numeric MIP-gap channel is future work — never fabricated.
                "mip_gap":         None,
            },
        }

        # Very large files can hit the MILP wall-clock cap — CBC then returns
        # its best incumbent. Disclose it: the optimum becomes a lower bound.
        if _dispatch_mode(asset.asset_type) == "storage" and \
                _MILP_LAST.get("status") not in ("Optimal",):
            dq_flags.append(_dq("info", "milp_time_capped",
                                f"The optimizer hit its {45}s time cap on {_MILP_LAST.get('steps')} "
                                "steps and returned its best solution so far — the reported optimum "
                                "is a LOWER bound; the true gap can only be larger."))

        # Model/data disagreement: actual "beat" the theoretical optimum →
        # the mapping or specs are wrong, not the operator superhuman. Flag it
        # loudly rather than shipping a quietly-clamped perfect score.
        if (result.dq_score_raw or 0.0) > 1.02:
            dq_flags.append(_dq("warning", "actual_exceeds_optimal",
                                f"Actual captured value exceeds the modeled optimum by "
                                f"{(result.dq_score_raw - 1) * 100:.0f}%. The column mapping or asset "
                                "specs likely don't match this asset — review the resolved mapping "
                                "before quoting these results."))

        # Ch 4.2 third domain case: EDV_optimal ≈ 0 but EDV_actual > 0 is an
        # ERROR STATE per the Reference Manual (profit was mathematically
        # impossible) — surface it, never certify it silently.
        if result.edv_optimal_total <= 0.01 and result.edv_actual_total > 0.01:
            dq_flags.append(_dq("warning", "dq_undefined_error_state",
                                "The model found no economic opportunity in this period, yet the "
                                "asset reports captured value — DQ is undefined here (Ref. Manual "
                                "Ch 4.2 error state). Check asset specs and column mapping."))

        # Reconciliation with the file's OWN gap estimate, when it carries one
        # (many SCADA exports embed a simple-rule gap column). Disclosing the
        # comparison — instead of silently ignoring the column — is what lets
        # an operator trust the MILP figure.
        embedded_col = next(
            (c for c in df.columns
             if "economic_decision_gap" in _normalise_col(str(c))
             or _normalise_col(str(c)).startswith("edg_")
             or _normalise_col(str(c)) in ("edg", "gap_omr", "gap_usd")), None)
        if embedded_col is not None:
            emb = pd.to_numeric(df[embedded_col], errors="coerce").fillna(0.0)
            emb_total = float(emb.sum())
            ours = float(result.total_gap_usd)
            if emb_total > 0:
                ratio = ours / emb_total
                if 0.75 <= ratio <= 1.25:
                    dq_flags.append(_dq("info", "embedded_gap_consistent",
                                        f"Your file carries its own gap estimate ({emb_total:,.0f}) — "
                                        f"consistent with the MILP counterfactual ({ours:,.0f})."))
                else:
                    dq_flags.append(_dq("info", "embedded_gap_differs",
                                        f"Your file carries its own gap estimate ({emb_total:,.0f}), "
                                        f"while the MILP counterfactual finds {ours:,.0f}. The embedded "
                                        "column is typically a simple threshold rule; the MILP evaluates "
                                        "every feasible dispatch trajectory (Ref. Manual Ch 9), so a "
                                        "difference is expected — both are shown for transparency."))

        _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
        background.add_task(_bump_audit_count, lead.token)

        # L3 Economic Knowledge Layer: account users' audits are persisted —
        # the platform remembers. (Blueprint law 1: this row IS the stored
        # Economic State of the audit.) Trial audits stay ephemeral by design.
        # Persistence failure must never break the audit itself.
        try:
            if getattr(lead, "user_id", None):
                _persist_audit_record(lead, result, input_sha256, file.filename)
        except Exception as _pe:
            print(f"[history] WARNING: audit persistence failed (audit unaffected): {_pe}")

        # Non-fatal ingestion notes — surfaced on the response for the frontend
        # to display "we auto-corrected X, confirm before quoting the audit."
        has_notes = (
            unit_corrections or ts_corrections or col_info["fuzzy_scores"]
            or ts_format.get("format_detected") or resolution_notes.get("detected_resolution_sec")
            or dq_flags or currency
        )
        if has_notes:
            result_dict = result.dict()
            result_dict["ingestion_notes"] = {
                "unit_corrections":       unit_corrections,
                "timestamp_corrections":  ts_corrections,
                "fuzzy_column_matches":   col_info["fuzzy_scores"],
                "timestamp_format":       ts_format,
                "time_resolution":        resolution_notes,
                "data_quality":           dq_flags,
                "currency":               currency,
            }
            return JSONResponse(content=_json_safe(result_dict))
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error parsing file: {str(e)}"})


@app.post("/api/v1/audit/inspect")
async def inspect_file(file: UploadFile = File(...)):
    """
    Pre-audit preview per Coverage Tasks 1.6. Returns everything the engine
    would apply if the operator hits "run audit," without spending CPU on MILP.

    Response includes:
      - file_columns, rows, sample_row
      - resolved_mapping   internal → column, from exact + fuzzy tiers
      - fuzzy_column_matches (with score) — anything not exact
      - unresolved_columns — columns we couldn't map, worth manual review
      - unit_corrections   — kW→MW, $/kWh→$/MWh auto-fixes
      - timestamp_corrections — Excel-serial recovery
      - field_warnings     — per missing optional field, the fallback we'd apply
      - will_succeed       — the "safe to proceed" flag
    """
    try:
        contents = await file.read()
        if len(contents) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={
                "detail": f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."})
        df = _parse_file_bytes(contents, file.filename or "")
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Simulate the pre-audit normalisation to preview corrections
        preview = df.copy()
        rename_map = {v: k for k, v in col_map.items() if v in preview.columns}
        preview = preview.rename(columns=rename_map)
        parse_flags = list(df.attrs.get("ingest_flags", []))
        preview, ts_corrections = _detect_excel_serial_timestamps(preview) if "hour" in preview.columns else (preview, [])
        preview, ts_format = _parse_timestamps(preview)
        preview, dq_flags = _order_and_dedupe_timestamps(preview)
        dq_flags = parse_flags + dq_flags
        preview, coerce_flags = _coerce_numeric_columns(preview)
        dq_flags.extend(coerce_flags)
        preview, unit_corrections = _detect_and_apply_units(preview)
        preview, resolution_notes = _detect_and_resample(preview)

        # Same dt / asset-spec resolution the audit will apply, so the preview
        # shows the exact sensor-quality flags the audit response will carry.
        res_sec = resolution_notes.get("detected_resolution_sec")
        dt_hours = (res_sec / 3600.0) if res_sec else 1.0
        resolution_notes["dt_hours_used"] = round(dt_hours, 6)
        meta_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in preview.columns:
                non_null = preview[key].dropna()
                if len(non_null):
                    val = non_null.iloc[0]
                    meta_kwargs[key] = val.strip() if isinstance(val, str) else val
        try:
            asset_preview = AssetSpecs(**meta_kwargs)
        except Exception:
            asset_preview = AssetSpecs()
        dq_flags.extend(_build_sensor_quality_flags(preview, dt_hours,
                                                    asset_preview.p_max, asset_preview.e_max))
        currency = _detect_currency(list(df.columns))

        # Warnings for missing optional fields
        expected_optional = ["actual_charge", "soc", "curtailment_mw", "forecast_price",
                             "operator_override", "grid_demand", "hour"]
        field_warnings = []
        for f in expected_optional:
            if f not in col_map:
                field_warnings.append({
                    "field":    f,
                    "status":   "missing",
                    "fallback": _MISSING_FIELD_FALLBACKS.get(f, "safe default applied."),
                })

        return {
            "file_columns":         list(df.columns),
            "rows":                 len(df),
            "resolved_mapping":     col_map,
            "fuzzy_column_matches": col_info["fuzzy_scores"],
            "unresolved_columns":   [c for c in df.columns if c not in col_map.values()],
            "unit_corrections":     unit_corrections,
            "timestamp_corrections": ts_corrections,
            "timestamp_format":     ts_format,
            "time_resolution":      resolution_notes,
            "data_quality":         dq_flags,
            "currency":             currency,
            "field_warnings":       field_warnings,
            "will_succeed":         "price" in col_map
                                    and ("actual_discharge" in col_map or "actual_charge" in col_map),
            "sample_row":           df.iloc[0].to_dict() if len(df) > 0 else {},
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/historical", response_model=HistoricalResponse)
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

@app.post("/api/share")
async def create_share_link(data: AuditResponse):
    token = str(uuid.uuid4())
    shared_audits[token] = data.dict()
    return {"share_url": f"/share/{token}"}

@app.get("/share/{token}")
async def get_shared_audit(token: str):
    if token in shared_audits:
        return shared_audits[token]
    return JSONResponse(status_code=404, content={"detail": "Report link expired or not found"})

@app.get("/api/latest")
async def get_latest_live_data(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Returns the caller's most recent audit result. Gated on the trial token
    per the tenant-isolation fix — previously this endpoint returned the
    process-global `latest_live_result` and leaked between callers.
    """
    return _latest_by_token.get(lead.token, _EMPTY_LATEST)

# ==========================================
# NEW: EDA Credit Rating
# ==========================================
# ── C3: Certificate signing + verification ──────────────────────────────────
# Ed25519 over the canonical certificate payload. The signing key comes from
# PREDAIOT_CERT_SIGNING_KEY (base64, 32-byte seed). Without a configured key
# the certificate is HONESTLY issued as unsigned — never a fake signature.
# Certificate trust service now lives in app/services/certificate_service.py
# (refactor step 3, service 2). CRYPTO FROZEN — moved byte-for-byte.
from app.services.certificate_service import (  # noqa: E402
    _CERT_KEY_ENV, _VERIFY_BASE_URL, _cert_signing_key, _canonical_json,
    _register_certificate, _build_certificate,
)








# ── Economic Rating: WITHDRAWN ────────────────────────────────────────────────
# The former AAA–CCC composite (weights 40/30/20/10, hard-coded governance
# fallback 8.0, thresholds every 10 points) was an unvalidated construct and
# has been withdrawn under the No-Fabrication rule. Per the hardening
# directive it is NOT re-derived from DQ alone: an Economic Rating represents
# a broader construct than DQ measures, and no defensible methodology exists
# until the EDA Standard defines and validates one.
# See docs/REMOVED_HEURISTICS.md.
# _RATING_WITHDRAWN_LABEL → app/core/constants.py (refactor step 2A)


# ==========================================
# NEW: Rich Real-Time Decision Core (shared by WebSocket + REST)
# ==========================================


# ==========================================
# NEW: Real-Time WebSocket Stream
# ==========================================
@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    Real-time SCADA / EMS data stream — PREDAIOT Economic Advisory Observer.

    Client sends one JSON message per interval (see _live_decision_core docstring
    for the full payload schema). Server responds with a full economic assessment
    plus cumulative session statistics (cumulative_gap, dq_score_live, rating).

    Integration levels:
      Level 1 — Read Only   : SCADA → PREDAIOT (compute only)
      Level 2 — Advisory    : SCADA → PREDAIOT → Recommendation → Operator decides
      Level 3 — Closed Loop : SCADA → PREDAIOT → Dispatch Command → EMS (opt-in only)
    PREDAIOT ships at Level 1–2 by default. Level 3 requires explicit customer opt-in.
    """
    await websocket.accept()
    cumulative_opt = 0.0
    cumulative_act = 0.0
    step_count = 0

    try:
        while True:
            # A field outage is exactly when garbage frames arrive (half-written
            # buffers, proxy timeouts). One bad frame must never kill the
            # session — reply with an error frame and keep listening.
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("frame must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                await websocket.send_json({"error": f"bad frame ignored: {e}",
                                           "step": step_count})
                continue

            # Session resume after a connection drop (grid/network outage):
            # the client replays its last cumulative counters in the first
            # message of the new socket so the session's economics continue
            # instead of resetting to zero. Only honoured before step 1,
            # and applied atomically — garbage resume fields change nothing.
            resume = data.pop("resume", None)
            if isinstance(resume, dict) and step_count == 0:
                try:
                    r_opt = max(0.0, float(resume.get("cumulative_opt", 0) or 0))
                    r_act = float(resume.get("cumulative_act", 0) or 0)
                    r_step = max(0, int(resume.get("step", 0) or 0))
                except (TypeError, ValueError):
                    pass
                else:
                    cumulative_opt, cumulative_act, step_count = r_opt, r_act, r_step

            try:
                step = _live_decision_core(data)
            except Exception as e:
                await websocket.send_json({"error": f"step could not be evaluated: {e}",
                                           "step": step_count})
                continue
            step_count += 1

            cumulative_opt += max(0.0, step["optimal_value"])
            cumulative_act += step["captured_value"]
            dq_live = (cumulative_act / cumulative_opt * 100) if cumulative_opt > 0 else 100.0

            step.update({
                "step":            step_count,
                "cumulative_gap":  round(cumulative_opt - cumulative_act, 2),
                "cumulative_opt":  round(cumulative_opt, 2),
                "cumulative_act":  round(cumulative_act, 2),
                "dq_score_live":   round(dq_live, 1),
                # Economic Rating withdrawn — see _RATING_WITHDRAWN_LABEL.
                "rating":          None,
                "rating_label":    _RATING_WITHDRAWN_LABEL,
            })
            await websocket.send_json(step)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass


# ==========================================
# NEW: Single-Step Live Calculation (polling fallback)
# ==========================================
@app.post("/api/v1/live/step")
async def live_step(data: Dict[str, Any] = Body(...)):
    """
    Single real-time step calculation — REST polling alternative to /ws/live.
    Useful for SCADA/EMS systems that cannot maintain a persistent WebSocket connection.
    Same payload schema and response shape as the WebSocket stream (minus cumulative state).
    """
    return _live_decision_core(data)


# ==========================================
# NEW: Real-time MQTT bridge (Coverage Tasks Area 3.3)
# ==========================================
# Topic structure (per brief 3.3):
#   {prefix}/{asset_id}/telemetry       ← we subscribe here
#   {prefix}/{asset_id}/recommendation  ← we publish per-step decisions
#   {prefix}/{asset_id}/audit           ← reserved for completed audit results
#
# Env config (all optional — bridge stays offline if MQTT_BROKER_HOST unset):
#   MQTT_BROKER_HOST     e.g. mqtt.hivemq.cloud
#   MQTT_BROKER_PORT     default 8883 (TLS) or 1883 (plain)
#   MQTT_USE_TLS         "1" enables TLS
#   MQTT_USERNAME        broker auth
#   MQTT_PASSWORD        broker auth
#   MQTT_TOPIC_PREFIX    default "predaiot"
#   MQTT_QOS             default 1 (at-least-once, per brief 3.3)
#
# Client-cert auth is NOT implemented here — that's a follow-up; needs cert-
# issuance infra that doesn't exist yet. Username+password + TLS is the
# realistic first pilot posture. Broker choice deferred to deployment.

_mqtt_client = None
_mqtt_state = {
    "connected": False, "broker": None, "topic_prefix": None,
    "messages_received": 0, "messages_published": 0, "last_error": None,
}


def _start_mqtt_bridge() -> None:
    """Kick off the MQTT bridge if env is configured. Idempotent, safe if
    paho-mqtt isn't installed (logs and moves on)."""
    global _mqtt_client
    host = os.environ.get("MQTT_BROKER_HOST")
    if not host:
        return  # bridge stays offline — normal for local dev
    if _mqtt_client is not None:
        return  # already running

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        _mqtt_state["last_error"] = "paho-mqtt not installed"
        print("[mqtt] paho-mqtt not installed — MQTT bridge disabled")
        return

    port         = int(os.environ.get("MQTT_BROKER_PORT", "8883"))
    use_tls      = os.environ.get("MQTT_USE_TLS", "1") == "1"
    username     = os.environ.get("MQTT_USERNAME")
    password     = os.environ.get("MQTT_PASSWORD")
    topic_prefix = os.environ.get("MQTT_TOPIC_PREFIX", "predaiot")
    qos          = int(os.environ.get("MQTT_QOS", "1"))

    client = mqtt.Client(client_id=f"predaiot-bridge-{uuid.uuid4().hex[:8]}", clean_session=True)
    if username:
        client.username_pw_set(username, password or "")
    if use_tls:
        client.tls_set()  # default: system CA, TLS 1.2+, verify hostname

    def on_connect(c, _u, _f, rc):
        if rc == 0:
            _mqtt_state["connected"] = True
            _mqtt_state["broker"] = f"{host}:{port}"
            _mqtt_state["topic_prefix"] = topic_prefix
            sub_topic = f"{topic_prefix}/+/telemetry"
            c.subscribe(sub_topic, qos=qos)
            print(f"[mqtt] connected to {host}:{port}, subscribed to {sub_topic} (QoS {qos})")
        else:
            _mqtt_state["last_error"] = f"connect failed rc={rc}"
            print(f"[mqtt] connect failed rc={rc}")

    def on_disconnect(_c, _u, rc):
        _mqtt_state["connected"] = False
        if rc != 0:
            _mqtt_state["last_error"] = f"disconnected rc={rc}"
            print(f"[mqtt] unexpected disconnect rc={rc}")

    def on_message(c, _u, msg):
        """Feed each telemetry message through _live_decision_core, publish
        the recommendation back to {prefix}/{asset_id}/recommendation."""
        _mqtt_state["messages_received"] += 1
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"[mqtt] non-json payload on {msg.topic}: {e}")
            return

        # asset_id from topic: {prefix}/{asset_id}/telemetry
        parts = msg.topic.split("/")
        asset_id = parts[1] if len(parts) >= 3 else payload.get("asset_id") or "unknown"
        payload.setdefault("asset_id", asset_id)

        try:
            result = _live_decision_core(payload)
        except Exception as e:
            _mqtt_state["last_error"] = f"decision core: {e}"
            print(f"[mqtt] decision-core error for {asset_id}: {e}")
            return

        pub_topic = f"{topic_prefix}/{asset_id}/recommendation"
        try:
            c.publish(pub_topic, json.dumps(result), qos=qos, retain=False)
            _mqtt_state["messages_published"] += 1
        except Exception as e:
            _mqtt_state["last_error"] = f"publish: {e}"
            print(f"[mqtt] publish error to {pub_topic}: {e}")

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    try:
        client.connect_async(host, port, keepalive=60)
        client.loop_start()  # background thread — non-blocking
        _mqtt_client = client
    except Exception as e:
        _mqtt_state["last_error"] = f"connect_async: {e}"
        print(f"[mqtt] connect_async failed: {e}")


def _stop_mqtt_bridge() -> None:
    global _mqtt_client
    if _mqtt_client is not None:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception:
            pass
        _mqtt_client = None
        _mqtt_state["connected"] = False


@app.on_event("startup")
async def _mqtt_startup():
    _start_mqtt_bridge()


@app.on_event("shutdown")
async def _mqtt_shutdown():
    _stop_mqtt_bridge()


@app.get("/api/v1/integrations/mqtt/status")
async def mqtt_status(lead: TrialLead = Depends(require_trial_or_user)):
    """Bridge status. Gated on trial token so a stranger can't probe our broker."""
    return dict(_mqtt_state, has_paho=True if _mqtt_client is not None else _mqtt_state.get("last_error") != "paho-mqtt not installed")


# ==========================================
# NEW: Economic Decision Certificate
# ==========================================


@app.get("/api/v1/certificate")
async def get_certificate_for_latest(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Returns an Economic Decision Certificate for the caller's most recent
    audit. Gated on the trial token per the tenant-isolation fix.
    """
    data = _latest_by_token.get(lead.token)
    if not data or data.get("dq_score") is None:
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
    return _build_certificate(data)


@app.post("/api/v1/certificate")
async def generate_certificate_for_audit(data: AuditResponse):
    """Generate a certificate for a provided audit result."""
    return _build_certificate(data.dict())


@app.get("/api/v1/metrics/registry")
async def metrics_registry():
    """
    Public, ungated self-description of every versioned quality metric
    (name, version, equation, inputs, outputs, dependencies, validation
    rules). No customer data. Enables independent reproduction of DQI /
    Audit Confidence from the Data Quality Manifest.
    """
    return {
        "registry_version": "1.0",
        "metrics": eda_metrics.METRIC_REGISTRY,
        "grade_scale": {lo: g for lo, g, _ in eda_metrics._GRADE_BANDS},
        "note": "Grade cut-points are a declared normative scale, not empirical "
                "constants; the numeric value is the primary reproducible quantity.",
    }


@app.get("/api/v1/certificate/verify/{cert_id}")
async def verify_certificate(cert_id: str):
    """
    Public verification portal endpoint (C3) — the target of the certificate
    QR code. Deliberately UNGATED and deliberately minimal: it confirms the
    certificate's existence, integrity, signature and revocation state plus
    the software versions that produced it. It never returns customer
    identity, asset names, or economic figures.
    """
    db = SessionLocal()
    try:
        rec = db.query(CertificateRecord).filter_by(cert_id=cert_id.strip()).first()
    finally:
        db.close()
    if rec is None:
        return JSONResponse(status_code=404, content={
            "certificate_id": cert_id, "valid": False,
            "reason": "No certificate with this ID exists in the registry."})

    signature_ok = None  # None = issued unsigned (disclosed), True/False when signed
    if rec.signature_b64 and rec.public_key_b64:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub = Ed25519PublicKey.from_public_bytes(_base64.b64decode(rec.public_key_b64))
            pub.verify(_base64.b64decode(rec.signature_b64), rec.payload_sha256.encode())
            signature_ok = True
        except Exception:
            signature_ok = False

    return {
        "certificate_id":      rec.cert_id,
        "valid":               (not rec.revoked) and (signature_ok is not False),
        "revoked":             rec.revoked,
        "revocation_reason":   rec.revocation_reason,
        "signature_status":    ("VERIFIED" if signature_ok else
                                "INVALID" if signature_ok is False else
                                "UNSIGNED — issued without a signing key"),
        "payload_sha256":      rec.payload_sha256,
        "dataset_sha256":      rec.input_sha256,
        "audit_scope":         {"asset_type": rec.asset_type, "audit_period": rec.audit_period},
        # Quality grades only — never the underlying customer economics.
        "data_quality_grade":  rec.dqi_grade,
        "confidence_grade":    rec.confidence_grade,
        "methodology_version": rec.methodology_ver,
        "engine_version":      rec.engine_ver,
        "solver_version":      rec.solver_ver,
        "issued_at":           rec.issued_at.isoformat() + "Z",
        "verified_at":         datetime.utcnow().isoformat() + "Z",
    }


# ==========================================
# Audit-report PDF (letterhead overlay)
# ==========================================
# Report rendering service now lives in app/services/report_service.py
# (refactor step 3, service 3). OUTPUT FROZEN — moved byte-for-byte.
from app.services.report_service import _build_audit_pdf  # noqa: E402






@app.post("/api/v1/audit/pdf")
@limiter.limit("20/minute")
async def generate_audit_pdf(
    request: Request,   # noqa: ARG001 — used by rate limiter
    data: AuditResponse,
    lead: TrialLead = Depends(require_trial_or_user),
):
    """
    Produce a branded PDF of the supplied audit result, rendered over the
    corporate letterhead. Gated by trial token like the audit endpoints.
    """
    pdf_bytes = _build_audit_pdf(data.dict())
    safe_asset = "".join(ch for ch in (data.asset_name or "audit") if ch.isalnum() or ch in "-_") or "audit"
    filename = f"PREDAIOT_Audit_{safe_asset}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/audit/ledger.csv")
async def get_audit_ledger_csv(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Economic Energy Ledger (Reference Manual Ch 8.1): the caller's most
    recent audit as a step-by-step CSV. Every headline number on the PDF is
    the sum of a column in this file — anyone can open it and reconcile the
    certificate line by line. R_k rows, fully auditable.
    """
    data = _latest_by_token.get(lead.token)
    if not data or not data.get("decision_log"):
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})

    import csv as _csv
    buf = StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    cur = (data.get("currency") or "USD").lower()
    w.writerow(["step", "hour", f"price_{cur}_per_mwh", "forecast_price",
                "optimal_action_mw", "actual_action_mw",
                f"edv_optimal_step_{cur}", f"edv_actual_step_{cur}",
                f"gap_step_{cur}", f"cumulative_gap_{cur}",
                "decision_type", "soc",
                "curtailment_mw", "operator_override"])
    cum = 0.0
    for i, r in enumerate(data["decision_log"], 1):
        g = float(r.get("gap_step") or 0)
        cum += g
        w.writerow([i, r.get("hour"), r.get("price"), r.get("forecast_price"),
                    r.get("optimal_action"), r.get("actual_action"),
                    r.get("edv_optimal_step"), r.get("edv_actual_step"),
                    round(g, 2), round(cum, 2),
                    r.get("decision_type"), r.get("soc"),
                    r.get("curtailment_mw"), r.get("operator_override")])
    # Trailer: totals for one-glance reconciliation against the PDF.
    w.writerow([])
    w.writerow(["TOTALS", "", "", "", "", "",
                data.get("edv_optimal_total"), data.get("edv_actual_total"),
                data.get("total_gap_usd"), round(cum, 2),
                f"dq_score={data.get('dq_score')}", "", "", ""])
    ga = data.get("gap_attribution") or {}
    if ga:
        w.writerow(["GAP ATTRIBUTION (Ch 8.2)", "", "", "", "", "",
                    f"forecast_gap={ga.get('forecast_gap')}",
                    f"execution_gap={ga.get('execution_gap')}",
                    "", "", "", "", "", ""])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="predaiot_audit_ledger.csv"'},
    )


@app.get("/api/v1/audit/pdf/latest")
async def get_latest_audit_pdf(lead: TrialLead = Depends(require_trial_or_user)):
    """PDF for the caller's most recent audit. Per-tenant cache, no cross-leak."""
    data = _latest_by_token.get(lead.token)
    if not data or data.get("dq_score") is None:
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
    pdf_bytes = _build_audit_pdf(data)
    safe_asset = "".join(ch for ch in (data.get("asset_name") or "audit") if ch.isalnum() or ch in "-_") or "audit"
    filename = f"PREDAIOT_Audit_{safe_asset}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================
# NEW: Claude AI Enhancement Proxy
# ==========================================
@app.post("/api/v1/ai-enhance")
async def ai_enhance(request: Dict[str, Any] = Body(...)):
    """
    Proxy endpoint for Claude AI enhanced commentary.
    Requires ANTHROPIC_API_KEY environment variable.

    Add to your Render / Railway env vars:
      ANTHROPIC_API_KEY = sk-ant-...
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(status_code=503, content={
            "detail": "ANTHROPIC_API_KEY not configured. Add it to your deployment environment variables."
        })
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=request.get("model", "claude-sonnet-4-6"),
            max_tokens=request.get("max_tokens", 1000),
            messages=request.get("messages", []),
        )
        return {"content": [{"type": "text", "text": msg.content[0].text}]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Claude API error: {str(e)}"})



# ==========================================
# 8. Serve Frontend  (must come LAST — StaticFiles at "/" is a catch-all
# that intercepts anything not matched by an earlier route.)
# ==========================================

# Register /health FIRST so it isn't shadowed by the static mount below.
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/db")
def health_db():
    """
    Direct evidence of the storage backend — no inference, no credentials.
    dialect 'sqlite' = ephemeral (data lost on redeploy); 'postgresql' =
    persistent. Row counts double as a persistence signal across deploys.
    """
    info = {
        "boot_id": _BOOT_ID,
        "boot_time": _BOOT_TIME.isoformat() + "Z",
        "dialect": engine.dialect.name,
        "persistent": engine.dialect.name != "sqlite",
        "database_url_configured": bool(os.environ.get("DATABASE_URL")),
        "auth_secret_configured": bool(os.environ.get("PREDAIOT_AUTH_SECRET")),
        "cert_signing_key_configured": bool(os.environ.get("PREDAIOT_CERT_SIGNING_KEY")),
    }
    _sk, _ = _cert_signing_key()
    info["cert_signing_key_status"] = (
        "valid" if _sk else
        ("present_but_invalid" if os.environ.get(_CERT_KEY_ENV) else "absent"))
    if info["cert_signing_key_status"] == "present_but_invalid":
        try:
            import cryptography as _cg_check  # noqa: F401
            _lib_ok = True
        except ImportError:
            info["cert_signing_key_problem"] = "cryptography_library_not_installed"
            _lib_ok = False
        # Corruption class only — never the value. Same normalisation as the loader.
        raw = os.environ.get(_CERT_KEY_ENV, "") if _lib_ok else ""
        cleaned = "".join(raw.strip().strip('"').strip("'").split())
        if _lib_ok:
            try:
                seed = _base64.b64decode(cleaned + "=" * (-len(cleaned) % 4))
                info["cert_signing_key_problem"] = (
                    f"decodes_to_{len(seed)}_bytes_need_32 (value length {len(cleaned)} chars)")
            except Exception:
                info["cert_signing_key_problem"] = (
                    f"not_valid_base64 (value length {len(cleaned)} chars)")
    try:
        with engine.connect() as conn:
            try:
                info["alembic_version"] = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version").scalar()
            except Exception:
                info["alembic_version"] = None
            for t in ("users", "organizations", "assets", "certificate_registry",
                      "audit_records", "economic_states", "decisions", "decision_events",
                      "outcomes", "governance_records", "live_events", "live_states",
                      "reconciliations"):
                try:
                    info[f"rows_{t}"] = conn.exec_driver_sql(
                        f"SELECT count(*) FROM {t}").scalar()
                except Exception:
                    info[f"rows_{t}"] = None
        info["status"] = "connected"
    except Exception as e:
        info["status"] = f"error: {type(e).__name__}"
    return info


try:
    # Resolve relative to THIS file, not the process CWD — uvicorn launched
    # with --app-dir (or from any directory) must still find the build.
    _here = os.path.dirname(os.path.abspath(__file__))
    _candidates = [
        os.path.abspath(os.path.join(_here, "..", "frontend", "dist")),
        os.path.abspath("../frontend/dist"),
    ]
    frontend_path = next((p for p in _candidates if os.path.exists(p)), _candidates[0])
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
        print(f"[startup] Frontend mounted successfully from: {frontend_path}")
    else:
        print(f"[startup] WARNING: Frontend build not found at {frontend_path}.")
        print("[startup] The React app was not built before backend startup — the API will work, but the website will show a blank page.")
        print("[startup] Fix: ensure your Render Build Command runs 'npm run build' inside frontend/ before starting uvicorn.")
except Exception as e:
    print(f"[startup] ERROR mounting frontend: {e}")