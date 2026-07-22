# -*- coding: utf-8 -*-
"""Facility-scoped RBAC (Org → Facility → Role). The permission matrix + the
end-to-end guarantee: a member sees/acts only on facilities they're granted,
org owner/admin remain org-wide superusers, and cross-org access is denied.
The economic engine is never involved — this is pure API-boundary authorization.
"""
import time

from app.core import authz


# ── Pure permission matrix (no DB) ──────────────────────────────────────────
def test_permission_matrix():
    assert authz.permitted("auditor", authz.RUN_AUDIT) is True
    assert authz.permitted("viewer", authz.RUN_AUDIT) is False
    assert authz.permitted("executive", authz.EXPORT_REPORT) is True
    assert authz.permitted("operator", authz.MANAGE_DEPLOY) is True
    # No facility role grants member management — that's owner/admin (or explicit).
    assert authz.permitted("operator", authz.MANAGE_FACILITY) is False
    assert authz.FACILITY_ROLES == ("auditor", "operator", "executive", "viewer")


# ── End-to-end via the real endpoints ───────────────────────────────────────
def _register(client, org="Acme Energy"):
    email, pw = f"owner-{time.time_ns()}@preda-iot.com", "S3cure-pass-123"
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": pw, "organization": org})
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"], email, pw


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _new_facility(client, owner_tok, name):
    r = client.post("/api/v1/assets", headers=_hdr(owner_tok),
                    json={"name": name, "asset_type": "storage"})
    assert r.status_code == 200, r.text[:200]
    return r.json()["id"]


def _add_org_member(client, owner_tok, role="viewer"):
    email, pw = f"member-{time.time_ns()}@preda-iot.com", "M3mber-pass-123"
    r = client.post("/api/v1/org/users", headers=_hdr(owner_tok),
                    json={"email": email, "role": role, "password": pw})
    assert r.status_code == 200, r.text[:200]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    return login.json()["token"], email


def test_owner_sees_all_member_sees_only_granted(client):
    owner_tok, _, _ = _register(client)
    fac_a = _new_facility(client, owner_tok, "Steel Plant A")
    fac_b = _new_facility(client, owner_tok, "Solar Farm B")

    member_tok, member_email = _add_org_member(client, owner_tok)

    # Owner (org superuser) sees both facilities.
    owned = client.get("/api/v1/facilities", headers=_hdr(owner_tok)).json()["facilities"]
    assert {f["id"] for f in owned} >= {fac_a, fac_b}

    # Member with no membership yet sees none.
    assert client.get("/api/v1/facilities", headers=_hdr(member_tok)).json()["facilities"] == []

    # Grant the member auditor on A only.
    g = client.post(f"/api/v1/facilities/{fac_a}/members", headers=_hdr(owner_tok),
                    json={"email": member_email, "role": "auditor"})
    assert g.status_code == 200, g.text[:200]

    seen = client.get("/api/v1/facilities", headers=_hdr(member_tok)).json()["facilities"]
    assert [f["id"] for f in seen] == [fac_a]           # A only, never B


def test_viewer_role_cannot_manage_members(client):
    owner_tok, _, _ = _register(client)
    fac = _new_facility(client, owner_tok, "Plant V")
    member_tok, member_email = _add_org_member(client, owner_tok)
    client.post(f"/api/v1/facilities/{fac}/members", headers=_hdr(owner_tok),
                json={"email": member_email, "role": "viewer"})
    # A facility viewer may VIEW members but not GRANT them (needs facility:manage).
    assert client.get(f"/api/v1/facilities/{fac}/members",
                      headers=_hdr(member_tok)).status_code == 200
    denied = client.post(f"/api/v1/facilities/{fac}/members", headers=_hdr(member_tok),
                         json={"email": member_email, "role": "operator"})
    assert denied.status_code == 403


def test_cross_org_access_denied(client):
    owner1, _, _ = _register(client, org="Org One")
    fac1 = _new_facility(client, owner1, "Org1 Plant")
    owner2, _, _ = _register(client, org="Org Two")
    # Owner of a different org cannot view another org's facility members.
    r = client.get(f"/api/v1/facilities/{fac1}/members", headers=_hdr(owner2))
    assert r.status_code == 403
    # ...nor grant on it.
    r2 = client.post(f"/api/v1/facilities/{fac1}/members", headers=_hdr(owner2),
                     json={"email": "x@y.com", "role": "auditor"})
    assert r2.status_code == 403
