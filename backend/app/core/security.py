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
