# -*- coding: utf-8 -*-
"""Request logging: client-IP resolution + the per-request API access-log
middleware. Extracted VERBATIM from main.py (refactor step 2B). Imports only
core + models (downward); registered onto the app by main.py to preserve
middleware order. _client_ip is also reused by the rate-limit key function.
"""
from datetime import datetime

from app.core.config import SessionLocal
from app.models import APIAccessLog

# _security_log → app/repositories/security_log.py (step 7; D5b resolved — core no
# longer writes SecurityAuditLog; the chained-append helper lives with its repo).


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
