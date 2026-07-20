# -*- coding: utf-8 -*-
"""Health + build-identity API router — /health (liveness), /version (deployed
git SHA for deterministic deploy verification), /health/db (storage-backend
evidence: dialect, persistence, alembic head, row counts, secret/key status —
never values). Extracted VERBATIM from main.py (Router Extraction, step 6).

Dependency direction: api -> core (config.engine, state boot markers, versions)
+ services.certificate_service (_cert_signing_key status probe) + stdlib.

NOTE (non-verbatim line, same class as D12): _build_version resolves the baked
VERSION file relative to the backend root — recomputed as 3 levels up from this
file after the move (was: alongside main.py).
"""
import base64 as _base64
import os

from fastapi import APIRouter

from app.core.config import engine
from app.core.state import _BOOT_ID, _BOOT_TIME
from app.services.certificate_service import _CERT_KEY_ENV, _cert_signing_key

router = APIRouter()

# backend root = .../backend (this file lives at backend/app/api/health.py)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_version() -> str:
    """Deployed build identity. Render injects RENDER_GIT_COMMIT at build time; a
    baked VERSION file (Dockerfile / on-prem image) is the fallback; 'unknown' only
    in a bare checkout. Makes deploys verifiable via GET /version instead of
    inferring from boot time (deployment-maturity fix)."""
    sha = (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT")
           or os.environ.get("SOURCE_VERSION"))
    if not sha:
        try:
            _vf = os.path.join(_BACKEND_DIR, "VERSION")
            if os.path.exists(_vf):
                with open(_vf, encoding="utf-8") as _f:
                    sha = _f.read().strip()
        except Exception:
            sha = None
    return sha or "unknown"


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/version")
def version():
    """Deployed build identity — deterministic deploy verification."""
    from app.core.versions import ENGINE_VERSION
    return {
        "service": "predaiot-backend",
        "engine_version": ENGINE_VERSION,
        "git_commit": _build_version(),
        "boot_id": _BOOT_ID,
        "boot_time": _BOOT_TIME.isoformat() + "Z",
    }


@router.get("/health/db")
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
