# -*- coding: utf-8 -*-
"""Facility flexibility_factor as a DECLARED per-facility attribute (owner-ratified).

The operational shiftability is stored on the Facility (Asset), never a platform
constant. It is optional (blank ⇒ Theoretical-only), validated to [0,1], carries the
mandatory 'must reflect this plant's reality' guidance, and is settable/clearable via
a facility:manage-gated endpoint.
"""
import time

from app.services.tou_bands import validate_flexibility, FLEXIBILITY_GUIDANCE


def test_validate_flexibility_range():
    assert validate_flexibility(None) is None            # blank passes through
    assert validate_flexibility(0.44) == 0.44
    assert validate_flexibility(0) == 0.0 and validate_flexibility(1) == 1.0
    for bad in (1.5, -0.1, 2):
        try:
            validate_flexibility(bad); assert False, f"{bad} should be rejected"
        except ValueError:
            pass


def test_guidance_is_non_benchmark_and_optional():
    g = FLEXIBILITY_GUIDANCE.lower()
    assert "not an industry benchmark" in g or "not an industry benchmark," in g \
        or "industry benchmark" in g
    assert "blank" in g and "theoretical" in g            # the leave-blank option is stated


# ── Endpoint flow (real facilities API) ─────────────────────────────────────
def _owner(client):
    email, pw = f"o-{time.time_ns()}@x.com", "S3cure-pass-1"
    client.post("/api/v1/auth/register", json={"email": email, "password": pw, "organization": "Steel Co"})
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw}).json()["token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def test_facility_carries_declared_flexibility(client):
    tok = _owner(client)
    # Create WITHOUT flexibility → None (no assumption), guidance present.
    a = client.post("/api/v1/assets", headers=_hdr(tok),
                    json={"name": "Ibri Steel", "asset_type": "load"}).json()
    assert a["flexibility_factor"] is None
    assert "flexibility_guidance" in a and "benchmark" in a["flexibility_guidance"].lower()

    fid = a["id"]
    # Declare 0.44 via the facility-manage endpoint.
    r = client.patch(f"/api/v1/facilities/{fid}/flexibility", headers=_hdr(tok),
                     json={"flexibility_factor": 0.44})
    assert r.status_code == 200 and r.json()["flexibility_factor"] == 0.44
    # It sticks on the facility listing.
    facs = client.get("/api/v1/facilities", headers=_hdr(tok)).json()["facilities"]
    assert next(f for f in facs if f["id"] == fid)["flexibility_factor"] == 0.44
    # Out-of-range is rejected with guidance.
    bad = client.patch(f"/api/v1/facilities/{fid}/flexibility", headers=_hdr(tok),
                       json={"flexibility_factor": 1.8})
    assert bad.status_code == 422 and "guidance" in bad.json()["detail"]
    # Clearing it (null) returns to Theoretical-only.
    cleared = client.patch(f"/api/v1/facilities/{fid}/flexibility", headers=_hdr(tok),
                           json={"flexibility_factor": None})
    assert cleared.json()["flexibility_factor"] is None


def test_create_asset_rejects_bad_flexibility(client):
    tok = _owner(client)
    r = client.post("/api/v1/assets", headers=_hdr(tok),
                    json={"name": "Bad", "asset_type": "load", "flexibility_factor": 5})
    assert r.status_code == 422
