# -*- coding: utf-8 -*-
"""H3 (prod-readiness): the JWT auth secret must FAIL CLOSED in production.

Regression guard for Gate-Review H3. Before the fix, a missing
PREDAIOT_AUTH_SECRET silently fell back to a secret derived from this module's
absolute path — publicly derivable on a fixed container image, so tokens were
forgeable. In production (a Postgres DATABASE_URL) the app must now REFUSE to
start instead. Dev/test keeps a convenience fallback.
"""
import pytest

from app.core.security import _resolve_auth_secret


def test_production_without_secret_refuses_to_start():
    # Postgres configured + no explicit secret → must raise (fail closed).
    with pytest.raises(RuntimeError):
        _resolve_auth_secret({"DATABASE_URL": "postgresql://u:p@host:5432/predaiot"})


def test_dev_without_secret_uses_deterministic_fallback():
    # No production DB + no secret → dev fallback (sha256 hex), no raise.
    s = _resolve_auth_secret({"DATABASE_URL": "sqlite:///./predaiot.db"})
    assert isinstance(s, str) and len(s) >= 32


def test_explicit_secret_is_authoritative_even_in_production():
    assert _resolve_auth_secret(
        {"PREDAIOT_AUTH_SECRET": "a-real-configured-secret",
         "DATABASE_URL": "postgresql://u:p@host:5432/predaiot"}
    ) == "a-real-configured-secret"
