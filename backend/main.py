import os
import uuid
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any

# ── Version identity (chain of custody, C2) → app/core/versions.py (refactor 3).

# ==========================================
# 1. Database Setup  (CORE LOGIC UNCHANGED — connection made fault-tolerant)
# ==========================================
# DB engine / session / URL now live in app/core/config.py (refactor step 2A).
# Imported back so every `engine` / `SessionLocal` / `DATABASE_URL` call site and
# the fault-tolerant startup handler remain unchanged.
from app.core.config import engine  # noqa: E402
# ORM models + Base now live in app/models/tables.py (refactor step 2B).
from app.models import (  # noqa: E402
    Base, TrialLead,
)

# Pure literal constants now live in app/core/constants.py (refactor step 2A).
from app.core.constants import (  # noqa: E402
    _RATING_WITHDRAWN_LABEL,
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
# Auth DI dependencies now live in app/core/dependencies.py (refactor step 2B).
from app.core.dependencies import (  # noqa: E402
    require_trial_or_user,
)




# ==========================================
# Sprint 1: Account auth (COMMODITY per blueprint §0 — minimal robust
# JWT + bcrypt, org-scoped; no external IdP so on-prem/sovereign works).
# Existing trial-token funnel is untouched; account users are dual-accepted
# on every audit endpoint via a linked TrialLead row ("acct-<user_id>").
# ==========================================
# Auth primitives (JWT + bcrypt) now live in app/core/security.py (refactor 2A).








# -> app/api/audit.py (Router Extraction, step 6).






# ==========================================
# 3. FastAPI Setup  (safety hardening applied)
# ==========================================
# Rate limiter — lazy-imported so a deploy without slowapi still boots and
# the endpoints just aren't rate-limited (fail-open, not fail-closed —
# availability > perfect throttling on a pre-seed platform).
# Access-log middleware + _client_ip helper now live in app/core/logging.py (2B).
from app.core.logging import _client_ip, _api_access_log  # noqa: E402,F401
from app.repositories.security_log import _security_log  # noqa: E402,F401
# Rate limiter + in-process runtime state now live in app/core (refactor step 6
# prep) so routers share them without importing main (no import cycle).
from app.core.ratelimit import register_rate_limiter  # noqa: E402


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
from app.api.certificates import router as certificates_router  # noqa: E402
app.include_router(security_router)
app.include_router(health_router)
app.include_router(legacy_router)
app.include_router(auth_router)
app.include_router(tenancy_router)
app.include_router(records_router)
app.include_router(decisions_router)
app.include_router(live_router)
app.include_router(certificates_router)
from app.api.audit import router as audit_router  # noqa: E402
app.include_router(audit_router)


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
# PDF renderer import-back (the certificates segment cut swept the original line).

# ==========================================
# 7. API Endpoints  (UNCHANGED CORE + universal file parser + trial gate)
# ==========================================

# ---- Trial Gate endpoints --------------------------------------------------

# trial/* + auth/* endpoints -> app/api/auth.py (Router Extraction, step 6).


# assets + org/users endpoints -> app/api/tenancy.py (Router Extraction, step 6).


# ---- Sprint 2: Audit History + Economic Memory (L3, blueprint §3) ----------
# -> app/api/records.py (Router Extraction, step 6).


# -> app/api/decisions.py (Router Extraction, step 6).


# -> app/api/live.py (Router Extraction, step 6).


# -> app/api/records.py (Router Extraction, step 6).


# Security-log endpoints → app/api/security.py (Router Extraction, step 6).


# ---- Audit endpoints (gated by trial token) --------------------------------
# -> app/api/audit.py (Router Extraction, step 6).

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


# -> app/api/certificates.py (Router Extraction, step 6).






# -> app/api/audit.py (Router Extraction, step 6).



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
