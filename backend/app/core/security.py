# -*- coding: utf-8 -*-
"""Authentication primitives — JWT + bcrypt (COMMODITY per blueprint §0; no
external IdP so on-prem/sovereign works). Extracted verbatim from main.py
(refactor step 2A).

Duck-types the user object (annotation only), so this module has NO dependency
on the ORM models and stays at the bottom of the import graph.
"""
import hashlib as _hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
import jwt as _pyjwt

def _resolve_auth_secret(environ=None) -> str:
    """Resolve the JWT signing secret, FAIL-CLOSED in production.

    If PREDAIOT_AUTH_SECRET is set, it is authoritative. If it is missing:
      - In production (a Postgres DATABASE_URL is configured) we REFUSE to start.
        The old behaviour derived a secret from this file's absolute path, which
        on a fixed container image (`/app/app/core/security.py`) is publicly
        derivable — i.e. anyone could forge tokens. Failing closed is mandatory.
      - In dev/test (SQLite / no Postgres) we keep a deterministic per-machine
        fallback so local work and the test suite run without extra setup.
    """
    environ = os.environ if environ is None else environ
    secret = environ.get("PREDAIOT_AUTH_SECRET", "")
    if secret:
        return secret
    is_production = "postgres" in environ.get("DATABASE_URL", "").lower()
    if is_production:
        raise RuntimeError(
            "PREDAIOT_AUTH_SECRET is not set but a production (Postgres) database "
            "is configured. Refusing to start with a derivable dev secret — set "
            "PREDAIOT_AUTH_SECRET in the environment."
        )
    print("[startup] WARNING: PREDAIOT_AUTH_SECRET not set — using dev-only derived secret.")
    return _hashlib.sha256(f"predaiot-dev-{os.path.abspath(__file__)}".encode()).hexdigest()


_AUTH_SECRET = _resolve_auth_secret()

_JWT_TTL_HOURS = int(os.environ.get("PREDAIOT_JWT_TTL_HOURS", "24"))
_ROLES = ("owner", "admin", "asset_manager", "operator", "finance", "viewer")


def _hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode("utf-8"), _bcrypt.gensalt()).decode("ascii")


def _verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return _bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("ascii"))
    except Exception:
        return False


def _issue_jwt(user) -> str:
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
