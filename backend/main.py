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
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta

# ── Version identity (chain of custody, C2) ─────────────────────────────────
# Stamped into every audit manifest and certificate so an archived report can
# be matched to the exact software that produced it.
ENGINE_VERSION      = "2.1.0"
METHODOLOGY_VERSION = "EDA-Methodology-1.0-draft"
PARSER_VERSION      = "ingest-1.3"
SOLVER_NAME         = "CBC via PuLP"
SOLVER_VERSION      = getattr(pulp, "__version__", "unknown")

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
    # Sprint 1: account users get a linked lead row (token "acct-<user_id>")
    # so every existing audit endpoint works unchanged with per-user isolation.
    user_id = Column(Integer, nullable=True, index=True)


class Organization(Base):
    """
    Tenancy root (blueprint §3/§11). Every business row carries org_id;
    all queries are scoped by the org resolved from the caller's JWT.
    """
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    plan = Column(String, default="trial", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    """
    Account identity (blueprint: auth is COMMODITY — minimal robust JWT+bcrypt,
    no external IdP dependency so sovereign/on-prem deployments work).
    role ∈ {owner, admin, asset_manager, operator, finance, viewer}.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="owner", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Asset(Base):
    """
    Asset registry (blueprint L3 — the Economic Knowledge Layer's anchor).
    Audits, decisions and economic states all hang off an asset row.
    """
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    asset_type = Column(String, default="storage", nullable=False)
    capacity_mw = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    specs_json = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditRecord(Base):
    """
    L3 Economic Knowledge Layer (blueprint §3, MOAT): one row per completed
    account audit — the persisted Economic State of that audit. The full
    AuditResponse is stored verbatim (result_json) so any past audit can be
    reloaded into the dashboard bit-for-bit; headline figures are denormalised
    into columns for cheap history/memory queries.
    """
    __tablename__ = "audit_records"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    asset_id = Column(Integer, index=True, nullable=True)   # linked when upload names one
    asset_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)
    input_sha256 = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=True)
    engine_version = Column(String, nullable=True)
    methodology_version = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    gap_total = Column(Float, nullable=True)          # Theoretical-ceiling gap
    gap_recoverable = Column(Float, nullable=True)    # Recoverable Execution Gap
    dqi = Column(Float, nullable=True)
    dqi_grade = Column(String, nullable=True)
    aei = Column(Float, nullable=True)                # Audit Confidence value
    aei_grade = Column(String, nullable=True)
    top_root_cause = Column(String, nullable=True)
    result_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class SecurityAuditLog(Base):
    """
    Tamper-evident security event log (ISO 27001 A.12.4 direction).
    Each row's hash covers its content AND the previous row's hash, so any
    retroactive edit or deletion breaks the chain from that point forward.
    Chain validity is independently checkable via /api/v1/security/log/verify.
    """
    __tablename__ = "security_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=True)   # NULL = platform-level event
    actor = Column(String, nullable=True)                  # email or token prefix
    action = Column(String, nullable=False)                # e.g. auth.login.ok
    object_ref = Column(String, nullable=True)             # e.g. asset:3, cert:EDPC-…
    at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False, index=True)


def _security_log(action: str, actor: Optional[str] = None,
                  object_ref: Optional[str] = None, org_id: Optional[int] = None) -> None:
    """Append one hash-chained security event. Never fatal to the caller."""
    try:
        db = SessionLocal()
        try:
            last = db.query(SecurityAuditLog).order_by(SecurityAuditLog.id.desc()).first()
            prev = last.row_hash if last else "GENESIS"
            at = datetime.utcnow()
            body = f"{prev}|{org_id}|{actor}|{action}|{object_ref}|{at.isoformat()}"
            row = SecurityAuditLog(org_id=org_id, actor=actor, action=action,
                                   object_ref=object_ref, at=at, prev_hash=prev,
                                   row_hash=_hashlib.sha256(body.encode()).hexdigest())
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[seclog] WARNING: could not append security event ({action}): {e}")


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


class CertificateRecord(Base):
    """
    Certificate registry (C3 — verification system). Stores ONLY what public
    verification needs: hashes, signature, versions, scope metadata. No
    customer identity, no asset economics — a scanned QR must never expose
    customer data.
    """
    __tablename__ = "certificate_registry"
    id                = Column(Integer, primary_key=True, index=True)
    cert_id           = Column(String, unique=True, index=True, nullable=False)
    payload_sha256    = Column(String, index=True, nullable=False)
    signature_b64     = Column(String, nullable=True)   # None = issued unsigned
    public_key_b64    = Column(String, nullable=True)
    asset_type        = Column(String, nullable=True)
    audit_period      = Column(String, nullable=True)
    methodology_ver   = Column(String, nullable=False)
    engine_ver        = Column(String, nullable=False)
    solver_ver        = Column(String, nullable=False)
    input_sha256      = Column(String, nullable=True)   # dataset hash from the manifest
    dqi_grade         = Column(String, nullable=True)   # W1 quality grade (A..E / N/A)
    confidence_grade  = Column(String, nullable=True)   # W1 confidence grade / INDETERMINATE
    issued_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked           = Column(Boolean, default=False, nullable=False)
    revocation_reason = Column(String, nullable=True)


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
    grid_demand: Optional[float] = None
    curtailment_mw: Optional[float] = 0.0
    operator_override: Optional[bool] = False
    forecast_price: Optional[float] = None

class AuditRequest(BaseModel):
    asset: AssetSpecs
    time_series: List[TimeStepData]
    # Step duration in hours (0.0833… = 5-minute SCADA data). Defaults to the
    # legacy hourly assumption so existing callers get identical numbers.
    dt_hours: Optional[float] = 1.0

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
    grid_demand: Optional[float] = None
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
    # No-Fabrication rule (docs/REMOVED_HEURISTICS.md): every numeric field is
    # either derived from ledger rows with a stated formula, or None. The
    # withdrawn fields are retained as keys for API compatibility only.
    name: str
    description: str
    # Derived economics — Σ gap_step over the ledger rows matching this
    # opportunity's classification filter. None on advisory items.
    period_gain: Optional[float] = None
    annual_gain_usd: Optional[float] = None      # period_gain × (8760/span_h), linear extrapolation
    share_of_positive_gap_pct: Optional[float] = None  # period_gain / Σ positive gap_step × 100
    intervals_observed: Optional[int] = None
    evidence: Optional[str] = None
    derivation: Optional[str] = None             # exact ledger filter + formula
    # Qualitative advisory labels (recommendations expressed as text, not
    # dressed as measurements)
    difficulty: Optional[str] = None
    investment_type: Optional[str] = None
    owner: Optional[str] = None
    operational_risk: Optional[str] = None
    # Experimental flag: conceptually valuable, not derivable from this audit
    experimental: bool = False
    experimental_note: Optional[str] = None
    # WITHDRAWN (previously fabricated) — always None
    priority_stars: Optional[int] = None
    priority_score: Optional[int] = None
    confidence_pct: Optional[float] = None
    payback_days: Optional[int] = None
    efficiency_gain_pct: Optional[float] = None

class HeatMapCell(BaseModel):
    hour: int
    label: str               # HH:MM
    status: str              # optimal | acceptable | poor | critical
    gap_usd: float
    price: float
    action_taken: str

class EDAMetrics(BaseModel):
    # Section 6 — Economic Decision Quality Metrics.
    # Only ratios derivable from ledger rows are populated. Withdrawn
    # composite/invented-scale fields are retained as None for API
    # compatibility (docs/REMOVED_HEURISTICS.md).
    economic_decision_efficiency: float     # EDE = EDV_act / EDV_opt × 100 (Ch 4.2 domain rules)
    economic_leakage_ratio: float           # ELR = 100 − EDE
    dispatch_accuracy: float                # steps classified Correct / total × 100
    forecast_utilization_index: float       # steps with forecast present / total × 100
    override_rate_pct: Optional[float] = None      # override-flagged steps / total × 100
    curtailed_energy_mwh: Optional[float] = None   # Σ curtailment_mw × Δt
    # WITHDRAWN (previously fabricated) — always None
    decision_delay_index: Optional[float] = None
    curtailment_recovery_ratio: Optional[float] = None
    revenue_stacking_index: Optional[int] = None
    economic_intelligence_score: Optional[float] = None
    battery_opportunity_capture: Optional[float] = None

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
    # Unclamped DQ ratio. > 1.0 signals model/data disagreement (bad column
    # mapping or asset specs) — ingestion turns that into a data-quality flag.
    dq_score_raw: Optional[float] = None
    total_gap_usd: float
    # Currency the uploaded data is denominated in (detected from column
    # names, e.g. "solar_revenue_omr" → OMR). PDF + certificate render this
    # instead of assuming dollars. "USD" = legacy default.
    currency: Optional[str] = "USD"
    # Offline audits benchmark against ETL — the perfect-foresight hindsight
    # optimum (Reference Manual Ch 6.1) — so dq_score is formally the ECF.
    benchmark: Optional[str] = "ETL (perfect-foresight hindsight, Ref. Manual Ch 6.1)"
    # Ch 8.2 split: {forecast_gap, execution_gap, recommended_value, method}.
    # Present only for storage audits whose file carries a forecast column.
    gap_attribution: Optional[Dict[str, Any]] = None
    # Presentation hierarchy (Scientific Hardening item 2). The perfect-
    # foresight optimum is a BENCHMARK, not an achievable target:
    #   theoretical_ceiling_gap   — alias of total_gap_usd under its honest
    #                               name: gap vs the Theoretical Economic
    #                               Ceiling (Upper Bound Benchmark).
    #   recoverable_execution_gap — gap_attribution.execution_gap: value
    #                               achievable using information available at
    #                               decision time. None when no forecast
    #                               column exists — never fabricated.
    #   headline_gap_basis        — which figure the UI should headline.
    theoretical_ceiling_gap: Optional[float] = None
    recoverable_execution_gap: Optional[float] = None
    headline_gap_basis: Optional[str] = "ceiling"  # "execution" | "ceiling"
    # C2 — chain of custody: input hash, provenance, and software versions.
    # Populated by the file-audit endpoint; None for raw JSON audits.
    audit_manifest: Optional[Dict[str, Any]] = None
    # W1–W4 — versioned quality metrics (asset-agnostic; N/A-aware).
    # data_quality_index: {value, grade, interpretation, components{...}}
    # audit_confidence:   {value|None, grade|INDETERMINATE, factors{...}}
    # forecast_reliability: report-only, Experimental; None when no forecast.
    # data_quality_manifest: raw integer evidence DQI is derived from.
    data_quality_index: Optional[Dict[str, Any]] = None
    audit_confidence: Optional[Dict[str, Any]] = None
    forecast_reliability: Optional[Dict[str, Any]] = None
    data_quality_manifest: Optional[Dict[str, Any]] = None
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
# Sprint 1: Account auth (COMMODITY per blueprint §0 — minimal robust
# JWT + bcrypt, org-scoped; no external IdP so on-prem/sovereign works).
# Existing trial-token funnel is untouched; account users are dual-accepted
# on every audit endpoint via a linked TrialLead row ("acct-<user_id>").
# ==========================================
import bcrypt as _bcrypt
import jwt as _pyjwt

_AUTH_SECRET = os.environ.get("PREDAIOT_AUTH_SECRET", "")
if not _AUTH_SECRET:
    # Dev fallback: deterministic per-machine secret. Production MUST set
    # PREDAIOT_AUTH_SECRET (startup log warns; tokens don't survive redeploys
    # of ephemeral filesystems otherwise).
    _AUTH_SECRET = _hashlib.sha256(f"predaiot-dev-{os.path.abspath(__file__)}".encode()).hexdigest()
    print("[startup] WARNING: PREDAIOT_AUTH_SECRET not set — using dev-only derived secret.")

_JWT_TTL_HOURS = int(os.environ.get("PREDAIOT_JWT_TTL_HOURS", "24"))
_ROLES = ("owner", "admin", "asset_manager", "operator", "finance", "viewer")


def _hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode("utf-8"), _bcrypt.gensalt()).decode("ascii")


def _verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return _bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("ascii"))
    except Exception:
        return False


def _issue_jwt(user: "User") -> str:
    now = datetime.utcnow()
    return _pyjwt.encode(
        {"sub": str(user.id), "org": user.org_id, "role": user.role,
         "email": user.email, "iat": now, "exp": now + timedelta(hours=_JWT_TTL_HOURS)},
        _AUTH_SECRET, algorithm="HS256")


def _decode_jwt(token: str) -> Optional[dict]:
    try:
        return _pyjwt.decode(token, _AUTH_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def require_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> "User":
    """JWT-only dependency for account endpoints (assets, org)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "auth_required",
                            "message": "Sign in to access this resource."})
    claims = _decode_jwt(authorization[7:])
    if not claims:
        raise HTTPException(status_code=401, detail={"code": "auth_invalid",
                            "message": "Session expired or invalid. Sign in again."})
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(claims["sub"])).first()
        if user is None:
            raise HTTPException(status_code=401, detail={"code": "auth_invalid",
                                "message": "Account not found."})
        db.expunge(user)
        return user
    finally:
        db.close()


def require_role(*roles: str):
    """RBAC dependency factory. Owner passes every check."""
    def _dep(user: "User" = Depends(require_user)) -> "User":
        if user.role != "owner" and user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": f"Requires role: {', '.join(roles)}."})
        return user
    return _dep


def _lead_for_user(user: "User") -> TrialLead:
    """
    Dual-accept bridge: get/create the TrialLead row linked to an account so
    every existing audit endpoint (keyed by lead.token) works unchanged.
    Account leads never expire (far-future expiry, refreshed on touch).
    """
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.user_id == user.id).first()
        if lead is None:
            lead = TrialLead(token=f"acct-{user.id}-{secrets.token_urlsafe(16)}",
                             email=user.email, asset_name=None,
                             expires_at=datetime.utcnow() + timedelta(days=3650),
                             user_id=user.id)
            db.add(lead)
            db.commit()
            db.refresh(lead)
        elif lead.expires_at < datetime.utcnow() + timedelta(days=365):
            lead.expires_at = datetime.utcnow() + timedelta(days=3650)
            db.commit()
            db.refresh(lead)
        db.expunge(lead)
        return lead
    finally:
        db.close()


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
        _security_log("audit.run", actor=user.email, org_id=user.org_id,
                      object_ref=f"audit:{rec.id}|sha:{input_sha256[:12]}")
    finally:
        db.close()


def require_trial_or_user(
    x_trial_token: Optional[str] = Header(default=None, alias="X-Trial-Token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> TrialLead:
    """
    Dual-accept gate for audit endpoints: a signed-in account (Bearer JWT)
    OR a legacy trial token. Account takes precedence when both present.
    """
    if authorization and authorization.startswith("Bearer "):
        claims = _decode_jwt(authorization[7:])
        if claims:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == int(claims["sub"])).first()
            finally:
                db.close()
            if user is not None:
                return _lead_for_user(user)
    return require_trial_token(x_trial_token)


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


def _client_ip(request) -> str:
    """
    Real client IP behind Render's reverse proxy. `request.client.host` returns
    the proxy's internal IP so every visitor would share one rate-limit key —
    exactly the incident that put the trial gate in the 429 hole earlier. Parse
    X-Forwarded-For instead (Render sets it; format is "client, proxy1, ...").
    """
    try:
        xff = request.headers.get("X-Forwarded-For", "") if hasattr(request, "headers") else ""
        if xff:
            return xff.split(",")[0].strip()
    except Exception:
        pass
    try:
        return request.client.host if request.client else "unknown"
    except Exception:
        return "unknown"


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
            client_ip = _client_ip(request)   # real IP behind Render's proxy
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
_INTERMITTENT_TYPES = {"solar", "pv", "wind", "tidal", "wave"}
_DISPATCHABLE_TYPES = {"gas", "oilgas", "coal", "thermal", "chp", "nuclear", "geothermal", "hydro"}
_LOAD_TYPES         = {"hydrogen", "electrolyzer", "desalination", "desal"}


def _dispatch_mode(asset_type: Optional[str]) -> str:
    t = (asset_type or "").strip().lower()
    if t in _INTERMITTENT_TYPES: return "intermittent"
    if t in _DISPATCHABLE_TYPES: return "dispatchable"
    if t in _LOAD_TYPES:         return "load"
    # Hybrid labels from real SCADA exports: "Solar+BESS", "Wind + Storage",
    # "PV/Battery". The storage component is the one making dispatch decisions,
    # so storage keywords win over generation keywords.
    if any(k in t for k in ("bess", "battery", "storage")):
        return "storage"
    if any(k in t for k in ("solar", "pv", "wind", "tidal", "wave")):
        return "intermittent"
    if any(k in t for k in ("gas", "coal", "thermal", "nuclear", "geothermal", "chp")):
        return "dispatchable"
    if any(k in t for k in ("hydrogen", "electrolyzer", "desal")):
        return "load"
    return "storage"  # default + explicit storage types


# Last MILP solve telemetry — read by ingestion to disclose time-limited
# (incumbent, not proven-optimal) solves on very large files.
_MILP_LAST = {"status": "Optimal", "steps": 0}


def _run_optimizer_storage(asset: AssetSpecs, prices: List[float], dt_hours: float = 1.0,
                           return_charge: bool = False):
    """
    BESS MILP. dt_hours is the step duration: SoC moves by P × dt / E_max per
    step, so a 5-minute SCADA feed (dt=1/12) no longer lets the model shift
    12× the physically possible energy per step. dt=1.0 reproduces the v1
    reference audit exactly.

    return_charge=True also returns the optimal charge schedule — needed by
    the EDV accounting (Reference Manual Vol II Ch 3: J subtracts the charge
    purchase cost) and by the Ch 8.2 gap-attribution second solve.
    """
    if not prices:
        return ({}, {}) if return_charge else {}
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
        step_delta = (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) * dt_hours / asset.e_max
        if t == 0:
            prob += soc[t] == asset.soc_init + step_delta
        else:
            prob += soc[t] == soc[t-1] + step_delta
        if t == max(hours):
            prob += soc[t] == asset.soc_init
    # Hard wall-clock cap: a multi-day 5-minute file means thousands of
    # binaries — CBC keeps the best incumbent when the limit hits, and the
    # status below lets ingestion disclose "optimum is a lower bound".
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=45))
    _MILP_LAST["status"] = pulp.LpStatus.get(prob.status, "Unknown")
    _MILP_LAST["steps"] = len(prices)
    dis = {t: (p_dis[t].varValue or 0.0) for t in hours}
    ch  = {t: (p_ch[t].varValue or 0.0) for t in hours}
    return (dis, ch) if return_charge else dis


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


def run_optimizer(asset: AssetSpecs, time_series_list: list, dt_hours: float = 1.0) -> dict:
    """
    Dispatch router. Picks the right optimizer for the asset class and returns
    `{step_index: optimal_dispatch_mw}`. Defaults to the storage MILP so legacy
    audits (BESS, asset_type unset / 'Generic') produce identical numbers.

    dt_hours only affects the storage MILP (SoC energy balance). The
    intermittent / dispatchable / load optimizers are per-step MW policies —
    step duration cancels out of their dispatch decision, and the money side
    is handled centrally in process_calculation's EDV × dt.
    """
    mode = _dispatch_mode(asset.asset_type)
    if mode == "intermittent":
        return _run_optimizer_intermittent(asset, time_series_list)
    if mode == "load":
        return _run_optimizer_load(asset, time_series_list)
    prices = [float(ts.get("price", 0)) for ts in time_series_list]
    if mode == "dispatchable":
        return _run_optimizer_dispatchable(asset, prices)
    return _run_optimizer_storage(asset, prices, dt_hours=dt_hours)


def run_optimizer_full(asset: AssetSpecs, time_series_list: list, dt_hours: float = 1.0) -> tuple:
    """
    Like run_optimizer but also returns the optimal CHARGE schedule (empty for
    non-storage modes, which have no charging concept). The EDV ledger needs
    both sides: per Reference Manual Vol II Ch 3 the storage objective is
    J = [P·P_dis − P·P_ch]·Δt − C_deg — charging cost is real money.
    """
    mode = _dispatch_mode(asset.asset_type)
    if mode == "storage":
        prices = [float(ts.get("price", 0)) for ts in time_series_list]
        dis, ch = _run_optimizer_storage(asset, prices, dt_hours=dt_hours, return_charge=True)
        return dis, ch
    return run_optimizer(asset, time_series_list, dt_hours=dt_hours), {}

# ==========================================
# 5. NEW: EDA Intelligence Engine
# ==========================================
def _classify_decision(opt: float, act: float, price: float, threshold: float = 5.0) -> tuple:
    """
    Deterministic step classification. The boundaries below are NORMATIVE
    TAXONOMY DEFINITIONS (published in the methodology), not measurements:
      tolerance 0.5 MW  — |opt − act| below this is "the same action"
      materiality 5 MW  — optimal dispatch below this is "no opportunity"

    Returns (decision_type, confidence). Confidence is ALWAYS None: the
    previous per-class constants (0.96/0.85/…) were fabricated and were
    removed under the No-Fabrication rule (docs/REMOVED_HEURISTICS.md).
    A defensible confidence must derive from data quality — future EDA
    Standard work, not an invented constant.
    """
    if abs(opt - act) < 0.5:
        return "Correct Dispatch", None
    if opt > threshold and act < 0.5:
        return "Missed Arbitrage", None
    if act > opt + threshold:
        return "Over-Dispatch", None
    if opt < threshold and act < 0.5:
        return "Correct Idle", None
    if opt > threshold and 0 < act < opt:
        return "Partial Capture", None
    return "Sub-optimal Dispatch", None

def _root_cause_bucket(decision_type: str) -> str:
    """Mutually exclusive mapping from step classification to gap category —
    every positive gap_step is attributed to EXACTLY ONE category, so the
    category losses partition Σ positive gap exactly (no double counting)."""
    dt = decision_type or ""
    if "Missed Arbitrage" in dt:
        return "Missed Arbitrage"
    if "Partial" in dt:
        return "Partial Capture"
    if "Over" in dt:
        return "Over-Dispatch"
    return "Schedule-based Dispatch"


def _build_root_causes(
    decision_log: List[DecisionRecord],
    total_gap: float,
    total_edv_opt: float,
) -> List[RootCauseItem]:
    """
    Attribute the ceiling gap to categories via an EXACT PARTITION:

        loss(cat)            = Σ gap_step over rows with gap_step > 0
                               whose classification maps to cat
        contribution_pct(cat)= loss(cat) / Σ_cat loss(cat) × 100

    The percentages therefore sum to 100.0 by construction, and every figure
    reproduces from ledger rows by filtering on decision_type. The former
    "Curtailment += gap × 0.15" secondary tag was removed — the 0.15 factor
    was fabricated and double-counted gap already attributed to another
    category (docs/REMOVED_HEURISTICS.md). Curtailed energy is reported
    separately as a descriptive quantity in EDAMetrics.curtailed_energy_mwh.
    """
    cats: dict = {}
    for rec in decision_log:
        gap = rec.gap_step or 0
        if gap <= 0:
            continue
        cats[_root_cause_bucket(rec.decision_type)] = \
            cats.get(_root_cause_bucket(rec.decision_type), 0.0) + gap

    total_positive = sum(cats.values())
    result = []
    for cat, loss in cats.items():
        if loss > 0 and total_positive > 0:
            result.append(RootCauseItem(
                category=cat,
                contribution_pct=round(loss / total_positive * 100.0, 1),
                loss_usd=round(loss, 2),
            ))
    result.sort(key=lambda x: x.contribution_pct, reverse=True)
    return result

# ── Economic Action Plan under the No-Fabrication rule ──────────────────────
# QUANTIFIED items derive every number from ledger rows:
#     period_gain(cat) = sum of gap_step over rows with gap_step > 0 whose
#                        classification maps to cat (_root_cause_bucket)
#     annual_gain      = period_gain x annual_factor (linear extrapolation,
#                        labeled as such everywhere it is shown)
#     share%           = period_gain / sum of positive gap_step x 100
# Each carries a `derivation` string stating the exact filter + formula, so
# any reader can reproduce it from the exported ledger CSV.
#
# ADVISORY items (market/strategy ideas that CANNOT be quantified from the
# audited dataset) carry NO numbers and are flagged
# "Experimental - Not part of EDA Standard v1.0".
#
# The former implementation allocated fixed shares of the gap
# (0.28/0.35/0.18/0.12/0.07 ...) with invented confidence/priority/payback
# figures - removed; see docs/REMOVED_HEURISTICS.md.

_EXPERIMENTAL_NOTE = ("Experimental - Not part of EDA Standard v1.0. "
                      "Not quantifiable from the audited dataset; no value figure is given.")

# Mode-aware recommendation wording per evidence bucket. Text is advice;
# numbers always come from the ledger.
_BUCKET_ACTIONS = {
    "storage": {
        "Missed Arbitrage":        ("Dynamic dispatch trigger",
                                    "Respond to high-price windows instead of holding charge - replace static "
                                    "thresholds with a price-responsive trigger."),
        "Partial Capture":         ("Raise dispatch to the available optimum",
                                    "During priced windows the asset dispatched below the feasible optimum - "
                                    "review threshold conservatism and power-limit settings."),
        "Schedule-based Dispatch": ("Replace fixed-schedule logic",
                                    "Dispatch followed a predefined schedule rather than market signals during "
                                    "these intervals."),
        "Over-Dispatch":           ("Stop dispatch below marginal economics",
                                    "Discharge occurred when the price did not cover marginal cost."),
    },
    "intermittent": {
        "Missed Arbitrage":        ("Export available generation during priced windows",
                                    "Available power was not exported while prices exceeded marginal cost."),
        "Partial Capture":         ("Reduce unnecessary curtailment",
                                    "Output was partially curtailed while export remained economic."),
        "Schedule-based Dispatch": ("Price-responsive curtailment logic",
                                    "Curtailment decisions did not track market signals in these intervals."),
        "Over-Dispatch":           ("Negative-price curtailment discipline",
                                    "Export continued into intervals where it destroyed value."),
    },
    "dispatchable": {
        "Missed Arbitrage":        ("Merit-order compliance",
                                    "The plant idled while price exceeded marginal generation cost."),
        "Partial Capture":         ("Dispatch to full economic capacity",
                                    "Output was below the economic optimum during priced windows."),
        "Schedule-based Dispatch": ("Replace fixed-schedule logic",
                                    "Dispatch followed a schedule rather than the merit-order rule."),
        "Over-Dispatch":           ("Stop uneconomic dispatch",
                                    "Generation ran while price was below marginal cost."),
    },
    "load": {
        "Missed Arbitrage":        ("Shift consumption into cheapest windows",
                                    "Consumption was scheduled outside the day's lowest-price windows."),
        "Partial Capture":         ("Deepen load-shifting into cheap windows",
                                    "Only part of the shiftable load moved to low-price intervals."),
        "Schedule-based Dispatch": ("Price-responsive consumption scheduling",
                                    "Consumption timing ignored market prices in these intervals."),
        "Over-Dispatch":           ("Avoid consumption in peak-price windows",
                                    "Load ran during the day's most expensive intervals."),
    },
}

# Advisory catalog: strategy directions worth investigating, explicitly not
# quantified by this audit.
_ADVISORY_IDEAS = {
    "storage": [
        ("Reserve / frequency-market stacking",
         "Idle capacity may qualify for FCR / spinning-reserve products in markets that offer them."),
        ("Curtailment-absorption charging",
         "Where colocated generation is curtailed, charging against curtailed energy may add value."),
    ],
    "intermittent": [
        ("Storage colocation for time-shift",
         "A colocated BESS could move midday oversupply into evening peaks."),
        ("Ancillary-services enrolment",
         "IBR-capable inverters may qualify for voltage-support or reactive-power products."),
    ],
    "dispatchable": [
        ("Spinning-reserve enrolment",
         "Synchronised idle capacity may qualify for operating-reserve products."),
        ("Fuel-cost hedging",
         "Forward fuel contracts could stabilise the marginal-cost input of the merit-order rule."),
    ],
    "load": [
        ("Demand-response enrolment",
         "The flexible load may qualify for interruptible-load or DR programmes."),
        ("Product-storage buffer sizing",
         "A larger downstream buffer would widen the feasible load-shifting window."),
    ],
}


def _build_opportunities(total_gap: float, asset_type: str, decision_log: list = None,
                         annual_factor: float = 365.0, currency: str = "USD") -> List[OpportunityItem]:
    """Evidence-derived action plan. See the block comment above for the
    derivation rules; every number reproduces from the exported ledger."""
    log = decision_log or []
    sums, counts = {}, {}
    for d in log:
        g = d.gap_step or 0
        if g <= 0:
            continue
        b = _root_cause_bucket(d.decision_type)
        sums[b] = sums.get(b, 0.0) + g
        counts[b] = counts.get(b, 0) + 1
    total_positive = sum(sums.values())

    mode = _dispatch_mode(asset_type)
    actions = _BUCKET_ACTIONS.get(mode, _BUCKET_ACTIONS["storage"])

    ops: List[OpportunityItem] = []
    for bucket, gain in sorted(sums.items(), key=lambda kv: kv[1], reverse=True):
        name, description = actions.get(bucket, (bucket, ""))
        ops.append(OpportunityItem(
            name=name,
            description=description,
            period_gain=round(gain, 2),
            annual_gain_usd=round(gain * annual_factor, 0),
            share_of_positive_gap_pct=round(gain / total_positive * 100.0, 1) if total_positive > 0 else None,
            intervals_observed=counts[bucket],
            evidence=(f"{counts[bucket]} ledger row(s) classified '{bucket}' with positive gap; "
                      f"sum of gap_step = {_fmt_money(gain, currency)} for the audited period."),
            derivation=(f"period_gain = sum of gap_step over ledger rows where decision_type maps to "
                        f"'{bucket}' and gap_step > 0; annual = period_gain x {annual_factor:.2f} "
                        "(linear extrapolation of the audited period)."),
        ))

    # Operator-override governance - derived from override-flagged rows only.
    ovr_gain = sum((d.gap_step or 0) for d in log if d.operator_override and (d.gap_step or 0) > 0)
    ovr_count = sum(1 for d in log if d.operator_override and (d.gap_step or 0) > 0)
    if ovr_count > 0:
        ops.append(OpportunityItem(
            name="Operator override governance",
            description="Manual interventions coincided with value loss - require an economic "
                        "justification record for each override.",
            period_gain=round(ovr_gain, 2),
            annual_gain_usd=round(ovr_gain * annual_factor, 0),
            share_of_positive_gap_pct=round(ovr_gain / total_positive * 100.0, 1) if total_positive > 0 else None,
            intervals_observed=ovr_count,
            evidence=(f"{ovr_count} override-flagged ledger row(s) with positive gap; "
                      f"sum of gap_step = {_fmt_money(ovr_gain, currency)}. NOTE: these rows are also "
                      "counted in their classification bucket above - this item is a cross-cut "
                      "view, not additional value."),
            derivation="period_gain = sum of gap_step over ledger rows where operator_override = True "
                       "and gap_step > 0 (cross-cut of the buckets above; do not sum with them).",
        ))

    # Advisory ideas - explicitly experimental, never quantified.
    for name, description in _ADVISORY_IDEAS.get(mode, []):
        ops.append(OpportunityItem(
            name=name,
            description=description,
            experimental=True,
            experimental_note=_EXPERIMENTAL_NOTE,
        ))
    return ops

def _build_heat_map(decision_log: List[DecisionRecord]) -> List[HeatMapCell]:
    """
    Severity banding derived from the audit's OWN gap distribution — the
    former bands (gap < price×1 / price×5) used fabricated multipliers
    (docs/REMOVED_HEURISTICS.md). Definition:
        optimal    : gap_step ≤ 0
        acceptable : 0 < gap_step ≤ P50 of this audit's positive gaps
        poor       : P50 < gap_step ≤ P90
        critical   : gap_step > P90
    Percentiles are computed from the ledger itself, so the legend is
    reproducible for any dataset.
    """
    positive = sorted((rec.gap_step or 0) for rec in decision_log if (rec.gap_step or 0) > 0)

    def _pct(p: float) -> float:
        if not positive:
            return 0.0
        k = max(0, min(len(positive) - 1, int(round(p * (len(positive) - 1)))))
        return positive[k]

    p50, p90 = _pct(0.50), _pct(0.90)

    cells = []
    for rec in decision_log:
        h = rec.hour or 0
        label = f"{h // 12:02d}:{(h % 12) * 5:02d}"
        gap = rec.gap_step or 0
        if gap <= 0:
            status = "optimal"
        elif gap <= p50:
            status = "acceptable"
        elif gap <= p90:
            status = "poor"
        else:
            status = "critical"
        cells.append(HeatMapCell(
            hour=h, label=label, status=status,
            gap_usd=round(gap, 2), price=rec.price or 0,
            action_taken=rec.decision_type or "Unknown"
        ))
    return cells

def _build_eda_metrics(
    decision_log: List[DecisionRecord],
    total_opt: float, total_act: float,
    asset_type: str,
    dt_hours: float = 1.0,
) -> EDAMetrics:
    """
    Only ledger-derivable ratios. The former EIS composite (weights
    45/30/15/10), decision_delay_index (×10 scale), revenue_stacking_index
    (2-if-fui>0.3) and battery_opportunity_capture (dispatch accuracy under a
    misleading name) were fabricated constructs and are withdrawn — the model
    keeps their keys as None for API compatibility (docs/REMOVED_HEURISTICS.md).
    """
    total = len(decision_log)
    correct = sum(1 for d in decision_log if "Correct" in (d.decision_type or ""))
    with_forecast = sum(1 for d in decision_log if d.forecast_price is not None)
    overrides = sum(1 for d in decision_log if d.operator_override)
    curtailed_mwh = sum((d.curtailment_mw or 0) for d in decision_log) * dt_hours

    # Same Ch. 4.2 rule as dq_score: no opportunity + nothing captured = full
    # efficiency (no leakage), not the literal 0/0 → 0 fallback.
    _EDV_EPS = 1e-9
    if total_opt > _EDV_EPS:
        ede = total_act / total_opt
    elif abs(total_act) <= _EDV_EPS:
        ede = 1.0
    else:
        ede = 0.0
    ede = max(0.0, min(1.0, ede))
    elr = 1 - ede
    dispatch_acc = (correct / total) if total > 0 else 0
    fui = (with_forecast / total) if total > 0 else 0

    return EDAMetrics(
        economic_decision_efficiency=round(ede * 100, 2),
        economic_leakage_ratio=round(elr * 100, 2),
        dispatch_accuracy=round(dispatch_acc * 100, 2),
        forecast_utilization_index=round(fui * 100, 2),
        override_rate_pct=round(overrides / total * 100, 2) if total > 0 else None,
        curtailed_energy_mwh=round(curtailed_mwh, 2),
    )

def _build_ai_commentary(
    asset_name: str, total_gap: float, total_opt: float,
    decision_log: List[DecisionRecord], dq: float,
    eda_metrics=None, opportunities: list = None, root_causes: list = None,
    annual_factor: float = 365.0, currency: str = "USD",
    gap_attribution: dict = None,
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
    # risk band per the published War-Room thresholds (Ref. Manual Vol III):
    # a documented banding of DQ, not an invented composite rating.
    risk_band    = _risk_level(dq)
    top_opp      = (opportunities[0].name if opportunities else None)
    top_cause    = (root_causes[0].category if root_causes else None)
    top_cause_pct = (root_causes[0].contribution_pct if root_causes else None)

    L = []
    L.append("EXECUTIVE ASSESSMENT")
    L.append(
        f"During the audit period, {asset_name} captured {capture_pct}% of its Theoretical "
        f"Economic Ceiling (perfect-foresight upper-bound benchmark). Decision-quality risk "
        f"band per the published DQ thresholds: {risk_band}."
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
    L.append(f"✔ Decision Quality (ECF)             {round(dq * 100, 1)} / 100")
    L.append(f"✔ Ceiling Gap (upper bound)          {_fmt_money(total_gap, currency)}")
    if gap_attribution:
        L.append(f"✔ Recoverable Execution Gap          {_fmt_money(gap_attribution['execution_gap'], currency)}")
    L.append(f"✔ Missed High-Value Intervals         {len(missed)}")
    if top_opp:
        L.append(f"✔ Largest Evidence-Backed Action      {top_opp}")
    L.append("")
    L.append("ROOT CAUSE ANALYSIS")
    if top_cause is not None:
        L.append(
            f"The largest gap category is '{top_cause}' — {top_cause_pct}% of the positive "
            "step-gap (exact partition of ledger rows by decision classification)."
        )
    else:
        L.append("No positive gap steps were recorded — no root-cause attribution applies.")
    if missed:
        L.append(
            f"The ledger records {len(missed)} high-price windows classified 'Missed Arbitrage'"
            + (f" — largest at {top_times}" if top_times else "")
            + " — where dispatch remained below the feasible optimum. Whether hardware, availability "
              "or contractual constraints contributed is OUTSIDE the scope of this data-only audit; "
              "the figures quantify the economic difference, not its operational cause."
        )
    L.append("")
    L.append("OPERATIONAL IMPACT")
    if gap_attribution:
        L.append(
            f"The Recoverable Execution Gap for the audited period is "
            f"{_fmt_money(gap_attribution['execution_gap'], currency)} — value that was achievable "
            f"using the day-ahead forecast available at decision time, with no additional hardware. "
            f"The remaining {_fmt_money(gap_attribution['forecast_gap'], currency)} of the ceiling gap "
            f"was reachable only with perfect price foresight and is NOT operator-attributable."
        )
    else:
        L.append(
            f"The gap of {_fmt_money(total_gap, currency)} is measured against the Theoretical "
            f"Economic Ceiling — a perfect-foresight upper-bound benchmark. It includes value that "
            f"no forecast-based operation could fully capture; the operationally recoverable portion "
            f"cannot be isolated for this dataset because no day-ahead forecast column was provided."
        )
    L.append("")
    L.append("AUDITOR CONCLUSION")
    L.append(
        f"Based solely on the audited dataset, the asset captured {round(dq * 100, 1)}% of its "
        f"perfect-foresight ceiling (risk band: {_risk_level(dq)} per the published DQ thresholds). "
        "This audit evaluates dispatch economics only; asset health, availability and contractual "
        "constraints are outside its evidence base."
    )
    L.append("")
    L.append("RECOMMENDED ACTIONS (evidence-derived)")
    quantified = [op for op in (opportunities or []) if not op.experimental and op.period_gain]
    advisory   = [op for op in (opportunities or []) if op.experimental]
    if quantified:
        for i, op in enumerate(quantified[:5], 1):
            L.append("")
            L.append(f"Recommendation {i} — {op.name}")
            L.append(f"  Period Value            {_fmt_money(op.period_gain, currency)}")
            L.append(f"  Annualised (linear est.) {_fmt_money(op.annual_gain_usd, currency, 0)}")
            L.append(f"  Ledger Intervals        {op.intervals_observed}")
            L.append(f"  Derivation              {op.derivation}")
    else:
        L.append("  No positive-gap intervals were recorded — no quantified actions apply.")
    if advisory:
        L.append("")
        L.append("ADVISORY DIRECTIONS — Experimental, not part of EDA Standard v1.0; not "
                 "quantifiable from the audited dataset:")
        for op in advisory:
            L.append(f"  • {op.name}: {op.description}")

    return "\n".join(L)

def _risk_level(dq: float) -> str:
    # War Room thresholds per Reference Manual Vol III Part 1, Screen 1:
    # green > 0.9, yellow > 0.7, red below.
    if dq >= 0.90:
        return "Low"
    elif dq >= 0.70:
        return "Moderate"
    return "Severe"

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
class RegisterRequest(BaseModel):
    email: str
    password: str
    organization: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AssetCreateRequest(BaseModel):
    name: str
    asset_type: str = "storage"
    capacity_mw: Optional[float] = None
    currency: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None


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
    lead: TrialLead = Depends(require_trial_or_user),
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
        "mw_out", "discharge_mw", "bess_discharge", "bess_discharge_mw",
        "battery_discharge", "battery_discharge_mw", "storage_discharge_mw",
        "pcs_discharge_mw", "solar_output",
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
        "charging_power", "bess_charge", "bess_charge_mw",
        "battery_charge", "battery_charge_mw", "storage_charge_mw",
        "charge_power", "p_ch",
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

    # Tier 1: exact alias match. Iterate the ALIAS LIST in order — each list is
    # curated most-specific-first, so with hybrid files that expose several
    # plausible columns (e.g. a Solar+BESS export with both `solar_output` and
    # `bess_discharge_mw`) the storage-specific name wins deterministically
    # instead of "whichever column happened to come first in the file". A
    # column can only be claimed once across internals.
    norm_to_orig: dict = {}
    for original, norm in normalised.items():
        norm_to_orig.setdefault(norm, original)  # first file occurrence wins ties
    claimed = set()
    for internal, aliases in all_aliases.items():
        for alias in aliases:
            original = norm_to_orig.get(alias)
            if original is not None and original not in claimed:
                resolved[internal] = original
                match_type[internal] = "exact"
                claimed.add(original)
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


# ==========================================
# DATA QUALITY & CLEANING LAYER
# "Trust of result is everything" — every silent auto-correction the pipeline
# makes gets a named flag the operator can read before quoting the audit.
# Severity: "warning" = affects result trust, "info" = cosmetic / advisory.
# ==========================================

def _dq(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}


def _fmt_money(x, cur: str = "USD", decimals: int = 2) -> str:
    """"$1,234.56" for USD, "1,234.56 OMR" for everything else."""
    cur = (cur or "USD").upper()
    try:
        val = float(x or 0)
    except (TypeError, ValueError):
        val = 0.0
    if cur == "USD":
        return f"${val:,.{decimals}f}"
    return f"{val:,.{decimals}f} {cur}"


def _json_safe(obj):
    """Recursively replace NaN/±inf with None — strict JSON has no NaN."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    return obj


def _order_and_dedupe_timestamps(df: pd.DataFrame) -> tuple:
    """
    Sort out-of-order rows, drop unparseable timestamps, drop duplicate
    timestamps (keep first). Only acts when "hour" is a real datetime.
    """
    flags = []
    if "hour" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["hour"]):
        return df, flags

    n_nat = int(df["hour"].isna().sum())
    if n_nat:
        df = df[df["hour"].notna()].copy()
        flags.append(_dq("warning", "timestamps_dropped",
                         f"{n_nat} row(s) had unreadable timestamps and were removed from the audit."))
    if len(df) and not df["hour"].is_monotonic_increasing:
        df = df.sort_values("hour").reset_index(drop=True)
        flags.append(_dq("info", "timestamps_sorted",
                         "Rows were not in chronological order — sorted by timestamp."))
    n_dup = int(df["hour"].duplicated().sum())
    if n_dup:
        df = df[~df["hour"].duplicated(keep="first")].reset_index(drop=True)
        flags.append(_dq("warning", "duplicate_timestamps",
                         f"{n_dup} duplicate timestamp row(s) removed (kept the first occurrence)."))
    return df, flags


def _coerce_numeric_columns(df: pd.DataFrame) -> tuple:
    """
    Numeric coercion with honest gap handling. Prices are load-bearing for
    every EDV figure, so missing prices are linearly interpolated from
    neighbours (with a flag) instead of silently becoming $0 — a fake $0
    price fabricates arbitrage that never existed. Power columns default
    missing → 0 MW and negatives are clipped (charge/discharge arrive in
    separate columns; a negative there is a sign-convention artefact).
    """
    flags = []
    for col in ("price", "actual_discharge", "actual_charge", "curtailment_mw"):
        if col not in df.columns:
            continue
        num = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce",
        )
        n_bad = int(num.isna().sum())
        if col == "price":
            if n_bad and n_bad < len(num):
                num = num.interpolate("linear", limit_direction="both")
                flags.append(_dq("warning", "price_gaps_interpolated",
                                 f"{n_bad} missing/non-numeric price value(s) were linearly "
                                 "interpolated from neighbouring steps."))
            df[col] = num.fillna(0.0)
        else:
            if n_bad and n_bad < len(num):
                flags.append(_dq("info", f"{col}_gaps_zeroed",
                                 f"{n_bad} missing {col} value(s) treated as 0 MW."))
            df[col] = num.fillna(0.0)
            n_neg = int((df[col] < 0).sum())
            if n_neg:
                df[col] = df[col].clip(lower=0.0)
                flags.append(_dq("info", f"{col}_negatives_clipped",
                                 f"{n_neg} negative {col} value(s) clipped to 0 MW "
                                 "(charge and discharge are separate columns)."))
    return df, flags


# Column names that carry a comms / link health status in SCADA exports
_COMMS_STATUS_ALIASES = {
    "communication_status", "comm_status", "comms_status", "comms",
    "link_status", "connection_status", "telemetry_status", "signal_status",
}
_COMMS_OK_VALUES = {"ok", "online", "good", "connected", "healthy", "up", "1", "true", "normal"}


def _build_sensor_quality_flags(df: pd.DataFrame, dt_hours: float,
                                p_max: float, e_max: float) -> list:
    """
    Read-only plausibility checks on the (renamed) frame. Nothing here mutates
    data — these flags exist so the operator knows which windows to distrust.
    """
    flags = []
    n_rows = len(df)

    # 1. Comms dropouts (TIMEOUT / LOST / OFFLINE windows → stale sensor values)
    comms_col = next(
        (c for c in df.columns if _normalise_col(str(c)) in _COMMS_STATUS_ALIASES), None)
    if comms_col is not None and n_rows:
        vals = df[comms_col].astype(str).str.strip().str.lower()
        bad = vals[~vals.isin(_COMMS_OK_VALUES) & (vals != "nan")]
        if len(bad):
            top = ", ".join(f"{v.upper()}×{c}" for v, c in bad.value_counts().head(3).items())
            flags.append(_dq("warning", "comms_dropouts",
                             f"{len(bad)} of {n_rows} steps report a degraded telemetry link "
                             f"({top}). Sensor values in those windows may be stale; they are "
                             "included in the audit but step-level attributions there should "
                             "be treated with caution."))

    # 2. SoC physics: a p_max MW converter on an e_max MWh pack can move at most
    #    p_max·dt/e_max of SoC per step. Bigger jumps = batch-updated SoC sensor.
    if "soc" in df.columns and e_max and e_max > 0:
        soc = pd.to_numeric(df["soc"], errors="coerce").dropna()
        if len(soc) >= 3:
            soc_pct = soc * 100.0 if float(soc.abs().max()) <= 1.5 else soc
            max_step_pct = (p_max * dt_hours / e_max) * 100.0
            viol = int((soc_pct.diff().abs() > max_step_pct * 1.5).sum())
            if viol:
                flags.append(_dq("warning", "soc_physics_violation",
                                 f"{viol} SoC step change(s) exceed what a {p_max:g} MW converter on a "
                                 f"{e_max:g} MWh pack can physically move in one step (max "
                                 f"{max_step_pct:.1f}%/step). The SCADA SoC register is likely "
                                 "batch-updated; the audit relies on the power columns, SoC is advisory."))

    # 3. Frozen price feed: identical price for ≥ 2 hours straight suggests a
    #    stuck market-data link, not a real market.
    if "price" in df.columns and n_rows:
        pr = pd.to_numeric(df["price"], errors="coerce")
        run_ids = (pr != pr.shift()).cumsum()
        longest = int(run_ids.value_counts().max()) if pr.notna().any() else 0
        freeze_threshold = max(3, int(round(2.0 / max(dt_hours, 1e-9))))
        if longest >= freeze_threshold:
            flags.append(_dq("warning", "price_feed_frozen",
                             f"The price column repeats the same value for {longest} consecutive "
                             "steps (≥ 2 hours) — the market feed may have been frozen in that window."))
        n_neg = int((pr < 0).sum())
        if n_neg:
            flags.append(_dq("info", "negative_prices",
                             f"{n_neg} step(s) have negative prices — legitimate in some markets; "
                             "the audit treats them as real."))

    return flags


def _collect_data_quality_counts(snap: pd.DataFrame, p_max: float, e_max: float,
                                 dt_hours: float, has_forecast_col: bool,
                                 col_map: dict) -> dict:
    """
    READ-ONLY, DETERMINISTIC extraction of the integer evidence the Data
    Quality Index is derived from. Operates on a snapshot of the renamed
    frame taken AFTER timestamp parsing but BEFORE the mutating pipeline
    (dedupe / coercion / resample), so the counts describe the dataset the
    customer actually supplied. Nothing here mutates `snap`.

    Asset-agnostic: SoC / telemetry / forecast counts are None when the
    corresponding column is absent — those DQI dimensions then become N/A.

    Returns the Data Quality Manifest (raw counts + metadata). Every DQI
    number is reproducible from these integers via eda_metrics.
    """
    n_rows = int(len(snap))
    mf = {
        "manifest_version": "1.0",
        "n_rows_raw": n_rows,
        # timestamps
        "has_timestamps": False, "n_expected_steps": None, "n_present_steps": None,
        "n_missing_steps": None, "n_unparseable_timestamps": 0,
        "n_duplicate_timestamps": 0, "n_out_of_order_timestamps": 0,
        "detected_interval_sec": None, "timezone_assumed": None, "span_hours": None,
        # price (required)
        "n_price_missing_interpolated": 0, "n_negative_price_steps": 0,
        # sensor (asset-specific → may be None)
        "n_soc_present": None, "n_soc_physics_violations": None,
        # telemetry (may be None)
        "n_telemetry_rows": None, "n_telemetry_degraded": None,
        # forecast (may be None)
        "n_forecast_present": None,
    }

    # ── Timestamps ──────────────────────────────────────────────────────────
    hour = snap["hour"] if "hour" in snap.columns else None
    if hour is not None and pd.api.types.is_datetime64_any_dtype(hour):
        mf["has_timestamps"] = True
        n_unparseable = int(hour.isna().sum())
        valid = hour.dropna()
        mf["n_unparseable_timestamps"] = n_unparseable
        mf["n_present_steps"] = int(len(valid))
        if len(valid) >= 2:
            deltas = valid.diff().dt.total_seconds().dropna()
            mf["n_out_of_order_timestamps"] = int((deltas < 0).sum())
            mf["n_duplicate_timestamps"] = int(valid.duplicated().sum())
            pos = deltas[deltas > 0]
            interval = float(pos.median()) if len(pos) else None
            mf["detected_interval_sec"] = round(interval, 3) if interval else None
            span = float((valid.max() - valid.min()).total_seconds())
            mf["span_hours"] = round(span / 3600.0, 4)
            if interval and interval > 0:
                mf["n_expected_steps"] = int(round(span / interval)) + 1
                mf["n_missing_steps"] = max(0, mf["n_expected_steps"] - mf["n_present_steps"])
        try:
            tz = valid.dt.tz
            mf["timezone_assumed"] = str(tz) if tz is not None else "naive/UTC"
        except Exception:
            mf["timezone_assumed"] = None

    # ── Price (required column) ─────────────────────────────────────────────
    if "price" in snap.columns:
        num = pd.to_numeric(snap["price"].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
                            errors="coerce")
        mf["n_price_missing_interpolated"] = int(num.isna().sum())
        mf["n_negative_price_steps"] = int((num < 0).sum())

    # ── Sensor validity (SoC physics — only when a SoC column was supplied) ──
    if "soc" in col_map and "soc" in snap.columns and e_max and e_max > 0:
        soc = pd.to_numeric(snap["soc"], errors="coerce").dropna()
        if len(soc) >= 3:
            soc_pct = soc * 100.0 if float(soc.abs().max()) <= 1.5 else soc
            max_step_pct = (p_max * dt_hours / e_max) * 100.0
            mf["n_soc_present"] = int(len(soc))
            mf["n_soc_physics_violations"] = int((soc_pct.diff().abs() > max_step_pct * 1.5).sum())

    # ── Telemetry health (only when a comms-status column was supplied) ──────
    comms_col = next((c for c in snap.columns
                      if _normalise_col(str(c)) in _COMMS_STATUS_ALIASES), None)
    if comms_col is not None and n_rows:
        vals = snap[comms_col].astype(str).str.strip().str.lower()
        mf["n_telemetry_rows"] = n_rows
        mf["n_telemetry_degraded"] = int((~vals.isin(_COMMS_OK_VALUES) & (vals != "nan")).sum())

    # ── Forecast availability (only when a forecast column was supplied) ─────
    if has_forecast_col and "forecast_price" in snap.columns:
        mf["n_forecast_present"] = int(pd.to_numeric(snap["forecast_price"], errors="coerce").notna().sum())

    return mf


def _dqi_components_from_manifest(mf: dict) -> dict:
    """Deterministically map manifest counts → the six DQI components (N/A-aware)."""
    n = mf.get("n_rows_raw")
    has_ts = mf.get("has_timestamps")
    return {
        "completeness": eda_metrics.completeness(
            mf.get("n_present_steps"), mf.get("n_expected_steps")),
        "timestamp_integrity": eda_metrics.timestamp_integrity(
            (n if has_ts else None), mf.get("n_unparseable_timestamps", 0),
            mf.get("n_duplicate_timestamps", 0)),
        "sensor_validity": eda_metrics.sensor_validity(
            mf.get("n_soc_present"), mf.get("n_soc_physics_violations") or 0),
        "telemetry_health": eda_metrics.telemetry_health(
            mf.get("n_telemetry_rows"), mf.get("n_telemetry_degraded") or 0),
        "price_integrity": eda_metrics.price_integrity(
            n, mf.get("n_price_missing_interpolated", 0)),
        "forecast_availability": eda_metrics.forecast_availability(
            (n if mf.get("n_forecast_present") is not None else None),
            mf.get("n_forecast_present")),
    }


def _forecast_reliability_from_snapshot(snap: pd.DataFrame, has_forecast_col: bool) -> Optional[dict]:
    """MAPE of a supplied forecast vs realized price → Forecast Reliability (report-only)."""
    if not has_forecast_col or "forecast_price" not in snap.columns or "price" not in snap.columns:
        return None
    f = pd.to_numeric(snap["forecast_price"], errors="coerce")
    p = pd.to_numeric(snap["price"].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce")
    mask = f.notna() & p.notna()
    if int(mask.sum()) < 2:
        return None
    denom = p[mask].abs().clip(lower=1e-9)
    mape = float(((f[mask] - p[mask]).abs() / denom).mean())
    return eda_metrics.forecast_reliability(mape)


# Currency detection from column-name hints ("solar_revenue_omr" → OMR).
# Display-only: figures are reported in the file's own currency, we just stop
# implying dollars when the data plainly isn't in dollars.
_CURRENCY_HINTS = [
    ("omr", "OMR"), ("aed", "AED"), ("sar", "SAR"), ("kwd", "KWD"),
    ("qar", "QAR"), ("bhd", "BHD"), ("eur", "EUR"), ("gbp", "GBP"),
    ("usd", "USD"),
]


def _detect_currency(raw_columns: list) -> Optional[str]:
    joined = " " + " ".join(_normalise_col(str(c)) for c in raw_columns) + " "
    for hint, code in _CURRENCY_HINTS:
        if f"_{hint}" in joined or f"{hint}_" in joined or f" {hint} " in joined:
            return code
    return None


# Upload ceiling: a year of 1-minute data for one asset is ~40 MB of CSV;
# anything past this is either the wrong export or a memory-exhaustion attempt.
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _looks_numeric(v: str) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _fix_banner_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    Real Excel/CSV exports often carry a title banner above the real header
    ("PREDAIOT — Site Export | July 2024" merged across the sheet). pandas
    then reads the banner as the header and every column becomes "Unnamed: N".
    Detect that shape, find the first row that actually looks like a header
    (mostly non-numeric strings across most columns), and re-head the frame.

    Adds a "banner_header_skipped" flag via df.attrs["ingest_flags"] so the
    correction is visible to the operator.
    """
    n_cols = len(df.columns)
    if n_cols == 0 or len(df) == 0:
        return df
    unnamed = sum(1 for c in df.columns
                  if str(c).startswith("Unnamed:") or not str(c).strip())
    if unnamed < max(2, n_cols // 2):
        return df

    for i in range(min(10, len(df))):
        row = df.iloc[i]
        vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if len(vals) < max(2, int(n_cols * 0.6)):
            continue  # banner / blank spacer row
        numericish = sum(1 for v in vals if _looks_numeric(v))
        if numericish > len(vals) * 0.3:
            continue  # data row, not a header
        # Group-band rows ("IDENTIFICATION IDENTIFICATION MARKET MARKET …")
        # repeat a handful of labels; a real header row is nearly all unique.
        if len(set(vals)) < len(vals) * 0.8:
            continue
        new_cols = [str(v).strip() if pd.notna(v) and str(v).strip() else f"col_{j}"
                    for j, v in enumerate(row)]
        out = df.iloc[i + 1:].reset_index(drop=True)
        out.columns = new_cols
        # Restore numeric dtypes the banner header forced to object.
        # Positional access — survives any residual duplicate names.
        for j in range(out.shape[1]):
            num = pd.to_numeric(out.iloc[:, j], errors="coerce")
            if num.notna().mean() >= 0.9:
                out.isetitem(j, num)
        out.attrs["ingest_flags"] = [_dq(
            "info", "banner_header_skipped",
            f"The file starts with {i + 1} title/banner row(s) above the real column "
            "header — skipped automatically.")]
        return out
    return df


def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    """Universal parser + banner-header recovery. See _parse_file_bytes_raw."""
    df = _parse_file_bytes_raw(contents, filename)
    return _fix_banner_header(df)


def _parse_file_bytes_raw(contents: bytes, filename: str) -> pd.DataFrame:
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

    # ── Encoding resolution, scored by USEFULNESS ──────────────────────────────
    # "Decoded without an exception" is NOT the same as "decoded correctly":
    # cp1256 Arabic bytes decode 'successfully' as Shift-JIS mojibake and the
    # column names become garbage. So every candidate parse is scored by how
    # many internal fields its columns actually resolve to, and the best
    # candidate wins. A score >= 2 (price + an output/consumption column)
    # short-circuits — that parse is definitely the right alphabet.
    def _alias_score(df_cand) -> int:
        try:
            return len(_resolve_columns_verbose([str(c) for c in df_cand.columns])["resolved"])
        except Exception:
            return 0

    ordered = []
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        ordered.append("utf-16")
    if contents[:3] == b"\xef\xbb\xbf":
        ordered.append("utf-8-sig")
    try:
        from charset_normalizer import from_bytes
        guess = from_bytes(contents[:20000]).best()
        if guess and guess.encoding:
            ordered.append(str(guess.encoding))
    except ImportError:
        pass
    try:
        import chardet
        g = chardet.detect(contents[:20000]).get("encoding")
        if g:
            ordered.append(g)
    except ImportError:
        pass
    ordered += [
        # Unicode
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32",
        # Arabic (كل ملفات Excel المحلية تستخدم هذا) — before Western so Gulf
        # exports don't get eaten by latin-1 (which never raises)
        "cp1256", "iso-8859-6",
        # Western European
        "latin-1", "cp1252", "iso-8859-15",
        # Central / Eastern European
        "cp1250", "iso-8859-2",
        # Cyrillic
        "cp1251", "iso-8859-5", "koi8-r",
        # CJK
        "gbk", "gb2312", "gb18030", "big5", "shift_jis", "euc-jp", "euc-kr",
        # Misc
        "ascii", "cp437",
    ]

    best_df, best_score, tried = None, -1, set()
    for enc in ordered:
        key = enc.lower()
        if key in tried:
            continue
        tried.add(key)
        try:
            df_cand = pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception:
            continue
        if len(df_cand.columns) == 0:
            continue
        score = _alias_score(df_cand)
        if score > best_score:
            best_df, best_score = df_cand, score
        if score >= 2:
            return df_cand
    if best_df is not None:
        return best_df

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
    lead: TrialLead = Depends(require_trial_or_user),
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
_CERT_KEY_ENV = "PREDAIOT_CERT_SIGNING_KEY"
_VERIFY_BASE_URL = os.getenv("PREDAIOT_VERIFY_BASE_URL",
                             "https://platform.preda-iot.com/api/v1/certificate/verify")


def _cert_signing_key():
    """Returns (private_key, public_key_b64) or (None, None) when unconfigured."""
    # Tolerate the classic env-paste corruptions: surrounding quotes, stray
    # whitespace/newlines, and lost base64 "=" padding. Never tolerate a bad
    # seed silently — decode failures still yield honest UNSIGNED certs.
    seed_b64 = os.getenv(_CERT_KEY_ENV, "").strip().strip('"').strip("'")
    seed_b64 = "".join(seed_b64.split())
    if not seed_b64:
        return None, None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        seed = _base64.b64decode(seed_b64 + "=" * (-len(seed_b64) % 4))
        if len(seed) < 32:
            raise ValueError(f"decoded seed is {len(seed)} bytes; need 32")
        key = Ed25519PrivateKey.from_private_bytes(seed[:32])
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return key, _base64.b64encode(pub).decode()
    except Exception as e:
        print(f"[cert] signing key invalid — issuing unsigned certificates: {e}")
        return None, None


def _canonical_json(payload: dict) -> bytes:
    """Deterministic byte serialisation: sorted keys, compact separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def _register_certificate(cert: dict, manifest: Optional[dict],
                          dqi_grade: Optional[str] = None,
                          confidence_grade: Optional[str] = None) -> dict:
    """
    Deterministic identity + signature + registry persistence.

    cert_id = first 16 hex of SHA-256 over the canonical CONTENT payload
    (metrics, scope, versions, quality grades — no timestamps), so
    re-requesting the certificate for the same audit returns the same
    certificate instead of minting a new ID each call. The registry stores
    only hashes, signature, versions, scope and quality GRADES — no customer
    identity or economics.
    """
    content = {k: cert.get(k) for k in (
        "asset_type", "audit_period", "economic_potential", "captured_value",
        "theoretical_ceiling_gap", "recoverable_execution_gap", "dq_score",
        "currency", "risk_level", "methodology", "standard", "version")}
    content["input_sha256"] = (manifest or {}).get("input_sha256")
    content["methodology_version"] = METHODOLOGY_VERSION
    content["engine_version"] = ENGINE_VERSION
    content["data_quality_grade"] = dqi_grade
    content["confidence_grade"] = confidence_grade
    payload_hash = _hashlib.sha256(_canonical_json(content)).hexdigest()
    cert_id = f"EDPC-{payload_hash[:16].upper()}"

    db = SessionLocal()
    try:
        rec = db.query(CertificateRecord).filter_by(payload_sha256=payload_hash).first()
        if rec is None:
            key, pub_b64 = _cert_signing_key()
            sig_b64 = None
            if key is not None:
                sig_b64 = _base64.b64encode(key.sign(payload_hash.encode())).decode()
            rec = CertificateRecord(
                cert_id=cert_id, payload_sha256=payload_hash,
                signature_b64=sig_b64, public_key_b64=pub_b64,
                asset_type=cert.get("asset_type"), audit_period=cert.get("audit_period"),
                methodology_ver=METHODOLOGY_VERSION, engine_ver=ENGINE_VERSION,
                solver_ver=f"{SOLVER_NAME} {SOLVER_VERSION}",
                input_sha256=(manifest or {}).get("input_sha256"),
                dqi_grade=dqi_grade, confidence_grade=confidence_grade,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            _security_log("certificate.issue", object_ref=f"cert:{rec.cert_id}",
                          actor=None)
        cert.update({
            "certificate_id":    rec.cert_id,
            "payload_sha256":    rec.payload_sha256,
            "signature_ed25519": rec.signature_b64,
            "public_key_ed25519": rec.public_key_b64,
            "signature_status":  ("SIGNED" if rec.signature_b64 else
                                  "UNSIGNED — no signing key configured on this deployment"),
            "verification_url":  f"{_VERIFY_BASE_URL}/{rec.cert_id}",
            "issued_at":         rec.issued_at.isoformat() + "Z",
            "certificate_status": ("REVOKED" if rec.revoked else "VALID"),
            "dataset_sha256":    rec.input_sha256,
            "solver_version":    rec.solver_ver,
            "methodology_version": rec.methodology_ver,
            "engine_version":    rec.engine_ver,
        })
    finally:
        db.close()
    return cert


# ── Economic Rating: WITHDRAWN ────────────────────────────────────────────────
# The former AAA–CCC composite (weights 40/30/20/10, hard-coded governance
# fallback 8.0, thresholds every 10 points) was an unvalidated construct and
# has been withdrawn under the No-Fabrication rule. Per the hardening
# directive it is NOT re-derived from DQ alone: an Economic Rating represents
# a broader construct than DQ measures, and no defensible methodology exists
# until the EDA Standard defines and validates one.
# See docs/REMOVED_HEURISTICS.md.
_RATING_WITHDRAWN_LABEL = "Withdrawn — pending EDA Standard v1.0 definition"


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

    # Same Ch 4.2 domain rules as the offline DQ. The former formula allowed
    # 150% and, in the no-opportunity branch, subtracted MONEY from a PERCENT
    # (100 − |gap|) — scientifically incorrect; corrected here.
    if optimal_value > 0.01:
        decision_quality = max(0.0, min(100.0, (captured_value / optimal_value) * 100))
    elif abs(captured_value) < 0.01:
        decision_quality = 100.0
    else:
        decision_quality = 0.0

    dec_type, conf = _classify_decision(
        optimal_discharge if optimal_discharge > 0 else optimal_charge,
        actual_dis if optimal_discharge > 0 else actual_chg,
        price,
    )

    # Derived, dimensionless step severity: the gap as a share of this step's
    # own optimal value. The former HIGH/MEDIUM/LOW bands used fabricated
    # absolute money thresholds ($100/$20) — currency-blind and arbitrary
    # (docs/REMOVED_HEURISTICS.md).
    gap_pct_of_optimal = round(economic_gap / optimal_value * 100, 1) if optimal_value > 0.01 else 0.0
    rec_power = optimal_discharge if action == "DISCHARGE" else optimal_charge

    recommendation_text = (
        f"{action} {rec_power:.0f} MW — {action_detail}. "
        f"Expected gain {economic_gap:.0f} per hour (market-price units)."
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
        # confidence WITHDRAWN (fabricated per-class constants); key kept None
        "confidence":         None,
        # severity replaced by a derived ratio; "alert" = the documented
        # display policy "gap exceeds half of this step's optimal value"
        "gap_pct_of_optimal": gap_pct_of_optimal,
        "severity":           None,
        "alert":              bool(optimal_value > 0.01 and economic_gap > 0.5 * optimal_value),
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
def _build_certificate(data: dict) -> dict:
    # Sanity gate: DQ is a ratio in [0,1] by definition (Ch. 4.2). A value
    # outside that range means the result came from a broken/stale engine —
    # never let it inflate a AAA rating on a signed certificate.
    dq         = max(0.0, min(1.0, float(data.get("dq_score", 0) or 0)))
    total_gap  = data.get("total_gap_usd", 0)
    opt        = data.get("edv_optimal_total", 0)
    act        = data.get("edv_actual_total", 0)
    m          = data.get("eda_metrics") or {}
    # Economic Rating WITHDRAWN (No-Fabrication rule + hardening constraint 4):
    # the AAA–CCC composite used unvalidated weights and is not re-derived
    # from DQ alone. Keys retained for API compatibility.
    rating, rating_label, rating_color = None, _RATING_WITHDRAWN_LABEL, "#8B93A7"
    efficiency = dq * 100  # alias of DQ (derived), kept for API compatibility
    # Span-correct annualisation: the audit result already computed
    # projection_12m from the actual period covered (8760 / span_hours).
    # Fall back to the legacy ×365 for results cached before that field.
    fl = data.get("financial_leakage") or {}
    annual_leakage = fl.get("projection_12m")
    if annual_leakage is None:
        annual_leakage = total_gap * 365
    cur = (data.get("currency") or "USD").upper()
    # Ch 8.2 attribution when the audited file carried a forecast column —
    # lets the certificate distinguish recoverable vs forecast-unreachable gap.
    _ga = data.get("gap_attribution") or None
    # W1–W4 quality metrics carried from the audit result (may be None for a
    # direct-JSON audit that never ran through the file ingestion pipeline).
    _dqi = data.get("data_quality_index") or None
    _ac  = data.get("audit_confidence") or None
    # cert identity + signature assigned by _register_certificate (C3):
    # deterministic content-hash ID, Ed25519 signature, registry persistence.

    # Factual narrative — states only what the ledger evidences. Grading
    # adjectives ("Outstanding"/"Critical") followed the withdrawn rating and
    # were removed with it.
    narrative = (
        f"The asset captured {round(dq * 100, 1)}% of its Theoretical Economic Ceiling "
        f"(perfect-foresight upper-bound benchmark) over the audited period; ceiling gap "
        f"{_fmt_money(total_gap, cur)}. "
        + (
            f"Recoverable Execution Gap (achievable with information available at decision "
            f"time): {_fmt_money(_ga['execution_gap'], cur)}. "
            if _ga else
            "The recoverable portion could not be isolated (no day-ahead forecast column in "
            "the source data). "
        )
        + f"Decision-quality risk band per the published DQ thresholds: "
        + str(data.get("risk_level", "Moderate")) + ". "
        "An AAA–CCC Economic Rating is not issued: the rating methodology is withdrawn "
        "pending formal definition and validation in EDA Standard v1.0."
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

    cert = {
        "issuer":               issuer,
        "recipient":            recipient,
        "audit_scope":          audit_scope,
        "asset_name":           data.get("asset_name", "Energy Asset"),
        "asset_type":           data.get("asset_type", "Generic"),
        "audit_period":         data.get("audit_period_label", "24h"),
        "economic_potential":   round(opt, 2),
        # Benchmark semantics (Scientific Hardening item 2): the potential is
        # the perfect-foresight upper bound, not an achievable target.
        "benchmark_label":      "Theoretical Economic Ceiling (Upper Bound Benchmark)",
        "captured_value":       round(act, 2),
        "destroyed_value":      round(total_gap, 2),   # legacy key = ceiling gap
        "theoretical_ceiling_gap": round(total_gap, 2),
        "recoverable_execution_gap": (round(_ga["execution_gap"], 2) if _ga else None),
        "forecast_unreachable_gap":  (round(_ga["forecast_gap"], 2) if _ga else None),
        "gap_basis":            ("execution" if _ga else "ceiling"),
        "dq_score":             round(dq * 100, 1),
        # WITHDRAWN composites — keys kept as None for API compatibility
        "eis_score":            None,
        "composite_score":      None,
        "rating":               rating,
        "rating_label":         rating_label,
        "rating_color":         rating_color,
        "rating_narrative":     narrative,
        "economic_efficiency":  round(efficiency, 1),
        "annual_leakage":       round(annual_leakage, 2),
        "currency":             cur,
        "risk_level":           data.get("risk_level", "Moderate"),
        "key_finding": (
            f"During the audit period, {data.get('asset_name','the asset')} captured "
            f"{round(dq*100,1)}% of its Theoretical Economic Ceiling (perfect-foresight "
            f"upper-bound benchmark). "
            + (
                f"Recoverable Execution Gap — achievable with information available at "
                f"decision time: {_fmt_money(_ga['execution_gap'], cur)} for the period."
                if _ga else
                f"Ceiling gap for the period: {_fmt_money(total_gap, cur)} (upper bound; "
                "includes forecast-unreachable value)."
            )
        ),
        # rating_components (fabricated 40/30/20/10 weights) removed with the
        # rating — see docs/REMOVED_HEURISTICS.md.
        "rating_components":    None,
        "certified_by":         "PREDAIOT Economic Decision Audit Engine",
        "methodology":          "MILP counterfactual optimization (hindsight ETL benchmark, Ch 8.2 attribution)",
        "standard":             "PREDAIOT EDA Methodology (pre-standard; EDA Standard v1.0 in preparation)",
        "version":              ENGINE_VERSION,
        # ── W1: Data Quality Grade + Confidence Grade (spec §12) ──────────
        # Overall DQI + every component (N/A shown, excluded from the mean),
        # numeric + grade + interpretation. Audit Confidence separate.
        "data_quality_index":   (None if not _dqi else {
            "value_pct":      _dqi.get("value_pct"),
            "grade":          _dqi.get("grade"),
            "interpretation": _dqi.get("interpretation"),
            "version":        _dqi.get("version"),
            "components":     _dqi.get("components"),
            "components_na":  _dqi.get("components_na"),
        }),
        "data_quality_grade":   (_dqi.get("grade") if _dqi else "N/A"),
        "audit_confidence":     (None if not _ac else {
            "value_pct":      _ac.get("value_pct"),
            "grade":          _ac.get("grade"),
            "interpretation": _ac.get("interpretation"),
            "version":        _ac.get("version"),
        }),
        "confidence_grade":     (_ac.get("grade") if _ac else "N/A"),
    }
    # C3: deterministic ID, Ed25519 signature, registry row, verification URL
    return _register_certificate(cert, data.get("audit_manifest"),
                                 dqi_grade=(_dqi.get("grade") if _dqi else None),
                                 confidence_grade=(_ac.get("grade") if _ac else None))


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
    # DQ is clamped to [0,1] by the engine; clamp here too so a stale cached
    # result can never print "12020.5 / 100" on a customer certificate again.
    dq_pct  = max(0.0, min(1.0, float(audit.get("dq_score", 0) or 0))) * 100.0
    risk    = (audit.get("risk_level") or "Moderate")
    cur     = (audit.get("currency") or "USD").upper()

    y = 540
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "EXECUTIVE SUMMARY")
    c.setStrokeColorRGB(0.04, 0.14, 0.22)
    c.setLineWidth(0.6)
    c.line(60, y - 4, 535, y - 4)

    # Benchmark hierarchy (Scientific Hardening item 2): the optimum is a
    # perfect-foresight UPPER BOUND; only the execution gap (when a forecast
    # column allowed the Ch 8.2 split) may be presented as recoverable.
    ga = audit.get("gap_attribution") or None
    rows = [
        ("Theoretical Ceiling (Upper Bound)", _fmt_money(edv_opt, cur)),
        ("Captured Value",                    _fmt_money(edv_act, cur)),
        ("Ceiling Gap (vs Upper Bound)",      _fmt_money(gap, cur)),
    ]
    if ga:
        rows += [
            ("Recoverable Execution Gap",     _fmt_money(ga.get("execution_gap"), cur)),
            ("Forecast-Unreachable Gap",      _fmt_money(ga.get("forecast_gap"), cur)),
        ]
    rows += [
        ("Decision Quality (DQ)",             f"{dq_pct:.1f} / 100"),
        ("Risk Level",                        risk.upper()),
    ]
    y -= 22
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 11)
    for label, value in rows:
        emphasize = label == "Recoverable Execution Gap"
        c.setFont("Helvetica-Bold" if emphasize else "Helvetica", 11)
        c.drawString(72, y, label)
        c.drawRightString(535, y, value)
        y -= 16
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.45, 0.45, 0.5)
    c.drawString(72, y, (
        "Ceiling = perfect-foresight benchmark. Recoverable Execution Gap = achievable with "
        "information available at decision time." if ga else
        "Ceiling = perfect-foresight benchmark (upper bound). Recoverable portion requires a "
        "day-ahead forecast column in the source data."))
    y -= 14
    c.setFillColorRGB(0.18, 0.18, 0.2)

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
            c.drawRightString(535, y, f"{float(pct or 0):.1f}%   ({_fmt_money(usd, cur, 0)})")
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

    # Quantified, ledger-derived items only — advisory/experimental ideas
    # carry no figures and do not appear on the certified one-pager.
    def _opf(op, key):
        return op.get(key) if isinstance(op, dict) else getattr(op, key, None)
    opps = [op for op in (audit.get("opportunities") or [])
            if not _opf(op, "experimental") and _opf(op, "period_gain")]
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 10)
    for i, op in enumerate(opps[:3], 1):
        c.drawString(72, y, f"{i}. {_opf(op, 'name')}")
        c.setFillColorRGB(0.55, 0.55, 0.6)
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(80, y - 11,
                     f"{_opf(op, 'intervals_observed')} ledger intervals · "
                     f"{_fmt_money(_opf(op, 'period_gain'), cur)} audited period · "
                     "annualised = linear extrapolation")
        c.setFillColorRGB(0.18, 0.18, 0.2)
        c.setFont("Helvetica", 10)
        c.drawRightString(535, y, _fmt_money(_opf(op, "annual_gain_usd"), cur, 0))
        y -= 26

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
    _q = cert.get("data_quality_index")
    _dq_line = (f"{_q['value_pct']}% / Grade {_q['grade']} / {_q['interpretation']}"
                if _q else "N/A (direct JSON audit)")
    _a = cert.get("audit_confidence")
    if _a and _a.get("value_pct") is not None:
        _ac_line = f"{_a['value_pct']}% / Grade {_a['grade']}"
    elif _a:
        _ac_line = str(_a.get("grade"))
    else:
        _ac_line = "N/A"
    cert_lines = [
        f"Certificate ID:  {cert.get('certificate_id', '—')}    Status: {cert.get('certificate_status', '—')}    Signature: {('Ed25519' if cert.get('signature_ed25519') else 'UNSIGNED')}",
        f"Issued:          {cert.get('issued_at', '—')}",
        f"Economic Rating: {cert.get('rating_label', '—')}",
        f"DQ / ECF:        {cert.get('dq_score', '—')} / 100    Risk band: {str(cert.get('risk_level', '—')).upper()}",
        f"Data Quality:    {_dq_line}   [{eda_metrics.DQI_VERSION}]",
        f"Audit Confidence:{_ac_line}   [{eda_metrics.AC_VERSION}]",
        f"Dataset SHA-256: {cert.get('dataset_sha256') or 'n/a (direct JSON audit)'}",
        f"Versions:        engine {cert.get('engine_version', '—')} · {cert.get('methodology_version', '—')} · {cert.get('solver_version', '—')}",
        f"Verify:          {cert.get('verification_url', '—')}",
    ]
    for line in cert_lines:
        c.drawString(72, y, line)
        y -= 12

    # QR to the public verification portal (C3)
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        qr = QrCodeWidget(cert.get("verification_url", ""))
        b = qr.getBounds()
        size = 62.0
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0,
                                           size / (b[3] - b[1]), 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, 470, y - 2)
    except Exception:
        pass  # QR is an enhancement; the URL line above remains authoritative

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
    try:
        with engine.connect() as conn:
            try:
                info["alembic_version"] = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version").scalar()
            except Exception:
                info["alembic_version"] = None
            for t in ("users", "organizations", "assets", "certificate_registry", "audit_records"):
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