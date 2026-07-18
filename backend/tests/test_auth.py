# -*- coding: utf-8 -*-
"""Account-auth characterization: JWT + bcrypt round-trip. Covers app/core/security.py
so the auth extraction is exercised end-to-end (register -> login -> me)."""
import time


def _email():
    return f"acct-{time.time_ns()}@preda-iot.com"


def test_register_login_me_roundtrip(client):
    email, pw = _email(), "S3cure-pass-123"
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": pw, "organization": "Acme Energy"})
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("token")

    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200
    tok = r2.json()["token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "owner"


def test_login_wrong_password_401(client):
    email, pw = _email(), "Right-pass-123"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": pw, "organization": "Acme"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401
