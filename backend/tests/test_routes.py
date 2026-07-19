# -*- coding: utf-8 -*-
"""Route-inventory guard for the Router Extraction phase (step 6).

Freezes every application (method, path) pair. Moving a route into an APIRouter
must NOT drop, rename, duplicate, or shadow it — any such change fails here
instantly. When routes change on purpose, update FROZEN in the SAME commit so the
diff shows the intent. Framework routes (/docs, /openapi.json, /redoc) are excluded.
"""
import main

FROZEN = {
    ("GET", "/api/historical"),
    ("GET", "/api/latest"),
    ("GET", "/api/v1/assets"),
    ("GET", "/api/v1/audit/ledger.csv"),
    ("GET", "/api/v1/audit/pdf/latest"),
    ("GET", "/api/v1/audits"),
    ("GET", "/api/v1/audits/{audit_id}"),
    ("GET", "/api/v1/audits/{audit_id}/decisions"),
    ("GET", "/api/v1/audits/{audit_id}/economic-state"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/certificate"),
    ("GET", "/api/v1/certificate/verify/{cert_id}"),
    ("GET", "/api/v1/decisions"),
    ("GET", "/api/v1/decisions/lifecycle/verify"),
    ("GET", "/api/v1/decisions/{decision_id}/lifecycle"),
    ("GET", "/api/v1/decisions/{decision_id}/outcomes"),
    ("GET", "/api/v1/economic-states"),
    ("GET", "/api/v1/governance"),
    ("GET", "/api/v1/governance/verify"),
    ("GET", "/api/v1/integrations/mqtt/status"),
    ("GET", "/api/v1/live/state"),
    ("GET", "/api/v1/live/{stream_id}/certified-state"),
    ("GET", "/api/v1/live/{stream_id}/reconciliations"),
    ("GET", "/api/v1/memory"),
    ("GET", "/api/v1/metrics/registry"),
    ("GET", "/api/v1/org/users"),
    ("GET", "/api/v1/outcomes"),
    ("GET", "/api/v1/outcomes/{outcome_id}/governance"),
    ("GET", "/api/v1/reconciliations"),
    ("GET", "/api/v1/reconciliations/verify"),
    ("GET", "/api/v1/security/log"),
    ("GET", "/api/v1/security/log/verify"),
    ("GET", "/api/v1/trial/status"),
    ("GET", "/health"),
    ("GET", "/health/db"),
    ("GET", "/share/{token}"),
    ("GET", "/version"),
    ("PATCH", "/api/v1/org/users/{member_id}"),
    ("POST", "/api/share"),
    ("POST", "/api/v1/ai-enhance"),
    ("POST", "/api/v1/assets"),
    ("POST", "/api/v1/audit"),
    ("POST", "/api/v1/audit/file"),
    ("POST", "/api/v1/audit/inspect"),
    ("POST", "/api/v1/audit/pdf"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/certificate"),
    ("POST", "/api/v1/decisions/{decision_id}/outcome"),
    ("POST", "/api/v1/decisions/{decision_id}/transition"),
    ("POST", "/api/v1/live/ingest"),
    ("POST", "/api/v1/live/step"),
    ("POST", "/api/v1/live/{stream_id}/reconcile"),
    ("POST", "/api/v1/org/users"),
    ("POST", "/api/v1/outcomes/{outcome_id}/govern"),
    ("POST", "/api/v1/trial/start"),
    ("WEBSOCKET", "/ws/live"),
}

_FRAMEWORK = {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}


def _current_routes():
    out = set()
    for r in main.app.routes:
        path = getattr(r, "path", None)
        if not path or path in _FRAMEWORK:
            continue
        for m in (getattr(r, "methods", None) or ["WEBSOCKET"]):
            if m in ("HEAD", "OPTIONS"):
                continue
            out.add((m, path))
    return out


def test_route_inventory_unchanged():
    current = _current_routes()
    assert current == FROZEN, (
        f"missing={sorted(FROZEN - current)} unexpected={sorted(current - FROZEN)}"
    )
