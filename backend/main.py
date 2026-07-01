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
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta

# ==========================================
# 1. Database Setup  (CORE LOGIC UNCHANGED — connection made fault-tolerant)
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./predaiot_audit.db")

# Render's managed Postgres sometimes gives "postgres://" — SQLAlchemy 2.x needs "postgresql://"
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DecisionAuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    market_price = Column(Float)
    optimal_action = Column(Float)
    actual_action = Column(Float)
    economic_gap = Column(Float)


class TrialLead(Base):
    """
    7-day free-diagnostic trial token. Each token gates access to the audit
    endpoints and ties anonymous demo runs to a captured lead (email + asset).
    Real auth (Clerk + per-user workspaces) is deferred — this is the minimum
    needed to turn anonymous visitors into CRM leads.
    """
    __tablename__ = "trial_leads"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    asset_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    audit_run_count = Column(Integer, default=0, nullable=False)
    crm_synced = Column(Boolean, default=False, nullable=False)


class APIAccessLog(Base):
    """
    Forensic access log. One row per /api/v1/* request. Foundation for
    "who accessed asset X and when" questions during pilot / procurement.
    Not a full audit trail yet (no request/response bodies, no PII masking),
    but a real starting point.
    """
    __tablename__ = "api_access_log"
    id           = Column(Integer, primary_key=True, index=True)
    timestamp    = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    trial_token  = Column(String, index=True, nullable=True)   # nullable for un-gated hits
    method       = Column(String, nullable=False)
    path         = Column(String, index=True, nullable=False)
    status_code  = Column(Integer, nullable=False)
    client_ip    = Column(String, nullable=True)
    user_agent   = Column(String, nullable=True)
    latency_ms   = Column(Integer, nullable=True)


TRIAL_DURATION_DAYS = 7

# NOTE: Base.metadata.create_all() is intentionally NOT called here at import time.
# It is registered as a FastAPI startup event below (after `app` is created), so that
# uvicorn binds the port FIRST and Render's port scan succeeds, regardless of how long
# the DB connection takes. See the @app.on_event("startup") handler near the FastAPI setup.

# ==========================================
# 2. Data Models  (UNCHANGED CORE + NEW FIELDS)
# ==========================================
class AssetSpecs(BaseModel):
    # Universal fields — works for all energy assets
    asset_type: Optional[str] = "Generic"
    # Supported: BESS | Solar | Wind | Gas | Hydro | Hydrogen | Desalination
    #            Nuclear | OilGas | CHP | Geothermal | Tidal | Generic
    asset_name: Optional[str] = "Energy Asset"
    asset_id:   Optional[str] = "ASSET_01"
    location:   Optional[str] = None
    market:     Optional[str] = None
    p_max:      float = 50.0
    e_max:      float = 100.0
    soc_init:   float = 0.2
    eta_ch:     float = 0.95
    eta_dis:    float = 0.95
    deg_cost:   float = 5.0
    # Cert "ISSUED TO" fields (Coverage Tasks Fix B). Optional — default falls
    # back to "Confidential — Available on Request" in _build_certificate.
    client_name:    Optional[str] = None
    client_company: Optional[str] = None

class TimeStepData(BaseModel):
    hour: int
    price: float
    actual_discharge: float = 0.0
    # Optional enrichment columns accepted from uploaded files
    actual_charge: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[str] = None
    curtailment_mw: Optional[float] = 0.0
    operator_override: Optional[bool] = False
    forecast_price: Optional[float] = None

class AuditRequest(BaseModel):
    asset: AssetSpecs
    time_series: List[TimeStepData]

class DecisionRecord(BaseModel):
    hour: Optional[int] = None
    day: Optional[str] = None
    price: Optional[float] = None
    optimal_action: Optional[float] = None
    actual_action: Optional[float] = None
    edv_optimal_step: Optional[float] = None
    edv_actual_step: Optional[float] = None
    gap_step: Optional[float] = None
    daily_gap: Optional[float] = None
    # Extended decision intelligence fields
    decision_type: Optional[str] = None         # Missed Arbitrage | Correct | Over-Discharge | Idle
    operator_override: Optional[bool] = False
    curtailment_mw: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[str] = None
    forecast_price: Optional[float] = None
    confidence: Optional[float] = None

# ==========================================
# NEW: Extended EDA Metrics Model
# ==========================================
class RootCauseItem(BaseModel):
    category: str
    contribution_pct: float
    loss_usd: float

class OpportunityItem(BaseModel):
    name: str
    description: str
    annual_gain_usd: float
    difficulty: str           # Quick Win | Strategic Initiative | Market Integration
    priority_stars: int       # 1–5 (kept for API compatibility)
    priority_score: int       # 0–100 investment-grade priority
    confidence_pct: float     # statistical confidence %
    investment_type: str      # No CAPEX | Low CAPEX | Requires Investment
    owner: str                # EMS Engineer | Operations | Trading Desk | Asset Manager
    operational_risk: str     # Low | Medium | High
    payback_days: int         # estimated payback period
    evidence: str             # data evidence supporting this opportunity
    intervals_observed: int   # dispatch intervals showing this pattern
    efficiency_gain_pct: float  # expected EDE improvement

class HeatMapCell(BaseModel):
    hour: int
    label: str               # HH:MM
    status: str              # optimal | acceptable | poor | critical
    gap_usd: float
    price: float
    action_taken: str

class EDAMetrics(BaseModel):
    # Section 6 — Economic Decision Quality Metrics
    economic_decision_efficiency: float     # EDE  = captured / potential
    economic_leakage_ratio: float           # ELR  = lost / potential
    dispatch_accuracy: float                # correct dispatches / total
    decision_delay_index: float             # avg timesteps late (0 if perfect)
    forecast_utilization_index: float       # % of steps with forecast provided
    curtailment_recovery_ratio: float       # curtailed MWh potentially rescued
    revenue_stacking_index: int             # number of distinct revenue services used
    economic_intelligence_score: float      # 0–100 composite
    battery_opportunity_capture: Optional[float] = None  # BESS only

class FinancialLeakage(BaseModel):
    period_24h: float
    period_7d: Optional[float] = None
    period_30d: Optional[float] = None
    projection_12m: float
    top_sources: List[dict]                 # [{name, usd, pct}]

class AuditResponse(BaseModel):
    # Core (UNCHANGED field names)
    edv_optimal_total: float
    edv_actual_total: float
    dq_score: float
    total_gap_usd: float
    decision_log: List[DecisionRecord]
    # Extended EDA sections
    asset_name: Optional[str] = "Energy Asset"
    asset_type: Optional[str] = "Generic"
    audit_period_label: Optional[str] = "24 Hours"
    risk_level: Optional[str] = "Moderate"          # Low | Moderate | Severe
    eda_metrics: Optional[EDAMetrics] = None
    root_causes: Optional[List[RootCauseItem]] = None
    opportunities: Optional[List[OpportunityItem]] = None
    heat_map: Optional[List[HeatMapCell]] = None
    financial_leakage: Optional[FinancialLeakage] = None
    ai_commentary: Optional[str] = None
    counterfactual_summary: Optional[str] = None
    # ISSUED TO block (Coverage Tasks Fix B) — echoed from AssetSpecs so the
    # certificate + PDF can render engagement-letter-style header without a
    # second round-trip.
    asset_id: Optional[str] = None
    asset_location: Optional[str] = None
    client_name: Optional[str] = None
    client_company: Optional[str] = None

class HistoricalResponse(BaseModel):
    history_log: List[DecisionRecord]


# ==========================================
# 2.5  Trial Gate & Lead Capture
# ==========================================
# Commercial model (per PREDAIOT v2 brief): Free 7-day diagnostic → paid audit.
# This block turns anonymous /api/v1/audit usage into captured leads. A real
# multi-tenant auth layer (Clerk + Stripe) is deferred until first paying customer.

class TrialStartRequest(BaseModel):
    email: str
    asset_name: Optional[str] = None
    source: Optional[str] = None  # e.g. "landing", "demo-link", "outreach"


class TrialStartResponse(BaseModel):
    token: str
    expires_at: str
    booking_url: str  # surfaced upfront so the frontend can build the expiry CTA without a second request


class TrialStatusResponse(BaseModel):
    email: str
    asset_name: Optional[str] = None
    expires_at: str
    audit_run_count: int
    is_expired: bool


# Set via env. mailto fallback so the CTA always resolves to *something*.
CONSULTATION_BOOKING_URL = os.environ.get(
    "CONSULTATION_BOOKING_URL",
    "mailto:chams@preda-iot.com?subject=PREDAIOT%20Audit%20Consultation"
)

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


def require_trial_token(
    x_trial_token: Optional[str] = Header(default=None, alias="X-Trial-Token"),
) -> TrialLead:
    """
    FastAPI dependency. Validates X-Trial-Token header against TrialLead.
      - missing → 401  (no token)
      - unknown → 401  (bad token)
      - expired → 402  (trial ended — frontend renders booking CTA)
      - valid   → returns the TrialLead (detached). Audit endpoints schedule
                  _bump_audit_count separately so status pings don't count.
    """
    if not x_trial_token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "trial_token_missing",
                "message": "Start your free 7-day diagnostic to run an audit.",
                "booking_url": CONSULTATION_BOOKING_URL,
            },
        )
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == x_trial_token).first()
        if lead is None:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "trial_token_invalid",
                    "message": "Trial token not recognised. Start a fresh diagnostic.",
                    "booking_url": CONSULTATION_BOOKING_URL,
                },
            )
        if lead.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "trial_expired",
                    "message": "Your 7-day free diagnostic has ended. Book a paid audit consultation to continue.",
                    "booking_url": CONSULTATION_BOOKING_URL,
                    "expired_at": lead.expires_at.isoformat() + "Z",
                },
            )
        # Detach by expunging — caller can read fields, can't lazy-load.
        db.expunge(lead)
        return lead
    finally:
        db.close()


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


def _rate_limit_key(request) -> str:
    """
    Rate-limit key: prefer the trial token (per-user) with the client IP as
    fallback (per-connection). Falls back to a stable string if the request
    context is unusual so slowapi never explodes.
    """
    try:
        token = request.headers.get("X-Trial-Token") if hasattr(request, "headers") else None
        if token:
            return f"tok:{token[:16]}"
        return f"ip:{get_remote_address(request)}"
    except Exception:
        return "unknown"


app = FastAPI(title="PREDAIOT Engine")

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


# API access log middleware — writes one row per /api/v1/* request to
# api_access_log for forensic follow-up. Best-effort: a DB failure never
# breaks the response, it just prints and moves on.
@app.middleware("http")
async def _api_access_log(request, call_next):
    import time as _t
    started = _t.perf_counter()
    response = await call_next(request)
    try:
        path = request.url.path or ""
        if path.startswith("/api/v1/"):
            latency_ms = int((_t.perf_counter() - started) * 1000)
            token = request.headers.get("X-Trial-Token")
            client_ip = None
            try:
                client_ip = request.client.host if request.client else None
            except Exception:
                pass
            db = SessionLocal()
            try:
                db.add(APIAccessLog(
                    timestamp=datetime.utcnow(),
                    trial_token=token,
                    method=request.method,
                    path=path,
                    status_code=response.status_code,
                    client_ip=client_ip,
                    user_agent=request.headers.get("user-agent"),
                    latency_ms=latency_ms,
                ))
                db.commit()
            finally:
                db.close()
    except Exception as e:
        print(f"[access-log] non-fatal: {type(e).__name__}: {e}")
    return response

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
_INTERMITTENT_TYPES = {"solar", "pv", "wind", "tidal", "wave"}
_DISPATCHABLE_TYPES = {"gas", "oilgas", "coal", "thermal", "chp", "nuclear", "geothermal", "hydro"}
_LOAD_TYPES         = {"hydrogen", "electrolyzer", "desalination", "desal"}


def _dispatch_mode(asset_type: Optional[str]) -> str:
    t = (asset_type or "").strip().lower()
    if t in _INTERMITTENT_TYPES: return "intermittent"
    if t in _DISPATCHABLE_TYPES: return "dispatchable"
    if t in _LOAD_TYPES:         return "load"
    return "storage"  # default + explicit storage types


def _run_optimizer_storage(asset: AssetSpecs, prices: List[float]) -> dict:
    """Original BESS MILP. Unchanged from v1 — preserves the reference audit."""
    hours = range(len(prices))
    prob = pulp.LpProblem("PREDAIOT_MILP", pulp.LpMaximize)
    p_dis = pulp.LpVariable.dicts("Discharge", hours, lowBound=0, upBound=asset.p_max)
    p_ch  = pulp.LpVariable.dicts("Charge",    hours, lowBound=0, upBound=asset.p_max)
    soc   = pulp.LpVariable.dicts("SOC",        hours, lowBound=0.1, upBound=0.95)
    is_dis = pulp.LpVariable.dicts("IsDis",     hours, cat='Binary')

    prob += pulp.lpSum([
        (prices[t] * p_dis[t]) - (prices[t] * p_ch[t]) - (asset.deg_cost * p_dis[t])
        for t in hours
    ])
    for t in hours:
        prob += p_dis[t] <= asset.p_max * is_dis[t]
        prob += p_ch[t]  <= asset.p_max * (1 - is_dis[t])
        if t == 0:
            prob += soc[t] == asset.soc_init + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        else:
            prob += soc[t] == soc[t-1] + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        if t == max(hours):
            prob += soc[t] == asset.soc_init
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return {t: (p_dis[t].varValue or 0.0) for t in hours}


def _run_optimizer_intermittent(asset: AssetSpecs, time_series_list: list) -> dict:
    """
    Solar / Wind / Tidal: generation is exogenous (driven by irradiance, wind,
    tide). The only economic decision is curtailment. Available capacity at
    step t = actual_discharge + curtailment_mw (capped by p_max). The optimal
    policy exports all of it when price > 0 and curtails when price ≤ 0.

    Note: this gives a non-trivial audit ONLY when curtailment is logged. If
    `curtailment_mw` is always 0 in the input, the optimal collapses to the
    actual and DQ → 1.0 — which is the correct answer in that case.
    """
    out = {}
    for i, ts in enumerate(time_series_list):
        price = float(ts.get("price", 0))
        actual = float(ts.get("actual_discharge", 0))
        curt = float(ts.get("curtailment_mw", 0))
        available = min(asset.p_max, max(0.0, actual + curt))
        out[i] = available if price > asset.deg_cost else 0.0
    return out


def _run_optimizer_dispatchable(asset: AssetSpecs, prices: List[float]) -> dict:
    """
    Gas / Thermal / Nuclear / Geothermal / non-storage Hydro: the merit-order
    rule. Run at p_max when price exceeds marginal generation cost (`deg_cost`
    is interpreted as $/MWh marginal cost, including fuel/efficiency for gas).
    Idle otherwise. Per-step, no time coupling. (Unit-commitment ramp / min-up
    constraints are deliberately out of scope for v1; the optimal here is an
    economic upper bound, which is the correct ceiling for an audit.)
    """
    return {i: (asset.p_max if p > asset.deg_cost else 0.0) for i, p in enumerate(prices)}


def _load_consumption_series(time_series_list: list) -> List[float]:
    """
    For load-class assets the consumption column is `actual_charge`. Many
    uploads only fill `actual_discharge` though, so we fall back to that if
    charge is uniformly zero — better a working audit than a strict schema
    error at ingest.
    """
    charge = [float(ts.get("actual_charge", 0) or 0) for ts in time_series_list]
    if sum(charge) > 0:
        return charge
    return [float(ts.get("actual_discharge", 0) or 0) for ts in time_series_list]


def _run_optimizer_load(asset: AssetSpecs, time_series_list: list) -> dict:
    """
    Electrolyzer / Desalination / large flexible loads. The load has to meet a
    production target (H₂ tonnes/day, m³/day of water, etc.) — the decision is
    WHEN to consume, not whether to. The audit takes the observed total energy
    consumed as the target and asks: could the same total have been met at a
    lower electricity cost?

    Optimal policy: greedily allocate p_max to the cheapest steps until the
    observed total consumption is met. Any remainder goes into the next-cheapest
    step at a partial rate. No time coupling (no product-storage constraint) —
    this is the merit-order equivalent for loads.
    """
    prices = [float(ts.get("price", 0) or 0) for ts in time_series_list]
    consumption = _load_consumption_series(time_series_list)
    total_needed = sum(consumption)
    n = len(prices)
    optimal = {i: 0.0 for i in range(n)}
    if total_needed <= 0 or n == 0:
        return optimal

    # Ascending-price greedy fill: cheapest hour first, run at p_max until the
    # daily energy target is met, then partial-fill the boundary step.
    order = sorted(range(n), key=lambda i: prices[i])
    remaining = total_needed
    for i in order:
        if remaining <= 0:
            break
        take = min(asset.p_max, remaining)
        optimal[i] = take
        remaining -= take
    return optimal


def run_optimizer(asset: AssetSpecs, time_series_list: list) -> dict:
    """
    Dispatch router. Picks the right optimizer for the asset class and returns
    `{step_index: optimal_dispatch_mw}`. Defaults to the storage MILP so legacy
    audits (BESS, asset_type unset / 'Generic') produce identical numbers.
    """
    mode = _dispatch_mode(asset.asset_type)
    if mode == "intermittent":
        return _run_optimizer_intermittent(asset, time_series_list)
    if mode == "load":
        return _run_optimizer_load(asset, time_series_list)
    prices = [float(ts.get("price", 0)) for ts in time_series_list]
    if mode == "dispatchable":
        return _run_optimizer_dispatchable(asset, prices)
    return _run_optimizer_storage(asset, prices)

# ==========================================
# 5. NEW: EDA Intelligence Engine
# ==========================================
def _classify_decision(opt: float, act: float, price: float, threshold: float = 5.0) -> tuple:
    """Returns (decision_type, confidence)"""
    gap = (opt - act) * price
    if abs(opt - act) < 0.5:
        return "Correct Dispatch", 0.96
    if opt > threshold and act < 0.5:
        return "Missed Arbitrage", min(0.99, 0.80 + (price / 200))
    if act > opt + threshold:
        return "Over-Dispatch", 0.85
    if opt < threshold and act < 0.5:
        return "Correct Idle", 0.92
    if opt > threshold and 0 < act < opt:
        return "Partial Capture", 0.78
    return "Sub-optimal Dispatch", 0.70

def _build_root_causes(
    decision_log: List[DecisionRecord],
    total_gap: float,
    total_edv_opt: float,
) -> List[RootCauseItem]:
    """
    Attribute the Economic Gap to category-level root causes.

    Denominator note (P0 fix — Coverage Tasks v1): contribution_pct expresses
    each category as a fraction of TOTAL ECONOMIC POTENTIAL (EDV_optimal), not
    of total_gap. Using total_gap was a real bug: total_gap = Σ gap_step sums
    both positive AND negative step-gaps (operator-override steps that beat
    the MILP contribute negative), while category loss sums only positives —
    the ratio could exceed 100% (observed: "Missed Arbitrage 152.2%"). Using
    total_edv_opt guarantees ≤ 100% because Σ positive_gap ≤ Σ optimal_edv.
    We also min(100, …) as belt-and-suspenders. Curtailment attribution is
    a secondary tag (double-counts by design — flagged for a follow-up).
    """
    cats = {
        "Missed Arbitrage":     0.0,
        "Schedule-based Dispatch": 0.0,
        "Partial Capture":      0.0,
        "Over-Dispatch":        0.0,
        "Curtailment":          0.0,
        "SOC Constraint":       0.0,
    }
    for rec in decision_log:
        gap = rec.gap_step or 0
        if gap <= 0:
            continue
        dt = rec.decision_type or ""
        if "Missed Arbitrage" in dt:
            cats["Missed Arbitrage"] += gap
        elif "Partial" in dt:
            cats["Partial Capture"] += gap
        elif "Over" in dt:
            cats["Over-Dispatch"] += gap
        else:
            cats["Schedule-based Dispatch"] += gap
        if (rec.curtailment_mw or 0) > 0:
            cats["Curtailment"] += gap * 0.15

    denom = total_edv_opt if total_edv_opt and total_edv_opt > 0 else 0.0
    result = []
    for cat, loss in cats.items():
        if loss > 0 and denom > 0:
            pct = min(100.0, (loss / denom) * 100.0)
            result.append(RootCauseItem(
                category=cat,
                contribution_pct=round(pct, 1),
                loss_usd=round(loss, 2),
            ))
    result.sort(key=lambda x: x.contribution_pct, reverse=True)
    return result[:6]

def _opp(name, description, share, annual, total_gap, **fields) -> OpportunityItem:
    """Small helper — every opportunity shares the same shape, so factor out
    the arithmetic (annual_gain_usd, efficiency_gain_pct) and pass the rest."""
    return OpportunityItem(
        name=name,
        description=description,
        annual_gain_usd=round(annual * share, 0),
        efficiency_gain_pct=round(annual * share / max(1, total_gap) * 100, 1),
        **fields,
    )


def _ops_storage(annual, total_gap, stats) -> List[OpportunityItem]:
    """BESS / Pumped Hydro / storage-with-cycles."""
    total, missed, partial, curtail = stats["total"], stats["missed"], stats["partial"], stats["curtail"]
    curtail_ivals = stats["curtail_ivals"]
    return [
        _opp("Charging Window Optimization",
             "Shift battery charging to off-peak periods (00:00–05:00) to maximise arbitrage spread. "
             "Replace fixed schedule with rolling 4-hour price forecast trigger.",
             0.28, annual, total_gap,
             difficulty="Quick Win", priority_stars=5, priority_score=100,
             confidence_pct=round(min(99.5, 85 + (missed / total) * 15), 1),
             investment_type="No CAPEX", owner="EMS Engineer", operational_risk="Low", payback_days=0,
             evidence=f"Detected across {missed} dispatch intervals with chronic off-peak charging conflict.",
             intervals_observed=missed),
        _opp("Curtailment Recovery",
             "Absorb curtailed generation by charging the storage asset during curtailment events "
             "instead of wasting available energy. Captures otherwise-spilled economic value.",
             0.35, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=5, priority_score=98,
             confidence_pct=round(min(99.0, 80 + (curtail / max(1, total)) * 20), 1),
             investment_type="No CAPEX", owner="Operations", operational_risk="Low", payback_days=(0 if curtail > 0 else 14),
             evidence=f"{round(curtail, 1)} MWh curtailed during audit period — all recoverable.",
             intervals_observed=curtail_ivals),
        _opp("Reserve Market Participation",
             "Stack Frequency Containment Reserve (FCR) or Spinning Reserve on top of energy arbitrage. "
             "Available capacity that is idle during low-price windows can earn continuous passive income.",
             0.18, annual, total_gap,
             difficulty="Market Integration", priority_stars=4, priority_score=85, confidence_pct=92.4,
             investment_type="Low CAPEX", owner="Trading Desk", operational_risk="Medium", payback_days=45,
             evidence=f"Asset was idle in {round((total - missed) / total * 100, 0):.0f}% of intervals — capacity available for reserve stacking.",
             intervals_observed=total - missed),
        _opp("Dynamic Dispatch Threshold",
             "Replace fixed price threshold with market-adaptive trigger based on rolling 4-hour forecast. "
             "Captures high-price spikes currently missed by static rules.",
             0.12, annual, total_gap,
             difficulty="Quick Win", priority_stars=4, priority_score=80, confidence_pct=97.1,
             investment_type="No CAPEX", owner="EMS Engineer", operational_risk="Low", payback_days=2,
             evidence=f"{partial} partial-capture events show dispatch threshold is too conservative.",
             intervals_observed=partial),
        _opp("Frequency Regulation Market",
             "Enrol available capacity in primary frequency regulation (FFR / FCR-D). "
             "Earns continuous capacity payments regardless of price level.",
             0.07, annual, total_gap,
             difficulty="Market Integration", priority_stars=3, priority_score=62, confidence_pct=88.7,
             investment_type="Requires Investment", owner="Asset Manager", operational_risk="Medium", payback_days=90,
             evidence="Market data indicates FCR capacity prices support revenue stacking.",
             intervals_observed=0),
    ]


def _ops_intermittent(annual, total_gap, stats) -> List[OpportunityItem]:
    """Solar / Wind / Tidal — no storage, decision space is curtail-vs-export."""
    total, curtail = stats["total"], stats["curtail"]
    curtail_ivals = stats["curtail_ivals"]
    negative_price = stats["negative_price_ivals"]
    return [
        _opp("Negative-Price Curtailment Discipline",
             "Programmatically curtail export during negative-price intervals. Continuing to export "
             "into negative prices means paying the grid to take your energy — every MWh has a real "
             "cost, not zero.",
             0.38, annual, total_gap,
             difficulty="Quick Win", priority_stars=5, priority_score=100,
             confidence_pct=round(min(99.5, 85 + (negative_price / max(1, total)) * 100), 1),
             investment_type="No CAPEX", owner="EMS Engineer", operational_risk="Low", payback_days=0,
             evidence=f"{negative_price} intervals ran into negative prices without curtailment. Immediate SCADA-side inverter throttle would recover the loss.",
             intervals_observed=negative_price),
        _opp("Storage Colocation for Time-Shift",
             "Pair the plant with a colocated BESS to shift midday oversupply into evening peak. "
             "Turns curtailed generation into evening-peak revenue rather than lost value.",
             0.24, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=5, priority_score=94, confidence_pct=91.0,
             investment_type="Requires Investment", owner="Asset Manager", operational_risk="Medium", payback_days=730,
             evidence=f"{curtail_ivals} curtailment intervals concentrated in midday — the classic time-shift profile.",
             intervals_observed=curtail_ivals),
        _opp("Forecast-Weighted Bid Strategy",
             "Bid the plant's next-day output into the day-ahead market with a merit curve informed "
             "by wind/irradiance forecast confidence, instead of a flat price-taker bid.",
             0.14, annual, total_gap,
             difficulty="Market Integration", priority_stars=4, priority_score=82, confidence_pct=88.6,
             investment_type="Low CAPEX", owner="Trading Desk", operational_risk="Low", payback_days=60,
             evidence="Forecast utilisation index below sector benchmark — significant capacity to move from price-taker to price-shaper.",
             intervals_observed=total),
        _opp("Ancillary Services Enrolment",
             "Enrol the inverter fleet in voltage support / reactive power / synthetic inertia markets. "
             "These earn independent of energy price and reward available capacity.",
             0.14, annual, total_gap,
             difficulty="Market Integration", priority_stars=4, priority_score=76, confidence_pct=86.2,
             investment_type="Low CAPEX", owner="Trading Desk", operational_risk="Medium", payback_days=120,
             evidence="Modern IBR-capable inverters can participate in grid support markets during export hours with no fuel penalty.",
             intervals_observed=total),
        _opp("PPA-vs-Merchant Allocation",
             "Optimise the split between fixed-price PPA volume and merchant exposure. Excess merchant "
             "exposure at low prices is the highest-cost mistake this asset class makes.",
             0.10, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=3, priority_score=68, confidence_pct=81.4,
             investment_type="No CAPEX", owner="Asset Manager", operational_risk="Low", payback_days=180,
             evidence="Merchant-tail exposure detected during low-price windows — reallocatable to PPA volume.",
             intervals_observed=0),
    ]


def _ops_dispatchable(annual, total_gap, stats) -> List[OpportunityItem]:
    """Gas / Thermal / Hydro-no-storage / Nuclear / Geothermal / CHP."""
    total, missed, partial = stats["total"], stats["missed"], stats["partial"]
    return [
        _opp("Merit-Order Compliance",
             "Dispatch when market price exceeds the marginal cost of production and idle when it "
             "doesn't. Fixed schedules that ignore price are the largest source of value destruction "
             "in this asset class.",
             0.40, annual, total_gap,
             difficulty="Quick Win", priority_stars=5, priority_score=100,
             confidence_pct=round(min(99.5, 88 + (missed / total) * 12), 1),
             investment_type="No CAPEX", owner="EMS Engineer", operational_risk="Low", payback_days=0,
             evidence=f"{missed} intervals dispatched below marginal cost. Merit-order trigger would eliminate the loss.",
             intervals_observed=missed),
        _opp("Ramp-Rate Optimisation",
             "Align turbine ramp with the price gradient — ramp up as prices rise into peak, ramp "
             "down as they fall. Reduces cycling wear and captures more of the peak shoulder.",
             0.18, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=4, priority_score=84, confidence_pct=91.7,
             investment_type="Low CAPEX", owner="Operations", operational_risk="Medium", payback_days=90,
             evidence=f"{partial} partial-capture events consistent with mistimed ramps.",
             intervals_observed=partial),
        _opp("Startup-Cost Recovery Windowing",
             "Extend runs to amortise startup fuel and maintenance across a longer profitable window "
             "rather than cycling on/off around marginal prices.",
             0.14, annual, total_gap,
             difficulty="Quick Win", priority_stars=4, priority_score=78, confidence_pct=90.4,
             investment_type="No CAPEX", owner="Operations", operational_risk="Low", payback_days=14,
             evidence="Frequent short runs detected — starts likely uneconomic vs. sustained dispatch during peak windows.",
             intervals_observed=total),
        _opp("Spinning Reserve Enrolment",
             "Offer the plant's synchronised capacity into the spinning reserve / operating reserve "
             "market. Earns capacity payments during hours the plant would otherwise idle.",
             0.16, annual, total_gap,
             difficulty="Market Integration", priority_stars=4, priority_score=76, confidence_pct=89.0,
             investment_type="Low CAPEX", owner="Trading Desk", operational_risk="Medium", payback_days=60,
             evidence="Synchronised idle-capacity hours identified — direct qualification for reserve products.",
             intervals_observed=0),
        _opp("Fuel Cost Hedging",
             "Lock the marginal fuel component with forward contracts to stabilise dispatch economics "
             "and lift the confidence of the merit-order trigger.",
             0.12, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=3, priority_score=64, confidence_pct=83.0,
             investment_type="No CAPEX", owner="Trading Desk", operational_risk="Low", payback_days=180,
             evidence="Spot fuel exposure aligned with revenue volatility — hedgeable via monthly forwards.",
             intervals_observed=0),
    ]


def _ops_load(annual, total_gap, stats) -> List[OpportunityItem]:
    """Electrolyzer / Desalination / large flexible loads."""
    total, missed = stats["total"], stats["missed"]
    return [
        _opp("Off-Peak Load Shifting",
             "Shift required daily consumption into the cheapest-price windows. Meets the production "
             "target at a lower unit-electricity cost without changing daily throughput.",
             0.42, annual, total_gap,
             difficulty="Quick Win", priority_stars=5, priority_score=100,
             confidence_pct=round(min(99.5, 85 + (missed / total) * 15), 1),
             investment_type="No CAPEX", owner="EMS Engineer", operational_risk="Low", payback_days=0,
             evidence=f"{missed} intervals consumed at above-median prices with cheaper alternatives available in the same day.",
             intervals_observed=missed),
        _opp("Renewable Co-Optimisation (Behind-the-Meter)",
             "Align consumption with on-site or PPA-linked solar/wind surplus. Where the load can be "
             "matched to renewable generation minute-by-minute, energy cost approaches zero.",
             0.22, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=5, priority_score=92, confidence_pct=90.5,
             investment_type="Low CAPEX", owner="Asset Manager", operational_risk="Low", payback_days=180,
             evidence="Renewable surplus profile aligns well with the plant's flexible operating window.",
             intervals_observed=total),
        _opp("Demand-Response / Grid-Balancing Enrolment",
             "Enrol the flexible load into demand-response / interruptible-load markets. Getting paid "
             "to briefly cut consumption during grid stress is pure economic upside for a load with "
             "product storage buffer.",
             0.14, annual, total_gap,
             difficulty="Market Integration", priority_stars=4, priority_score=80, confidence_pct=87.2,
             investment_type="Low CAPEX", owner="Trading Desk", operational_risk="Medium", payback_days=90,
             evidence="Grid-side capacity payments cover the deferred production cost with room to spare.",
             intervals_observed=0),
        _opp("Product-Storage Buffer Sizing",
             "Increase downstream product buffer (H₂ tank, water reservoir) so production timing "
             "decouples further from delivery. Every hour of buffer is another hour of load-shifting "
             "flexibility.",
             0.12, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=3, priority_score=72, confidence_pct=84.6,
             investment_type="Requires Investment", owner="Asset Manager", operational_risk="Low", payback_days=365,
             evidence="Current buffer capacity limits how much daily production can shift into cheap-hour windows.",
             intervals_observed=0),
        _opp("Curtailment Absorption PPA",
             "Structure a discounted PPA that pays the generator only for otherwise-curtailed MWh. "
             "Turns the load into the natural sink for a nearby wind/solar plant's negative-price "
             "hours.",
             0.10, annual, total_gap,
             difficulty="Strategic Initiative", priority_stars=3, priority_score=68, confidence_pct=82.0,
             investment_type="No CAPEX", owner="Asset Manager", operational_risk="Low", payback_days=120,
             evidence="Adjacent variable-renewable assets show curtailment patterns matching the load's flexible window.",
             intervals_observed=0),
    ]


_SECTOR_OPS = {
    "storage":      _ops_storage,
    "intermittent": _ops_intermittent,
    "dispatchable": _ops_dispatchable,
    "load":         _ops_load,
}


def _build_opportunities(total_gap: float, asset_type: str, decision_log: list = None) -> List[OpportunityItem]:
    """
    Build a prioritised Economic Action Plan™ appropriate to the asset class.

    Routes on dispatch mode so a Solar audit doesn't recommend "Charging Window
    Optimization." Each mode ships 5 curated opportunities plus a mode-agnostic
    "Operator Override Governance" card when overrides > 5.
    """
    annual = total_gap * 365
    log = decision_log or []

    stats = {
        "total":                max(1, len(log)),
        "missed":               sum(1 for d in log if d.decision_type == "Missed Arbitrage"),
        "partial":              sum(1 for d in log if d.decision_type == "Partial Capture"),
        "curtail":              sum(d.curtailment_mw or 0 for d in log),
        "curtail_ivals":        sum(1 for d in log if (d.curtailment_mw or 0) > 0),
        "override":             sum(1 for d in log if d.operator_override),
        "negative_price_ivals": sum(1 for d in log if (d.price or 0) < 0),
    }

    mode = _dispatch_mode(asset_type)
    builder = _SECTOR_OPS.get(mode, _ops_storage)
    ops = builder(annual, total_gap, stats)

    # Mode-agnostic: governance opportunity when operator overrides are material
    override = stats["override"]
    if override > 5:
        ops.insert(2, _opp("Operator Override Governance",
                           "Implement structured override protocol: require economic justification for "
                           f"manual interventions. {override} overrides detected — each carries average leakage risk.",
                           0.08, annual, total_gap,
                           difficulty="Quick Win", priority_stars=4, priority_score=88, confidence_pct=94.2,
                           investment_type="No CAPEX", owner="Operations", operational_risk="Low", payback_days=1,
                           evidence=f"{override} operator overrides detected in audit period. Avg economic cost per override: ${round(total_gap / override, 0):.0f}.",
                           intervals_observed=override))

    return ops

def _build_heat_map(decision_log: List[DecisionRecord]) -> List[HeatMapCell]:
    cells = []
    for rec in decision_log:
        h = rec.hour or 0
        hh = h // 12
        mm = (h % 12) * 5
        label = f"{hh:02d}:{mm:02d}"
        gap = rec.gap_step or 0
        opt = rec.optimal_action or 0
        act = rec.actual_action or 0
        price = rec.price or 0

        if gap <= 0:
            status = "optimal"
        elif gap < price * 1:
            status = "acceptable"
        elif gap < price * 5:
            status = "poor"
        else:
            status = "critical"

        cells.append(HeatMapCell(
            hour=h, label=label, status=status,
            gap_usd=round(gap, 2), price=price,
            action_taken=rec.decision_type or "Unknown"
        ))
    return cells

def _build_eda_metrics(
    decision_log: List[DecisionRecord],
    total_opt: float, total_act: float,
    asset_type: str
) -> EDAMetrics:
    total = len(decision_log)
    correct = sum(1 for d in decision_log if "Correct" in (d.decision_type or ""))
    with_forecast = sum(1 for d in decision_log if d.forecast_price is not None)
    curtailed_mw = sum(d.curtailment_mw or 0 for d in decision_log)
    overrides = sum(1 for d in decision_log if d.operator_override)

    # Same Ch. 4.2 rule as dq_score: no opportunity + nothing captured = full
    # efficiency (no leakage), not the literal 0/0 → 0 fallback.
    _EDV_EPS = 1e-9
    if total_opt > _EDV_EPS:
        ede = total_act / total_opt
    elif abs(total_act) <= _EDV_EPS:
        ede = 1.0
    else:
        ede = 0.0
    elr = 1 - ede
    dispatch_acc = (correct / total) if total > 0 else 0
    fui = (with_forecast / total) if total > 0 else 0

    # EIS: composite 0–100
    eis = round(
        (ede * 45) +           # capture efficiency 45pts
        (dispatch_acc * 30) +  # decision accuracy 30pts
        (fui * 15) +           # forecast utilization 15pts
        (min(1, 1 - elr) * 10) # leakage control 10pts
    ) * 100
    eis = min(100, max(0, round(eis / 100, 1)))  # normalize

    boc = None
    if asset_type in ("BESS", "Hydro"):
        boc = round(dispatch_acc * 100, 1)

    return EDAMetrics(
        economic_decision_efficiency=round(ede * 100, 2),
        economic_leakage_ratio=round(elr * 100, 2),
        dispatch_accuracy=round(dispatch_acc * 100, 2),
        decision_delay_index=round(overrides / max(1, total) * 10, 2),
        forecast_utilization_index=round(fui * 100, 2),
        curtailment_recovery_ratio=round(curtailed_mw, 2),
        revenue_stacking_index=2 if fui > 0.3 else 1,
        economic_intelligence_score=round(eis, 1),
        battery_opportunity_capture=boc
    )

def _build_ai_commentary(
    asset_name: str, total_gap: float, total_opt: float,
    decision_log: List[DecisionRecord], dq: float,
    eda_metrics=None, opportunities: list = None, root_causes: list = None,
) -> str:
    """
    Generates the default (non-Claude) Economic Intelligence Report™.
    Structured like a McKinsey / Big-4 audit finding — used as fallback when
    /api/v1/ai-enhance is not configured, and as the base prompt context for Claude.
    """
    missed = [d for d in decision_log if d.decision_type == "Missed Arbitrage"]
    top3 = sorted(missed, key=lambda x: x.gap_step or 0, reverse=True)[:3]
    top_times = ", ".join([f"{(r.hour or 0)//12:02d}:{((r.hour or 0) % 12)*5:02d}" for r in top3])

    pct          = round((total_gap / total_opt * 100), 1) if total_opt > 0 else 0
    capture_pct  = round(100 - pct, 1)
    eis          = eda_metrics.economic_intelligence_score if eda_metrics else round(dq * 100, 1)
    rating_word  = "CRITICAL" if dq < 0.4 else "MODERATE" if dq < 0.7 else "STRONG"
    recoverable  = max(0, round(pct * 0.68, 1))
    top_opp      = (opportunities[0].name if opportunities else "Market-responsive dispatch")
    top_cause    = (root_causes[0].category if root_causes else "Schedule-based dispatch")
    top_cause_pct = (root_causes[0].contribution_pct if root_causes else 35)

    L = []
    L.append("EXECUTIVE ASSESSMENT")
    L.append(
        f"During the audit period, {asset_name} captured only {capture_pct}% of its available economic "
        f"potential, resulting in a {rating_word} Economic Intelligence Rating."
    )
    L.append(
        "Although the asset remained technically available, dispatch decisions failed to fully respond to "
        "market conditions, causing material value destruction."
        if dq < 0.7 else
        "The asset's dispatch decisions tracked the optimal counterfactual strategy closely throughout "
        "the audit period, with only minor deviations from peak economic performance."
    )
    L.append("")
    L.append("KEY FINDINGS")
    L.append(f"✔ Economic Intelligence Score        {eis} / 100")
    L.append(f"✔ Economic Leakage                   ${total_gap:,.2f}")
    L.append(f"✔ Missed High-Value Intervals         {len(missed)}")
    L.append(f"✔ Largest Opportunity                 {top_opp}")
    L.append("")
    L.append("ROOT CAUSE ANALYSIS")
    L.append(
        f"The audit indicates that the primary source of lost value was decision logic ({top_cause}, "
        f"{top_cause_pct}% contribution), not equipment performance."
    )
    if missed:
        L.append(
            f"The asset remained available throughout {len(missed)} high-price market windows"
            + (f" — most notably at {top_times}" if top_times else "")
            + " — but followed a predefined operating schedule instead of responding dynamically to "
              "economic signals. No hardware limitations were detected; no availability constraints "
              "prevented revenue capture. The lost value originated entirely from dispatch strategy."
        )
    L.append("")
    L.append("OPERATIONAL IMPACT")
    L.append(
        f"Had the dispatch strategy followed the economically optimal schedule, the asset could have "
        f"recovered approximately {recoverable}% additional revenue during the audited period without "
        f"additional hardware investment. Annualised, this represents an estimated ${total_gap*365*0.68:,.0f} "
        f"in recoverable value."
    )
    L.append("")
    L.append("AUDITOR CONCLUSION")
    L.append(
        f"The asset is operationally healthy but economically {'under-optimized' if dq < 0.7 else 'well-optimized'}. "
        + ("Current operating logic prioritizes schedule compliance over value maximization. Replacing "
           "rule-based dispatch with economic optimization would significantly improve financial "
           "performance while preserving all operational constraints."
           if dq < 0.7 else
           "Current operating logic is largely market-responsive. Incremental tuning of dispatch "
           "thresholds would close the remaining gap to full economic optimality.")
    )
    L.append("")
    L.append("RECOMMENDED ACTIONS")
    if opportunities:
        for i, op in enumerate(opportunities[:5], 1):
            L.append(f"")
            L.append(f"Recommendation {i} — {op.name}")
            L.append(f"  Expected Annual Gain    ${op.annual_gain_usd:,.0f}")
            L.append(f"  Implementation          {op.difficulty}")
            L.append(f"  Operational Risk        {op.operational_risk}")
            L.append(f"  Confidence              {op.confidence_pct}%")
            L.append(f"  Owner                   {op.owner}")
            L.append(f"  Priority                {op.priority_score}/100")
            L.append(f"  Status                  Recommended")
    else:
        L.append("  1. Shift charging window to 00:00–05:00 off-peak hours.")
        L.append("  2. Raise discharge trigger threshold with dynamic price floor.")
        L.append("  3. Integrate 4-hour ahead price forecast into dispatch logic.")
        L.append("  4. Enable automatic market-responsive dispatch; reduce operator overrides.")
        L.append("  5. Enroll available capacity in ancillary services to stack revenue streams.")

    return "\n".join(L)

def _risk_level(dq: float) -> str:
    if dq >= 0.70:
        return "Low"
    elif dq >= 0.40:
        return "Moderate"
    return "Severe"

# ==========================================
# 6. Central Calculation Engine  (CORE UNCHANGED + EDA LAYER)
# ==========================================
def process_calculation(asset: AssetSpecs, time_series_list: list, save_to_db: bool = True):
    """
    Runs the MILP + EDV + EDA pipeline. Does NOT touch the per-token cache —
    the endpoint handler is responsible for caching the result under its
    trial token. Keeping the tenant-scoping outside this function preserves
    it as a pure calc engine (no auth coupling).
    """
    optimal_actions = run_optimizer(asset, time_series_list)
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
    peak_price = max((float(ts.get("price", 0) or 0) for ts in time_series_list), default=0.0)

    try:
        for i, ts in enumerate(time_series_list):
            opt_dis  = optimal_actions.get(i, 0.0)
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
                edv_opt_step = (peak_price - price) * opt_dis
                edv_act_step = (peak_price - price) * act_dis
            else:
                edv_opt_step = (price * opt_dis) - (asset.deg_cost * opt_dis)
                edv_act_step = (price * act_dis) - (asset.deg_cost * act_dis)
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
    total_gap = total_edv_opt - total_edv_act

    # Build EDA intelligence layers
    eda_metrics  = _build_eda_metrics(decision_log, total_edv_opt, total_edv_act, asset.asset_type)
    root_causes  = _build_root_causes(decision_log, total_gap, total_edv_opt)
    opportunities = _build_opportunities(total_gap, asset.asset_type, decision_log)
    heat_map     = _build_heat_map(decision_log)
    ai_commentary = _build_ai_commentary(
        asset.asset_name, total_gap, total_edv_opt, decision_log, dq_score,
        eda_metrics=eda_metrics, opportunities=opportunities, root_causes=root_causes,
    )

    top_sources = []
    for rc in root_causes[:5]:
        top_sources.append({"name": rc.category, "usd": rc.loss_usd, "pct": rc.contribution_pct})

    financial_leakage = FinancialLeakage(
        period_24h=round(total_gap, 2),
        projection_12m=round(total_gap * 365, 2),
        top_sources=top_sources
    )

    result = AuditResponse(
        # UNCHANGED core fields
        edv_optimal_total=round(total_edv_opt, 2),
        edv_actual_total=round(total_edv_act, 2),
        dq_score=round(dq_score, 4),
        total_gap_usd=round(total_gap, 2),
        decision_log=decision_log,
        # Extended EDA
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        audit_period_label=f"{len(time_series_list)} Steps ({len(time_series_list)//12}h)",
        risk_level=_risk_level(dq_score),
        eda_metrics=eda_metrics,
        root_causes=root_causes,
        opportunities=opportunities,
        heat_map=heat_map,
        financial_leakage=financial_leakage,
        ai_commentary=ai_commentary,
        counterfactual_summary=(
            f"Under optimal dispatch, {asset.asset_name} would have captured "
            f"${total_edv_opt:,.2f} vs actual ${total_edv_act:,.2f}. "
            f"The counterfactual gap of ${total_gap:,.2f} represents decisions that "
            f"were physically feasible but economically sub-optimal."
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
@limiter.limit("5/hour")
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

# ---- Audit endpoints (gated by trial token) --------------------------------
@app.post("/api/v1/audit", response_model=AuditResponse)
@limiter.limit("10/minute")
async def calculate_gap(
    request: Request,   # noqa: ARG001 — used by rate limiter
    audit_req: AuditRequest,
    background: BackgroundTasks,
    lead: TrialLead = Depends(require_trial_token),
):
    result = process_calculation(audit_req.asset, [ts.dict() for ts in audit_req.time_series])
    _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
    background.add_task(_bump_audit_count, lead.token)
    return result

# ==========================================
# COLUMN ALIAS MAP — fuzzy resolver
# Maps any real-world column name variant → internal name
# ==========================================
COLUMN_ALIASES = {
    # ── price — market / spot price ─────────────────────────────────────────────
    "price": [
        # English — common
        "price", "spot_price", "market_price", "energy_price", "lmp",
        "price_usd", "price_$/mwh", "price_($/mwh)", "price_mwh",
        "clearing_price", "settlement_price", "pool_price", "da_price",
        "rt_price", "wholesale_price", "electricity_price", "tariff",
        "rate", "cost_per_mwh", "mwh_price", "$/mwh", "usd/mwh",
        "omr/mwh", "omr_mwh", "price_omr", "aed/mwh", "sar/mwh",
        # Extended market aliases
        "half_hourly_price", "hhp", "imbalance_price", "balancing_price",
        "nodal_price", "zonal_price", "hub_price", "index_price",
        "pjm_lmp", "ercot_spp", "caiso_lmp", "miso_lmp",
        "epex_price", "n2ex_price", "elspot_price", "belpex_price",
        "omel_price", "gme_price", "aps_price", "negative_price",
        # Oil & Gas
        "gas_price", "gas_price_mmbtu", "fuel_cost", "henry_hub",
        "nbp_price", "ttf_price", "co2_price", "carbon_price",
        # Hydrogen
        "h2_price", "hydrogen_price", "green_h2_price",
        # Arabic aliases (أسماء عربية)
        "السعر", "سعر_الكهرباء", "السعر_الفوري", "سعر_السوق",
        "التعريفة", "سعر_المقاصة", "تكلفة_الطاقة",
    ],

    # ── actual_discharge — actual generation / output / production ──────────────
    "actual_discharge": [
        # English — common
        "actual_discharge", "discharge", "actual_power", "power_output",
        "generation", "actual_generation", "gen_mw", "output_mw",
        "dispatch_mw", "actual_dispatch", "p_actual", "p_out",
        "power_mw", "energy_out", "production", "actual_production",
        "mw_out", "discharge_mw", "bess_discharge", "solar_output",
        "wind_output", "p_gen", "pgen", "p_dis", "pdis",
        "net_generation", "real_power", "active_power",
        "gross_generation", "net_output",
        # Solar
        "solar_generation", "pv_output", "solar_power", "irradiance_mw",
        "dc_power", "ac_power", "inverter_output",
        # Wind
        "wind_generation", "turbine_output", "wind_power",
        "rotor_power", "nacelle_power", "hub_power",
        # Hydro / Pumped hydro
        "hydro_generation", "turbine_generation", "hydro_output",
        "penstock_flow_mw", "dam_output",
        # Gas / thermal
        "gas_generation", "thermal_output", "combined_cycle_output",
        "gt_output", "st_output", "peaker_output", "ocgt_output",
        # Nuclear
        "nuclear_output", "reactor_power", "reactor_output",
        # Hydrogen electrolyzer
        "electrolyzer_power", "electrolyzer_output", "h2_production_power",
        "electrolyzer_mw",
        # Desalination
        "desalination_power", "desal_mw", "ro_power", "msf_power",
        "med_power",
        # Oil & Gas compression / injection
        "compressor_power", "injection_power", "pump_power",
        # Arabic aliases
        "التوليد", "الإنتاج", "القدرة_الفعلية", "الطاقة_المنتجة",
        "الصرف_الفعلي", "الخرج", "الطاقة_الكهربائية",
        "توليد_الطاقة", "إنتاج_الطاقة",
    ],

    # ── hour — timestep / interval index ────────────────────────────────────────
    "hour": [
        "hour", "interval", "timestep", "time_step", "step",
        "period", "slot", "index", "idx", "t", "timestamp",
        "datetime", "time", "date_time", "hour_index",
        "half_hour", "quarter_hour", "five_min", "minute",
        "الوقت", "الساعة", "الفترة", "الفاصل_الزمني",
    ],

    # ── actual_charge — charging power (BESS / pumped hydro / electrolyzer) ─────
    "actual_charge": [
        "actual_charge", "charge", "charge_mw", "p_charge", "pcharge",
        "charging_power", "bess_charge", "charge_power", "p_ch",
        "pumping_power", "pump_power_mw", "h2_load", "electrolyzer_load",
        "الشحن", "طاقة_الشحن",
    ],

    # ── soc — state of charge / reservoir level ──────────────────────────────────
    "soc": [
        "soc", "state_of_charge", "battery_soc", "soc_pct",
        "soc_%", "energy_level", "stored_energy_pct",
        # Hydro reservoir
        "reservoir_level", "water_level_m", "water_level_pct",
        "reservoir_pct", "head_m",
        # Hydrogen tank
        "tank_pressure", "h2_level", "h2_storage_pct",
        # Arabic
        "حالة_الشحن", "مستوى_الطاقة", "مستوى_الخزان",
    ],

    # ── curtailment ───────────────────────────────────────────────────────────────
    "curtailment_mw": [
        "curtailment_mw", "curtailment", "curtailed_mw", "curtailed",
        "clipped_mw", "clipping", "spilled_mw", "spillage",
        "wind_curtailment", "solar_curtailment", "forced_outage_mw",
        "التقليص", "التخفيض_القسري",
    ],

    # ── operator override ────────────────────────────────────────────────────────
    "operator_override": [
        "operator_override", "override", "manual_override",
        "human_override", "manual_dispatch", "operator_intervention",
        "تدخل_المشغل", "التجاوز_اليدوي",
    ],

    # ── forecast price ───────────────────────────────────────────────────────────
    "forecast_price": [
        "forecast_price", "predicted_price", "price_forecast",
        "da_forecast", "price_prediction", "forecast", "f_price",
        "price_forecast_da", "day_ahead_forecast",
        "السعر_المتوقع", "توقع_السعر",
    ],

    # ── grid demand ───────────────────────────────────────────────────────────────
    "grid_demand": [
        "grid_demand", "demand", "load", "system_load",
        "grid_load", "net_load", "demand_level",
        "الطلب", "حمل_الشبكة", "حمل_النظام",
    ],

    # ── asset-specific extras ─────────────────────────────────────────────────────
    # Gas / thermal efficiency
    "fuel_consumption": [
        "fuel_consumption", "fuel_rate", "heat_rate", "gas_consumption",
        "fuel_flow_mmbtu", "gas_flow_mcf",
    ],
    # Hydrogen production volume
    "h2_production_kg": [
        "h2_production_kg", "hydrogen_production", "h2_flow_rate",
        "h2_volume_nm3", "electrolyzer_kg_h",
    ],
    # Desalination
    "water_production_m3": [
        "water_production_m3", "permeate_flow", "product_water",
        "desal_output_m3h", "water_m3",
    ],
}

# Asset spec meta-columns that can optionally appear as file columns
ASSET_META_ALIASES = {
    "asset_type": ["asset_type", "type", "asset_class"],
    "asset_name": ["asset_name", "name", "asset", "plant_name", "site_name"],
    "p_max": ["p_max", "max_power", "capacity_mw", "rated_power", "nameplate_mw"],
    "e_max": ["e_max", "energy_capacity", "battery_capacity_mwh", "storage_mwh"],
    "soc_init": ["soc_init", "initial_soc", "soc_initial"],
    "eta_ch": ["eta_ch", "charge_efficiency", "charging_efficiency"],
    "eta_dis": ["eta_dis", "discharge_efficiency", "discharging_efficiency"],
    "deg_cost": ["deg_cost", "degradation_cost", "wear_cost"],
}

def _normalise_col(name: str) -> str:
    """
    Lowercase and strip punctuation for alias matching.
    Currency symbols, brackets, units-in-parens all get stripped so that
    "Spot Price ($/MWh)" → "spot_price_mwh" and lines up with the "spot_price"
    or "price" aliases (fuzzy tier fills in the rest).
    """
    n = (name or "").lower().strip()
    # Drop stuff that adds no semantic value for matching
    for ch in "()[]{}$€£¥%,;:'\"":
        n = n.replace(ch, "")
    # Whitespace + dashes + slashes normalise to underscore
    for ch in " -/\\":
        n = n.replace(ch, "_")
    # Collapse repeats
    while "__" in n:
        n = n.replace("__", "_")
    return n.strip("_")


_FUZZY_THRESHOLD = 80  # rapidfuzz token_sort_ratio out of 100


def _resolve_columns_verbose(df_cols: list) -> dict:
    """
    Two-tier column resolution.

    Tier 1 — exact alias match against the manually-curated COLUMN_ALIASES /
    ASSET_META_ALIASES tables. Fast, deterministic, unchanged behaviour.

    Tier 2 — fuzzy match (rapidfuzz.token_sort_ratio ≥ 80) for any internal
    field the exact tier didn't resolve. Handles the "close enough" cases:
    "Discharge_MW_avg" → actual_discharge, "PriceUSDperMWh" → price, etc.
    Silently falls back to exact-only if rapidfuzz isn't installed.

    Returns {resolved, match_type, fuzzy_scores} for diagnostics.
    """
    normalised = {c: _normalise_col(c) for c in df_cols}
    all_aliases = {**COLUMN_ALIASES, **ASSET_META_ALIASES}

    resolved = {}
    match_type = {}         # internal → "exact" | "fuzzy"
    fuzzy_scores = {}       # internal → {matched_alias, score, from_col}

    # Tier 1: exact alias match
    for internal, aliases in all_aliases.items():
        for original, norm in normalised.items():
            if norm in aliases and internal not in resolved:
                resolved[internal] = original
                match_type[internal] = "exact"
                break

    # Tier 2: fuzzy match for the remainder
    try:
        from rapidfuzz import fuzz, process as fz_process
    except ImportError:
        fuzz = None
        fz_process = None

    if fuzz is not None:
        used_cols = set(resolved.values())
        candidates = [(orig, norm) for orig, norm in normalised.items() if orig not in used_cols]
        for internal, aliases in all_aliases.items():
            if internal in resolved:
                continue
            best_col, best_score, best_alias = None, 0, None
            for orig, norm in candidates:
                match = fz_process.extractOne(norm, aliases, scorer=fuzz.token_sort_ratio)
                if match is None:
                    continue
                alias, score = match[0], match[1]
                if score > best_score:
                    best_col, best_score, best_alias = orig, score, alias
            if best_score >= _FUZZY_THRESHOLD and best_col is not None:
                resolved[internal] = best_col
                match_type[internal] = "fuzzy"
                fuzzy_scores[internal] = {
                    "matched_alias": best_alias,
                    "score": round(float(best_score), 1),
                    "from_col": best_col,
                }
                candidates = [(o, n) for o, n in candidates if o != best_col]

    return {"resolved": resolved, "match_type": match_type, "fuzzy_scores": fuzzy_scores}


def _resolve_columns(df_cols: list) -> dict:
    """Back-compat wrapper — same shape as before (internal_name → actual_col_name)."""
    return _resolve_columns_verbose(df_cols)["resolved"]


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


def _detect_and_apply_units(df: pd.DataFrame) -> tuple:
    """
    Heuristic unit correction per Coverage Tasks 1.5.

    Power kW → MW: max(actual_discharge) > 500 → treat as kW, divide by 1000.
    Price $/kWh → $/MWh: max(price) < 1.0 → treat as $/kWh, multiply by 1000.

    Returns (df_corrected, corrections_list). Corrections is a plain string list
    to surface in the inspect response so the operator can confirm or override.
    """
    corrections = []

    for col, label in (("actual_discharge", "actual_discharge"),
                       ("actual_charge",    "actual_charge")):
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            m = series.abs().max()
            if pd.notna(m) and m > 500:
                df[col] = series / 1000.0
                corrections.append(f"{label} looked like kW (max {m:.0f}); converted to MW.")

    if "price" in df.columns:
        series = pd.to_numeric(df["price"], errors="coerce")
        m = series.abs().max()
        # Only auto-scale up when max is clearly sub-dollar. > $1 could still be a
        # fair $/MWh price in emerging markets, so don't touch it.
        if pd.notna(m) and 0 < m < 1.0:
            df["price"] = series * 1000.0
            corrections.append(f"price looked like $/kWh (max {m:.3f}); converted to $/MWh.")

    return df, corrections


def _detect_excel_serial_timestamps(df: pd.DataFrame) -> tuple:
    """
    Excel-saved CSVs often serialise timestamps as float days-since-1899-12-30.
    Detection: the timestamp column is entirely numeric and falls in the plausible
    Excel-date range (40000..60000 covers 2009 through 2064). If so, convert to
    real datetime — the resolution detector downstream can then work on it.
    """
    corrections = []
    if "hour" not in df.columns:
        return df, corrections
    series = pd.to_numeric(df["hour"], errors="coerce")
    if series.notna().all() and 40000 < float(series.min()) and float(series.max()) < 60000:
        df["hour"] = pd.to_datetime(series, unit="D", origin="1899-12-30")
        corrections.append("hour column looked like Excel serial timestamps; parsed as datetime.")
    return df, corrections


# Order matters: try the strictest / most-informative parses first. ISO 8601
# (including Z-suffixed and offset-suffixed variants) parses cleanly with just
# `utc=True`; only fall through to Gulf/US slash-date if ISO fails.
_TIMESTAMP_FORMAT_ATTEMPTS = [
    # (label, pandas args to try in `pd.to_datetime(series, **kw)`)
    ("ISO 8601",                    dict(utc=True)),
    ("DD/MM/YYYY (Gulf default)",   dict(dayfirst=True)),
    ("MM/DD/YYYY (US)",             dict(dayfirst=False)),
]


def _parse_timestamps(df: pd.DataFrame) -> tuple:
    """
    Best-effort timestamp parsing for the "hour" column.

    Tries a fixed matrix of formats: ISO 8601 (Z, offset, space), Unix epoch
    (seconds vs milliseconds), then DD/MM (Gulf convention) and MM/DD (US) for
    ambiguous slash-separated dates. Assumes Gulf Standard Time (UTC+4) for
    timezone-naive inputs since that's the sales target (Coverage Tasks 1.4).

    Returns (df, notes). `notes` is a dict with `format_detected` (str or None)
    and, if a datetime column was produced, `first_ts` / `last_ts` ISO strings.
    """
    notes = {"format_detected": None, "first_ts": None, "last_ts": None}
    if "hour" not in df.columns:
        return df, notes

    col = df["hour"]

    # Already datetime? Nothing to do.
    if pd.api.types.is_datetime64_any_dtype(col):
        notes["format_detected"] = "already datetime"
        _fill_ts_bounds(col, notes)
        return df, notes

    # Try Unix epoch first (small integers won't collide with slash dates).
    numeric = pd.to_numeric(col, errors="coerce")
    if numeric.notna().all():
        m = float(numeric.abs().max())
        # Excel-serial range gets handled by _detect_excel_serial_timestamps; skip that here.
        if 40000 < m < 60000:
            pass  # Excel-serial branch owns this
        elif 1e12 < m < 1e14:
            df["hour"] = pd.to_datetime(numeric, unit="ms", utc=True)
            notes["format_detected"] = "Unix epoch (ms)"
            _fill_ts_bounds(df["hour"], notes)
            return df, notes
        elif 1e9 < m < 1e11:
            df["hour"] = pd.to_datetime(numeric, unit="s", utc=True)
            notes["format_detected"] = "Unix epoch (s)"
            _fill_ts_bounds(df["hour"], notes)
            return df, notes

    # String-shaped: run through the format matrix. Accept `object` (legacy
    # pandas) and `str` (pandas 2.1+) alike — the numeric path above handled
    # anything else that could plausibly be a timestamp.
    if not pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_datetime64_any_dtype(col):
        s = col.astype(str)
        for label, kw in _TIMESTAMP_FORMAT_ATTEMPTS:
            try:
                parsed = pd.to_datetime(s, errors="coerce", **kw)
            except (ValueError, TypeError):
                continue
            # Accept a format only if it parses (mostly) everything cleanly.
            if parsed.notna().mean() >= 0.98:
                suffix = ""
                # Timezone-naive → assume Gulf Standard Time (UTC+4). Per brief
                # 1.4: sales target is Oman/GCC, so the local wall-clock reading
                # is what the operator meant when they omitted the tz.
                if parsed.dt.tz is None:
                    parsed = parsed.dt.tz_localize("Asia/Muscat", nonexistent="shift_forward", ambiguous="NaT")
                    suffix = " (Gulf tz assumed)"
                df["hour"] = parsed
                notes["format_detected"] = label + suffix
                _fill_ts_bounds(parsed, notes)
                return df, notes

    return df, notes


def _fill_ts_bounds(series, notes: dict) -> None:
    try:
        notes["first_ts"] = pd.Timestamp(series.iloc[0]).isoformat()
        notes["last_ts"]  = pd.Timestamp(series.iloc[-1]).isoformat()
    except Exception:
        pass


# Standard energy-market resolutions we snap to (seconds)
_STANDARD_INTERVALS = [60, 300, 900, 1800, 3600]  # 1min, 5min, 15min, 30min, 60min


def _detect_and_resample(df: pd.DataFrame) -> tuple:
    """
    If the "hour" column is a real datetime, compute the median inter-step delta,
    snap it to the nearest standard interval, and resample:
      - forward-fill  operational fields (actual_discharge, actual_charge,
        soc, curtailment_mw, operator_override) — these persist between reads
      - linear-interp continuous fields (price, forecast_price) — these vary smoothly

    Skips resampling (with a warning) if more than 20% of the expected steps
    would be missing — better to audit what the operator actually gave us than
    fabricate 20% of the data. Also converts "hour" to an ordered int index at
    the end so process_calculation sees the shape it expects.

    Returns (df, notes). Notes shape:
      { detected_resolution_sec, expected_steps, actual_steps,
        resampled, missing_pct, warning (if any) }
    """
    notes = {
        "detected_resolution_sec": None,
        "detected_resolution_label": None,
        "expected_steps": None,
        "actual_steps": int(len(df)),
        "resampled": False,
        "missing_pct": None,
        "warning": None,
    }
    if "hour" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["hour"]):
        return df, notes

    ts = df["hour"]
    if len(ts) < 3:
        return df, notes

    deltas = ts.diff().dt.total_seconds().dropna()
    median_delta = float(deltas.median())
    if median_delta <= 0:
        return df, notes

    # Snap to the nearest standard interval by log-distance
    import math
    snapped = min(_STANDARD_INTERVALS, key=lambda x: abs(math.log(x) - math.log(median_delta)))
    notes["detected_resolution_sec"] = snapped
    notes["detected_resolution_label"] = {
        60: "1-minute", 300: "5-minute", 900: "15-minute",
        1800: "30-minute", 3600: "60-minute",
    }[snapped]

    span_sec = (ts.iloc[-1] - ts.iloc[0]).total_seconds()
    expected = int(span_sec / snapped) + 1
    notes["expected_steps"] = expected
    missing_pct = max(0.0, (expected - len(df)) / max(1, expected) * 100)
    notes["missing_pct"] = round(missing_pct, 2)

    if missing_pct >= 20.0:
        notes["warning"] = (
            f"Data has {missing_pct:.1f}% missing steps at the detected {notes['detected_resolution_label']} "
            "resolution. Skipping resample — audit uses steps as-provided."
        )
        return df, notes

    # Resample. Set the datetime as index, apply per-column policy, reset.
    df = df.set_index("hour").sort_index()
    op_cols  = [c for c in ("actual_discharge", "actual_charge", "soc",
                            "curtailment_mw", "operator_override") if c in df.columns]
    con_cols = [c for c in ("price", "forecast_price") if c in df.columns]
    rule = f"{snapped}s"

    parts = []
    if op_cols:
        parts.append(df[op_cols].resample(rule).ffill())
    if con_cols:
        # numeric only — linear interp
        parts.append(df[con_cols].apply(pd.to_numeric, errors="coerce").resample(rule).mean().interpolate("linear"))
    # Pass-through anything else (grid_demand etc.) with ffill
    other = [c for c in df.columns if c not in op_cols + con_cols]
    if other:
        parts.append(df[other].resample(rule).ffill())

    df = pd.concat(parts, axis=1).reset_index()
    notes["resampled"] = True
    notes["actual_steps"] = int(len(df))
    return df, notes


def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    """
    Universal file parser — handles CSV/TSV/Excel with automatic encoding detection.

    Encoding resolution order:
      1. BOM bytes  →  UTF-16 / UTF-8-BOM
      2. charset_normalizer (pip install charset-normalizer) auto-detect
      3. chardet fallback
      4. Exhaustive encoding list (Western, Arabic, Cyrillic, CJK …)
      5. Force-decode with replacement characters (never raises)
    """
    fname = (filename or "").lower()

    # ── Excel ──────────────────────────────────────────────────────────────────
    if fname.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(BytesIO(contents))

    # ── JSON ───────────────────────────────────────────────────────────────────
    # Accepts:
    #   1) Flat array of records:      [{"time": ..., "price": ...}, ...]
    #   2) Wrapper with a data array:  {"data": [...]}
    #      or {"timeseries": [...]}, {"time_series": [...]}, {"records": [...]},
    #      {"rows": [...]}, {"items": [...]}
    #   3) Column-oriented dict:       {"time": [...], "price": [...]}
    if fname.endswith(".json"):
        try:
            payload = json.loads(contents.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e.msg} at line {e.lineno}") from e
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            for key in ("data", "timeseries", "time_series", "records", "rows", "items", "values"):
                inner = payload.get(key)
                if isinstance(inner, list):
                    return pd.DataFrame(inner)
            # Column-oriented — every value is a list of the same length
            list_cols = {k: v for k, v in payload.items() if isinstance(v, list)}
            if list_cols and len({len(v) for v in list_cols.values()}) == 1:
                return pd.DataFrame(list_cols)
        raise ValueError(
            "JSON must be an array of records, a wrapper like {\"data\": [...]}, "
            "or a column-oriented dict of same-length arrays."
        )

    # ── XML ────────────────────────────────────────────────────────────────────
    # Common in EMS / SCADA historian exports (OSIsoft PI XML, various DCS).
    # pandas.read_xml handles the standard "list of rows" shape without much
    # coaxing. Lazy import so the app boots without lxml installed.
    if fname.endswith(".xml"):
        try:
            # pandas' read_xml uses lxml under the hood; give a clear error if
            # the operator hasn't installed it (this file path is opt-in).
            return pd.read_xml(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "XML upload requires the 'lxml' package. Install with "
                "`pip install lxml` (already declared in requirements.txt)."
            )
        except Exception as e:
            raise ValueError(
                f"Could not parse XML: {e}. Common shape: a root element with "
                "repeated child rows, each row containing scalar fields."
            ) from e

    # ── Parquet ────────────────────────────────────────────────────────────────
    # Data-lake exports. Lazy import — pyarrow is ~50MB, opt-in per deployment.
    if fname.endswith(".parquet"):
        try:
            return pd.read_parquet(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "Parquet upload requires the 'pyarrow' package (~50MB). Install "
                "with `pip install pyarrow` if your deploy environment can afford it."
            )
        except Exception as e:
            raise ValueError(f"Could not parse Parquet: {e}") from e

    # Separator heuristic
    sep = "\t" if fname.endswith(".tsv") else ","

    # ── BOM detection ──────────────────────────────────────────────────────────
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return pd.read_csv(BytesIO(contents), encoding="utf-16", sep=sep)
        except Exception:
            pass
    if contents[:3] == b"\xef\xbb\xbf":
        try:
            return pd.read_csv(BytesIO(contents), encoding="utf-8-sig", sep=sep)
        except Exception:
            pass

    # ── charset_normalizer auto-detect ─────────────────────────────────────────
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(contents[:20000]).best()
        if result and result.encoding:
            try:
                return pd.read_csv(BytesIO(contents), encoding=str(result.encoding), sep=sep)
            except Exception:
                pass
    except ImportError:
        pass

    # ── chardet fallback ───────────────────────────────────────────────────────
    try:
        import chardet
        detected = chardet.detect(contents[:20000])
        enc_detected = detected.get("encoding") or ""
        if enc_detected:
            try:
                return pd.read_csv(BytesIO(contents), encoding=enc_detected, sep=sep)
            except Exception:
                pass
    except ImportError:
        pass

    # ── Exhaustive encoding list ───────────────────────────────────────────────
    ENCODINGS = [
        # Unicode
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32",
        # Western European
        "latin-1", "cp1252", "iso-8859-15",
        # Arabic (كل ملفات Excel المحلية تستخدم هذا)
        "cp1256", "iso-8859-6", "windows-1256",
        # Central / Eastern European
        "cp1250", "iso-8859-2",
        # Cyrillic
        "cp1251", "iso-8859-5", "koi8-r",
        # CJK
        "gbk", "gb2312", "gb18030", "big5", "shift_jis", "euc-jp", "euc-kr",
        # Misc
        "ascii", "cp437",
    ]
    for enc in ENCODINGS:
        try:
            return pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception:
            continue

    # ── Nuclear fallback: force-decode with Unicode replacement chars ───────────
    try:
        text_content = contents.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(text_content), sep=sep)
        # Strip replacement chars from column names
        df.columns = [str(c).replace("\ufffd", "").strip() for c in df.columns]
        return df
    except Exception:
        pass

    raise ValueError(
        "Could not parse this file. "
        "Please try: (1) save as CSV UTF-8 in Excel → Save As → CSV UTF-8 (comma delimited), "
        "or (2) export as .xlsx. "
        "Your file's encoding was not recognizable after 20+ attempts."
    )


@app.post("/api/v1/audit/file", response_model=AuditResponse)
@limiter.limit("10/minute")
async def audit_from_file(
    request: Request,   # noqa: ARG001 — used by rate limiter
    background: BackgroundTasks,
    file: UploadFile = File(...),
    lead: TrialLead = Depends(require_trial_token),
):
    """
    Universal file ingestion. Accepts real-world exports from any SCADA / EMS /
    historian with a two-tier column resolver, JSON support, unit auto-detection,
    and Excel-serial timestamp recovery.

    Accepted formats: .csv  .tsv  .txt  .xlsx  .xls  .xlsm  .json
    """
    try:
        contents = await file.read()
        df = _parse_file_bytes(contents, file.filename or "")

        # Resolve column aliases (exact → fuzzy)
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Check required fields resolved
        missing_internal = [r for r in ("price", "actual_discharge") if r not in col_map]
        if missing_internal:
            return JSONResponse(status_code=400, content={
                "detail": (
                    f"Could not find required column(s): {missing_internal}. "
                    f"Your file has columns: {list(df.columns)}. "
                    f"Use /api/v1/audit/inspect to see the full mapping attempt."
                )
            })

        # Rename resolved columns to internal names
        rename_map = {v: k for k, v in col_map.items() if v in df.columns}
        df = df.rename(columns=rename_map)

        # Add missing optional columns with defaults
        defaults = {
            'hour': None, 'actual_charge': 0.0, 'soc': None,
            'grid_demand': None, 'curtailment_mw': 0.0,
            'operator_override': False, 'forecast_price': None,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        # Excel-serial timestamp recovery, then full timestamp matrix.
        df, ts_corrections = _detect_excel_serial_timestamps(df)
        df, ts_format = _parse_timestamps(df)

        # If we still have no usable "hour", fall back to a 0..N-1 index. The
        # audit engine only needs ordering; wall-clock time is a nice-to-have
        # for the resolution detector.
        if 'hour' not in df.columns or df['hour'].isnull().all():
            df['hour'] = range(len(df))

        df = df.fillna({'actual_discharge': 0.0, 'actual_charge': 0.0, 'curtailment_mw': 0.0})

        # Coerce numeric columns — tolerates strings like "12.5 MW"
        for col in ('price', 'actual_discharge', 'actual_charge', 'curtailment_mw'):
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r'[^\d.\-]', '', regex=True),
                    errors='coerce'
                ).fillna(0.0)

        # Unit auto-detection (kW→MW, $/kWh→$/MWh)
        df, unit_corrections = _detect_and_apply_units(df)

        # Time-resolution auto-detect + optional resample (only when hour is a
        # real datetime, so this is a no-op for CSV/JSON without a timestamp).
        df, resolution_notes = _detect_and_resample(df)

        # Collapse "hour" back to an ordered integer for the audit engine
        if 'hour' in df.columns and pd.api.types.is_datetime64_any_dtype(df['hour']):
            df['hour'] = range(len(df))

        # Asset specs from meta-columns (first row)
        asset_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in df.columns:
                val = df[key].iloc[0]
                if pd.notna(val):
                    asset_kwargs[key] = val
        asset = AssetSpecs(**asset_kwargs)

        time_series = df[[
            'hour', 'price', 'actual_discharge', 'actual_charge',
            'soc', 'grid_demand', 'curtailment_mw', 'operator_override', 'forecast_price'
        ]].to_dict('records')

        result = process_calculation(asset, time_series)
        _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
        background.add_task(_bump_audit_count, lead.token)

        # Non-fatal ingestion notes — surfaced on the response for the frontend
        # to display "we auto-corrected X, confirm before quoting the audit."
        has_notes = (
            unit_corrections or ts_corrections or col_info["fuzzy_scores"]
            or ts_format.get("format_detected") or resolution_notes.get("detected_resolution_sec")
        )
        if has_notes:
            result_dict = result.dict()
            result_dict["ingestion_notes"] = {
                "unit_corrections":       unit_corrections,
                "timestamp_corrections":  ts_corrections,
                "fuzzy_column_matches":   col_info["fuzzy_scores"],
                "timestamp_format":       ts_format,
                "time_resolution":        resolution_notes,
            }
            return JSONResponse(content=result_dict)
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
        df = _parse_file_bytes(contents, file.filename or "")
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Simulate the pre-audit normalisation to preview corrections
        preview = df.copy()
        rename_map = {v: k for k, v in col_map.items() if v in preview.columns}
        preview = preview.rename(columns=rename_map)
        for col in ('price', 'actual_discharge', 'actual_charge', 'curtailment_mw'):
            if col in preview.columns:
                preview[col] = pd.to_numeric(
                    preview[col].astype(str).str.replace(r'[^\d.\-]', '', regex=True),
                    errors='coerce'
                ).fillna(0.0)
        preview, ts_corrections = _detect_excel_serial_timestamps(preview) if "hour" in preview.columns else (preview, [])
        preview, ts_format = _parse_timestamps(preview)
        preview, unit_corrections = _detect_and_apply_units(preview)
        preview, resolution_notes = _detect_and_resample(preview)

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
            "field_warnings":       field_warnings,
            "will_succeed":         "price" in col_map and "actual_discharge" in col_map,
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
async def get_latest_live_data(lead: TrialLead = Depends(require_trial_token)):
    """
    Returns the caller's most recent audit result. Gated on the trial token
    per the tenant-isolation fix — previously this endpoint returned the
    process-global `latest_live_result` and leaked between callers.
    """
    return _latest_by_token.get(lead.token, _EMPTY_LATEST)

# ==========================================
# NEW: EDA Credit Rating
# ==========================================
def _eda_rating(dq_score: float, eda_metrics=None) -> tuple:
    """
    Composite Economic Decision Performance Rating — like Moody's for energy assets.

    Weighting (mirrors PREDAIOT EDPC Standard v1.0):
        Decision Quality Index  40 pts
        Economic Efficiency     30 pts
        Revenue Capture         20 pts
        Governance Compliance   10 pts
    """
    dq = dq_score  # 0.0–1.0

    if eda_metrics:
        m = eda_metrics if isinstance(eda_metrics, dict) else eda_metrics.dict()
        eff  = (m.get("economic_decision_efficiency", 0) / 100) * 30
        cap  = dq * 20
        gov  = max(0, 10 - m.get("decision_delay_index", 0) * 2)
    else:
        eff  = dq * 30
        cap  = dq * 20
        gov  = 8.0

    composite = round(dq * 40 + eff + cap + gov, 1)  # 0–100

    if composite >= 90: return "AAA", "Outstanding",    "#00E676", composite
    if composite >= 80: return "AA",  "Excellent",      "#69F0AE", composite
    if composite >= 70: return "A",   "Good",           "#B9F6CA", composite
    if composite >= 60: return "BBB", "Acceptable",     "#FFD600", composite
    if composite >= 50: return "BB",  "Below Average",  "#FF9800", composite
    if composite >= 40: return "B",   "Poor",           "#FF5722", composite
    return               "CCC","Critical",              "#FF1744", composite


# ==========================================
# NEW: Rich Real-Time Decision Core (shared by WebSocket + REST)
# ==========================================
def _live_decision_core(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core real-time economic decision evaluation.

    PREDAIOT operates as an Economic Advisory Observer (Integration Level 1–2):
    it reads operational + market data and returns an economic assessment and
    recommendation. It does NOT issue dispatch commands directly to the asset.

    Accepted payload (richer PREDAIOT live schema):
      {
        "timestamp": "2026-07-05T14:05:00Z",
        "asset_id": "Ibri2_BESS",
        "market_price": 85.5,        // falls back to "price" if absent
        "actual_charge": 0,
        "actual_discharge": 20,
        "soc": 0.70,
        "p_max": 50,
        "e_max": 200,
        "eta_charge": 0.95,
        "eta_discharge": 0.95,
        "deg_cost": 5,
        "curtailment": 12,           // MW currently being curtailed/spilled
        "forecast_price": 97,        // next-window forecast price
        "forecast_pv": 180,          // optional forecast generation (solar/wind)
        "grid_limit": 50             // export/interconnection cap
      }
    """
    price       = float(data.get("market_price", data.get("price", 0)))
    actual_dis  = float(data.get("actual_discharge", 0))
    actual_chg  = float(data.get("actual_charge", 0))
    soc         = float(data.get("soc", 0.5))
    p_max       = float(data.get("p_max", 50))
    eta_chg     = float(data.get("eta_charge", data.get("eta_ch", 0.95)))
    deg_cost    = float(data.get("deg_cost", 5))
    curtailment = float(data.get("curtailment", data.get("curtailment_mw", 0)))
    forecast_price = data.get("forecast_price")
    grid_limit  = float(data.get("grid_limit", p_max))
    eff_p_max   = max(0.0, min(p_max, grid_limit))

    can_discharge = soc > 0.2
    can_charge    = soc < 0.9
    discharge_thr = deg_cost * 2.0
    charge_thr    = deg_cost * 0.5

    optimal_discharge, optimal_charge = 0.0, 0.0
    action, action_detail = "HOLD", "No Economic Trigger"

    # Curtailment recovery takes priority — always rational to absorb otherwise-wasted energy
    if curtailment > 0 and can_charge:
        optimal_charge = min(eff_p_max, curtailment)
        action, action_detail = "CHARGE", "Curtailment Recovery"
    elif price > discharge_thr and can_discharge:
        optimal_discharge = eff_p_max
        action, action_detail = "DISCHARGE", "Market Arbitrage"
    elif price < charge_thr and can_charge:
        optimal_charge = eff_p_max
        action, action_detail = "CHARGE", "Off-Peak Charging"

    forecast_note = None
    if forecast_price is not None:
        try:
            fp = float(forecast_price)
            if action == "DISCHARGE" and fp > price * 1.15 and soc > 0.5:
                forecast_note = f"Forecast price ${fp:.2f}/MWh exceeds current by >15% — consider partial hold for higher-value window."
            elif fp < price * 0.85 and action != "DISCHARGE":
                forecast_note = f"Forecast price declining to ${fp:.2f}/MWh — current window is comparatively favourable."
        except (TypeError, ValueError):
            pass

    def _value(dis_mw: float, chg_mw: float) -> float:
        v = max(0.0, (price - deg_cost) * dis_mw)
        if chg_mw > 0:
            recovered = min(chg_mw, curtailment)          # curtailed energy — effectively free
            from_grid = max(0.0, chg_mw - curtailment)     # genuine grid purchase
            v += price * recovered * eta_chg               # value of energy rescued from curtailment
            v -= price * from_grid / max(eta_chg, 0.01)    # cost of charging from the grid
        return v

    optimal_value  = _value(optimal_discharge, optimal_charge)
    captured_value = _value(actual_dis, actual_chg)
    economic_gap   = optimal_value - captured_value

    if optimal_value > 0.01:
        decision_quality = max(0.0, min(150.0, (captured_value / optimal_value) * 100))
    else:
        decision_quality = 100.0 if abs(captured_value) < 0.5 else max(0.0, 100.0 - abs(economic_gap))

    dec_type, conf = _classify_decision(
        optimal_discharge if optimal_discharge > 0 else optimal_charge,
        actual_dis if optimal_discharge > 0 else actual_chg,
        price,
    )

    severity = "HIGH" if economic_gap > 100 else "MEDIUM" if economic_gap > 20 else "LOW"
    rec_power = optimal_discharge if action == "DISCHARGE" else optimal_charge

    recommendation_text = (
        f"{action} {rec_power:.0f} MW — {action_detail}. Expected gain ${economic_gap:.0f}."
        if economic_gap > 10 else "✓ Current dispatch near-optimal — no action required."
    )
    if forecast_note:
        recommendation_text += f" Note: {forecast_note}"

    return {
        "timestamp":          data.get("timestamp"),
        "asset_id":           data.get("asset_id"),
        "price":              price,
        "optimal_action":     round(optimal_discharge if optimal_discharge > 0 else -optimal_charge, 2),
        "actual_action":      round(actual_dis - actual_chg, 2),
        "optimal_value":      round(optimal_value, 2),
        "captured_value":     round(captured_value, 2),
        "economic_gap":       round(economic_gap, 2),
        "gap_step":           round(economic_gap, 2),   # back-compat alias
        "decision_quality":   round(decision_quality, 1),
        "decision_type":      dec_type,
        "confidence":         round(conf * 100, 1),
        "severity":           severity,
        "alert":              economic_gap > 100,
        "recommended_action": action,
        "recommended_power":  round(rec_power, 2),
        "expected_gain":      round(economic_gap, 2),
        "recommendation":     recommendation_text,
        "advisory_level":     "Level 2 — Advisory (Read-Only Observer)",
        "integration_note":   "PREDAIOT does not control the asset. Output is a recommendation for operator or EMS action.",
    }


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
            data = await websocket.receive_json()
            step = _live_decision_core(data)
            step_count += 1

            cumulative_opt += max(0.0, step["optimal_value"])
            cumulative_act += step["captured_value"]
            dq_live = (cumulative_act / cumulative_opt * 100) if cumulative_opt > 0 else 100.0
            rating, rating_label, _, _ = _eda_rating(max(0.0, min(1.0, dq_live / 100)))

            step.update({
                "step":            step_count,
                "cumulative_gap":  round(cumulative_opt - cumulative_act, 2),
                "cumulative_opt":  round(cumulative_opt, 2),
                "cumulative_act":  round(cumulative_act, 2),
                "dq_score_live":   round(dq_live, 1),
                "rating":          rating,
                "rating_label":    rating_label,
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
async def mqtt_status(lead: TrialLead = Depends(require_trial_token)):
    """Bridge status. Gated on trial token so a stranger can't probe our broker."""
    return dict(_mqtt_state, has_paho=True if _mqtt_client is not None else _mqtt_state.get("last_error") != "paho-mqtt not installed")


# ==========================================
# NEW: Economic Decision Certificate
# ==========================================
def _build_certificate(data: dict) -> dict:
    dq         = data.get("dq_score", 0)
    total_gap  = data.get("total_gap_usd", 0)
    opt        = data.get("edv_optimal_total", 0)
    act        = data.get("edv_actual_total", 0)
    m          = data.get("eda_metrics") or {}
    rating, rating_label, rating_color, composite = _eda_rating(dq, m)
    eis        = m.get("economic_intelligence_score", 0) if isinstance(m, dict) else 0
    efficiency = dq * 100
    cert_id    = f"PREDAIOT-EDPC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    # Rating narrative (Moody's style)
    if rating == "AAA":
        narrative = (
            f"Outstanding economic decision performance. Only {round((1-dq)*100,1)}% of achievable value was lost. "
            "Dispatch decisions consistently matched the optimal counterfactual strategy."
        )
    elif rating in ("AA", "A"):
        narrative = (
            f"Strong economic performance with minor optimization opportunities identified. "
            f"{round((1-dq)*100,1)}% leakage is within acceptable bounds. "
            "Targeted schedule adjustments would further improve revenue capture."
        )
    elif rating == "BBB":
        narrative = (
            f"Moderate economic leakage detected ({round((1-dq)*100,1)}% of potential). "
            "Operator overrides and schedule-based dispatch are the primary value destroyers. "
            "Economic audit and EMS reconfiguration recommended within 30 days."
        )
    elif rating in ("BB", "B"):
        narrative = (
            f"Significant economic underperformance detected. {round((1-dq)*100,1)}% of achievable value destroyed. "
            "Immediate review of dispatch strategy and operator protocols required. "
            f"Estimated annual leakage: {round(total_gap * 365, 0):,.0f} USD."
        )
    else:  # CCC
        narrative = (
            f"Critical economic underperformance. Asset captured only {round(dq*100,1)}% of its achievable potential. "
            f"Estimated annual value destruction: ${round(total_gap * 365, 0):,.0f}. "
            "Immediate operational review and EMS reconfiguration required."
        )

    # ── ISSUED BY / ISSUED TO / AUDIT SCOPE (Coverage Tasks Fix B) ─────
    # Big-4-style engagement-letter framing. The letterhead's company name
    # ("Al Shams Investment and Trade Company SPC") is the licensed operator
    # behind PREDAIOT, NOT the audit issuer — so we make that explicit and
    # separate the recipient block cleanly.
    CONFIDENTIAL = "Confidential — Available on Request"
    issuer = {
        "organization":   "PREDAIOT Economic Decision Intelligence",
        "licensed_operator": "Al Shams Investment and Trade Company SPC",
        "email":          "chams@preda-iot.com",
        "domain":         "platform.preda-iot.com",
    }
    recipient = {
        "asset_name":     data.get("asset_name") or CONFIDENTIAL,
        "company":        data.get("client_company") or CONFIDENTIAL,
        "location":       data.get("asset_location") or CONFIDENTIAL,
        "contact_name":   data.get("client_name") or CONFIDENTIAL,
    }
    audit_scope = {
        "asset_id":       data.get("asset_id") or (data.get("asset_name") or CONFIDENTIAL),
        "asset_type":     data.get("asset_type", "Generic"),
        "period":         data.get("audit_period_label", "24h"),
    }

    return {
        "certificate_id":       cert_id,
        "issued_at":            datetime.utcnow().isoformat() + "Z",
        "issuer":               issuer,
        "recipient":            recipient,
        "audit_scope":          audit_scope,
        "asset_name":           data.get("asset_name", "Energy Asset"),
        "asset_type":           data.get("asset_type", "Generic"),
        "audit_period":         data.get("audit_period_label", "24h"),
        "economic_potential":   round(opt, 2),
        "captured_value":       round(act, 2),
        "destroyed_value":      round(total_gap, 2),
        "dq_score":             round(dq * 100, 1),
        "eis_score":            round(eis, 1),
        "composite_score":      round(composite, 1),
        "rating":               rating,
        "rating_label":         rating_label,
        "rating_color":         rating_color,
        "rating_narrative":     narrative,
        "economic_efficiency":  round(efficiency, 1),
        "annual_leakage":       round(total_gap * 365, 2),
        "risk_level":           data.get("risk_level", "Moderate"),
        "key_finding": (
            f"During the audit period, {data.get('asset_name','the asset')} captured "
            f"{round(dq*100,1)}% of its achievable economic value. "
            f"Estimated annual value destruction: ${total_gap*365:,.0f}."
        ),
        "rating_components": {
            "decision_quality_40":    round(dq * 40, 1),
            "economic_efficiency_30": round((m.get("economic_decision_efficiency", 0) / 100 if isinstance(m, dict) else dq) * 30, 1),
            "revenue_capture_20":     round(dq * 20, 1),
            "governance_10":          round(max(0, 10 - (m.get("decision_delay_index", 0) if isinstance(m, dict) else 0) * 2), 1),
        },
        "certified_by":         "PREDAIOT Economic Decision Audit Engine",
        "methodology":          "MILP Counterfactual Optimization (patent-pending)",
        "standard":             "PREDAIOT EDPC Standard v1.0",
        "version":              "2.0.0",
    }


@app.get("/api/v1/certificate")
async def get_certificate_for_latest(lead: TrialLead = Depends(require_trial_token)):
    """
    Returns an Economic Decision Certificate for the caller's most recent
    audit. Gated on the trial token per the tenant-isolation fix.
    """
    data = _latest_by_token.get(lead.token)
    if not data or not data.get("dq_score"):
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
    return _build_certificate(data)


@app.post("/api/v1/certificate")
async def generate_certificate_for_audit(data: AuditResponse):
    """Generate a certificate for a provided audit result."""
    return _build_certificate(data.dict())


# ==========================================
# Audit-report PDF (letterhead overlay)
# ==========================================
_LETTERHEAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "letterhead.pdf")
_LEGACY_EMAIL = b"al.shams.invest@gmail.com"
_REPLACEMENT_EMAIL = "chams@preda-iot.com"


def _load_patched_letterhead():
    """
    Open the letterhead and erase the legacy email from the page content stream.
    The replacement email is NOT substituted in place — the footer font is a
    glyph subset of the original characters, so chars like 'p', 'r', 'd', '-'
    have no glyph and render blank. The new email is drawn in the reportlab
    overlay instead, using a standard Helvetica that has every glyph.

    This is real redaction (text removed from content stream), not a visual
    cover-up — copy-paste from the rendered PDF can't leak the old address.
    """
    from pypdf import PdfReader
    from pypdf.generic import DecodedStreamObject, NameObject

    reader = PdfReader(_LETTERHEAD_PATH)
    page = reader.pages[0]

    contents = page.get_contents()
    if hasattr(contents, "get_data"):
        raw = contents.get_data()
    else:
        raw = b"".join(s.get_data() for s in contents)

    # Replace the email text-show operator with an empty one. Keeps the
    # surrounding font/transform state push valid for the PDF parser.
    legacy_tj = b"(" + _LEGACY_EMAIL + b")Tj"
    if legacy_tj not in raw:
        return reader, page  # letterhead changed shape; leave it alone
    patched = raw.replace(legacy_tj, b"()Tj")

    new_stream = DecodedStreamObject()
    new_stream.set_data(patched)
    page[NameObject("/Contents")] = new_stream
    return reader, page


def _build_audit_pdf(audit: dict) -> bytes:
    """
    Render an Economic Decision Audit one-pager over the corporate letterhead.

    Strategy:
      1. Load letterhead with the legacy email replaced in its content stream.
      2. Build a reportlab overlay (A4) containing only the audit content
         in the safe band (y ≈ 120–680), and merge it onto the letterhead.
    """
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from pypdf import PdfReader, PdfWriter

    W, H = A4

    overlay_buf = BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=A4)

    # ── Footer email (drawn here because the letterhead's font is a
    # glyph subset; see _load_patched_letterhead). Position matches the
    # original Tm matrix: 9pt Helvetica, baseline y=18.8, centred. ───────
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, 18.8, _REPLACEMENT_EMAIL)

    # ── Title strip ────────────────────────────────────────────────────
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, 670, "ECONOMIC DECISION AUDIT")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(60, 655, "Economic Decision Performance Certificate (EDPC) — PREDAIOT")

    # ── Engagement-letter header (ISSUED BY / ISSUED TO / AUDIT SCOPE) ─
    # Coverage Tasks Fix B. Reframes the letterhead so the audit reads as
    # "PREDAIOT issued this to Client X" (Big-4 style) rather than looking
    # like a self-report by the letterhead's legal entity.
    CONFIDENTIAL = "Confidential — Available on Request"
    asset_name    = audit.get("asset_name", "Energy Asset")
    asset_type    = audit.get("asset_type", "Generic")
    asset_id      = audit.get("asset_id") or asset_name
    asset_loc     = audit.get("asset_location") or CONFIDENTIAL
    client_comp   = audit.get("client_company") or CONFIDENTIAL
    period        = audit.get("audit_period_label", "—")
    issued_at     = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    LABEL_C = (0.34, 0.4, 0.5)
    BODY_C  = (0.14, 0.16, 0.2)
    MUTED_C = (0.42, 0.44, 0.48)
    RULE_C  = (0.8, 0.8, 0.84)

    # Two-column engagement-letter header. Left column carries the long
    # legal-operator line and needs more room (LEFT_X to RIGHT_X-8).
    LEFT_X, RIGHT_X, MAX_X = 60, 345, 535
    y = 630
    c.setFillColorRGB(*LABEL_C)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(LEFT_X, y, "ISSUED BY")
    c.drawString(RIGHT_X, y, "ISSUED TO")

    y -= 13
    c.setFillColorRGB(*BODY_C)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT_X, y, "PREDAIOT Economic Decision Intelligence")
    c.drawString(RIGHT_X, y, asset_name[:34])

    y -= 12
    c.setFont("Helvetica-Oblique", 8)  # 8pt italic so the long line fits under RIGHT_X
    c.setFillColorRGB(*MUTED_C)
    c.drawString(LEFT_X, y, "Al Shams Investment and Trade Company SPC (Licensed Operator)")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.34, 0.36, 0.4)
    c.drawString(RIGHT_X, y, client_comp[:40])

    y -= 12
    c.drawString(LEFT_X, y, f"{_REPLACEMENT_EMAIL}  ·  platform.preda-iot.com")
    c.drawString(RIGHT_X, y, asset_loc[:40])

    # Divider + AUDIT SCOPE / ISSUED
    y -= 12
    c.setStrokeColorRGB(*RULE_C)
    c.setLineWidth(0.5)
    c.line(LEFT_X, y, 535, y)
    y -= 12
    c.setFillColorRGB(*LABEL_C)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(LEFT_X, y, "AUDIT SCOPE")
    c.drawString(RIGHT_X, y, "ISSUED")
    y -= 11
    c.setFillColorRGB(*BODY_C)
    c.setFont("Helvetica", 9)
    c.drawString(LEFT_X, y, f"{asset_id}  ·  {asset_type}  ·  {period}")
    c.drawString(RIGHT_X, y, issued_at)

    # ── Executive Summary block ────────────────────────────────────────
    edv_opt = float(audit.get("edv_optimal_total", 0) or 0)
    edv_act = float(audit.get("edv_actual_total", 0) or 0)
    gap     = float(audit.get("total_gap_usd", 0) or 0)
    dq_pct  = float(audit.get("dq_score", 0) or 0) * 100.0
    risk    = (audit.get("risk_level") or "Moderate")

    y = 540
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "EXECUTIVE SUMMARY")
    c.setStrokeColorRGB(0.04, 0.14, 0.22)
    c.setLineWidth(0.6)
    c.line(60, y - 4, 535, y - 4)

    rows = [
        ("Economic Potential",      f"${edv_opt:,.2f}"),
        ("Captured Value",          f"${edv_act:,.2f}"),
        ("Destroyed Value (Gap)",   f"${gap:,.2f}"),
        ("Decision Quality (DQ)",   f"{dq_pct:.1f} / 100"),
        ("Risk Level",              risk.upper()),
    ]
    y -= 22
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 11)
    for label, value in rows:
        c.drawString(72, y, label)
        c.drawRightString(535, y, value)
        y -= 18

    # ── Top Root Causes ────────────────────────────────────────────────
    y -= 12
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "TOP ROOT CAUSES")
    c.line(60, y - 4, 535, y - 4)
    y -= 20

    root_causes = audit.get("root_causes") or []
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 10)
    if root_causes:
        for i, rc in enumerate(root_causes[:3], 1):
            cat = rc.get("category") if isinstance(rc, dict) else getattr(rc, "category", "")
            pct = rc.get("contribution_pct") if isinstance(rc, dict) else getattr(rc, "contribution_pct", 0)
            usd = rc.get("loss_usd") if isinstance(rc, dict) else getattr(rc, "loss_usd", 0)
            c.drawString(72, y, f"{i}. {cat}")
            c.drawRightString(535, y, f"{float(pct or 0):.1f}%   (${float(usd or 0):,.0f})")
            y -= 16
    else:
        c.setFillColorRGB(0.5, 0.5, 0.55)
        c.drawString(72, y, "No material root causes identified in this audit period.")
        y -= 16

    # ── Top Opportunities ──────────────────────────────────────────────
    y -= 12
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "TOP OPPORTUNITIES   (annualised)")
    c.line(60, y - 4, 535, y - 4)
    y -= 20

    opps = audit.get("opportunities") or []
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 10)
    for i, op in enumerate(opps[:3], 1):
        name = op.get("name") if isinstance(op, dict) else getattr(op, "name", "")
        gain = op.get("annual_gain_usd") if isinstance(op, dict) else getattr(op, "annual_gain_usd", 0)
        diff = op.get("difficulty") if isinstance(op, dict) else getattr(op, "difficulty", "")
        c.drawString(72, y, f"{i}. {name}")
        c.setFillColorRGB(0.55, 0.55, 0.6)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(80, y - 12, str(diff))
        c.setFillColorRGB(0.18, 0.18, 0.2)
        c.setFont("Helvetica", 10)
        c.drawRightString(535, y, f"${float(gain or 0):,.0f}")
        y -= 28

    # ── Certification block ───────────────────────────────────────────
    cert = _build_certificate(audit)
    y -= 8
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "CERTIFICATION")
    c.line(60, y - 4, 535, y - 4)
    y -= 18
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 9)
    cert_lines = [
        f"Certificate ID:  {cert.get('certificate_id', '—')}",
        f"Issued:          {cert.get('issued_at', '—')}",
        f"Rating:          {cert.get('rating', '—')}  ({cert.get('rating_label', '')})    Composite {cert.get('composite_score', 0)}/100",
        f"Methodology:     {cert.get('methodology', '—')}",
        f"Standard:        {cert.get('standard', '—')}",
    ]
    for line in cert_lines:
        c.drawString(72, y, line)
        y -= 13

    # Auditor signature strip (handoff line — no pricing, per Sec. 2.2)
    y -= 6
    c.setFillColorRGB(0.4, 0.4, 0.45)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(60, y, "For an Economic Audit consultation, contact " + _REPLACEMENT_EMAIL + ".")

    c.save()
    overlay_buf.seek(0)

    # ── Merge overlay onto the patched letterhead ──────────────────────
    _letterhead_reader, page = _load_patched_letterhead()
    overlay = PdfReader(overlay_buf)
    page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


@app.post("/api/v1/audit/pdf")
@limiter.limit("20/minute")
async def generate_audit_pdf(
    request: Request,   # noqa: ARG001 — used by rate limiter
    data: AuditResponse,
    lead: TrialLead = Depends(require_trial_token),
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


@app.get("/api/v1/audit/pdf/latest")
async def get_latest_audit_pdf(lead: TrialLead = Depends(require_trial_token)):
    """PDF for the caller's most recent audit. Per-tenant cache, no cross-leak."""
    data = _latest_by_token.get(lead.token)
    if not data or not data.get("dq_score"):
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


try:
    frontend_path = os.path.abspath("../frontend/dist")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
        print(f"[startup] Frontend mounted successfully from: {frontend_path}")
    else:
        print(f"[startup] WARNING: Frontend build not found at {frontend_path}.")
        print("[startup] The React app was not built before backend startup — the API will work, but the website will show a blank page.")
        print("[startup] Fix: ensure your Render Build Command runs 'npm run build' inside frontend/ before starting uvicorn.")
except Exception as e:
    print(f"[startup] ERROR mounting frontend: {e}")