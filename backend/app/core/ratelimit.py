# -*- coding: utf-8 -*-
"""Rate limiting (slowapi) — lazy-imported so a deploy without slowapi still boots
and the endpoints just aren't rate-limited (fail-open: availability > perfect
throttling on a pre-seed platform). Extracted VERBATIM from main.py (refactor step
6 prep, Router Extraction).

Lives in core so every api router (`@limiter.limit`) and the composition root share
ONE limiter without importing `main` (which would create an import cycle once the
routes move into routers).

Dependency direction: core.ratelimit -> core.logging (_client_ip). Used by: api
routers + main (register_rate_limiter).
"""
from app.core.logging import _client_ip

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    _HAS_SLOWAPI = True
except ImportError:
    _HAS_SLOWAPI = False


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


if _HAS_SLOWAPI:
    limiter = Limiter(key_func=_rate_limit_key)
else:
    # Null-object shim so the @limiter.limit(...) decorators are no-ops when
    # slowapi isn't installed. Keeps the audit code path identical.
    class _NullLimiter:
        def limit(self, *_args, **_kwargs):
            def _wrap(fn):
                return fn
            return _wrap
    limiter = _NullLimiter()


def register_rate_limiter(app) -> None:
    """Wire the shared limiter onto a FastAPI app (called from the composition root)."""
    if _HAS_SLOWAPI:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
