import os
import uuid
import json
import asyncio
import pandas as pd
from io import StringIO
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from typing import Optional, Dict, Any
import hashlib as _hashlib
import base64 as _base64
import eda_metrics  # versioned, asset-agnostic DQI / Audit Confidence (pure module)
from datetime import datetime

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
from app.core.config import engine, SessionLocal  # noqa: E402
# ORM models + Base now live in app/models/tables.py (refactor step 2B).
from app.models import (  # noqa: E402
    Base, TrialLead, User, AuditRecord,
    EconomicState, Decision, CertificateRecord,
)

# Pure literal constants now live in app/core/constants.py (refactor step 2A).
from app.core.constants import (  # noqa: E402
    _MAX_UPLOAD_BYTES, _RATING_WITHDRAWN_LABEL,
)



# _security_log → app/core/logging.py (refactor step 3; shared by certificate_service)





# NOTE: Base.metadata.create_all() is intentionally NOT called here at import time.
# It is registered as a FastAPI startup event below (after `app` is created), so that
# uvicorn binds the port FIRST and Render's port scan succeeds, regardless of how long
# the DB connection takes. See the @app.on_event("startup") handler near the FastAPI setup.

# ==========================================
# 2. Data Models  (UNCHANGED CORE + NEW FIELDS)
# ==========================================
# Pydantic schemas now live in app/schemas/ (refactor step 3, schemas-first).
from app.schemas import (  # noqa: E402
    AssetSpecs, AuditRequest, AuditResponse,
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

# Trial-lead helpers (_EMAIL_SHAPE, _push_lead_to_airtable, _create_trial_lead,
# _bump_audit_count, TRIAL_DURATION_DAYS) -> app/services/trial_service.py (step 6).
from app.services.trial_service import _bump_audit_count  # noqa: E402
# Auth DI dependencies now live in app/core/dependencies.py (refactor step 2B).
from app.core.dependencies import (  # noqa: E402
    require_audit_runner, require_trial_or_user,
)




# ==========================================
# Sprint 1: Account auth (COMMODITY per blueprint §0 — minimal robust
# JWT + bcrypt, org-scoped; no external IdP so on-prem/sovereign works).
# Existing trial-token funnel is untouched; account users are dual-accepted
# on every audit endpoint via a linked TrialLead row ("acct-<user_id>").
# ==========================================
# Auth primitives (JWT + bcrypt) now live in app/core/security.py (refactor 2A).








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
# Access-log middleware + _client_ip helper now live in app/core/logging.py (2B).
from app.core.logging import _client_ip, _api_access_log, _security_log  # noqa: E402,F401
# Rate limiter + in-process runtime state now live in app/core (refactor step 6
# prep) so routers share them without importing main (no import cycle).
from app.core.ratelimit import limiter, register_rate_limiter  # noqa: E402
from app.core.state import (  # noqa: E402
    _latest_by_token,
)


app = FastAPI(title="PREDAIOT Engine")
register_rate_limiter(app)

# ── API routers (extracted from main.py; Router Extraction, step 6). Registered
# here, BEFORE the catch-all StaticFiles mount at "/" at the end of this file. ──
from app.api.security import router as security_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.api.legacy import router as legacy_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.tenancy import router as tenancy_router  # noqa: E402
from app.api.records import router as records_router  # noqa: E402
from app.api.decisions import router as decisions_router  # noqa: E402
from app.api.live import router as live_router  # noqa: E402
app.include_router(security_router)
app.include_router(health_router)
app.include_router(legacy_router)
app.include_router(auth_router)
app.include_router(tenancy_router)
app.include_router(records_router)
app.include_router(decisions_router)
app.include_router(live_router)


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
# _latest_by_token / _EMPTY_LATEST / shared_audits → app/core/state.py (step 6 prep;
# the D7 in-process state seam). Imported back above.

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
    _dispatch_mode, _MILP_LAST,
)

# ==========================================
# 5. NEW: EDA Intelligence Engine
# ==========================================
# _classify_decision -> optimization_service (economic leaf); _live_decision_core
# -> telemetry_service (refactor step 3, service 4).
from app.services.telemetry_service import _live_decision_core  # noqa: E402

# Economic-narrative builders now in app/domain/economics.py (first domain module;
# refactor step 3, service 5 part 2). Internal helpers stay private to the module.

# ==========================================
# 6. Central Calculation Engine  (CORE UNCHANGED + EDA LAYER)
# ==========================================
# Central calculation engine now in app/services/audit_service.py (orchestrator;
# refactor step 3, service 5 part 3).
from app.services.audit_service import process_calculation  # noqa: E402

# ==========================================
# 7. API Endpoints  (UNCHANGED CORE + universal file parser + trial gate)
# ==========================================

# ---- Trial Gate endpoints --------------------------------------------------
from fastapi import BackgroundTasks  # local import keeps the imports block tidy

# trial/* + auth/* endpoints -> app/api/auth.py (Router Extraction, step 6).


# assets + org/users endpoints -> app/api/tenancy.py (Router Extraction, step 6).


# ---- Sprint 2: Audit History + Economic Memory (L3, blueprint §3) ----------
# -> app/api/records.py (Router Extraction, step 6).


# -> app/api/decisions.py (Router Extraction, step 6).


# -> app/api/live.py (Router Extraction, step 6).


# -> app/api/records.py (Router Extraction, step 6).


# Security-log endpoints → app/api/security.py (Router Extraction, step 6).


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
    ASSET_META_ALIASES, _normalise_col, _resolve_columns_verbose, _detect_and_apply_units, _detect_excel_serial_timestamps,
    _parse_timestamps, _detect_and_resample,
    _dq, _order_and_dedupe_timestamps, _coerce_numeric_columns, _build_sensor_quality_flags,
    _collect_data_quality_counts, _dqi_components_from_manifest, _forecast_reliability_from_snapshot, _detect_currency,
    _parse_file_bytes,
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

# /api/historical, /api/share, /share/{token}, /api/latest → app/api/legacy.py
# (Router Extraction, step 6). mqtt/status stays with the MQTT bridge below.

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
    _build_certificate,
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

# /health, /version, /health/db -> app/api/health.py (Router Extraction, step 6).


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
