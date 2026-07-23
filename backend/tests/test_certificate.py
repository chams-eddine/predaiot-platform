# -*- coding: utf-8 -*-
"""Certificate/PDF language characterization: recorded-period only, unified
currency, no 'Withdrawn'. Guards the client-review fixes."""
import io

import twin
from pypdf import PdfReader


def test_certificate_language(client, token):
    hdrs = token()
    df = twin.build(asset="bess", hours=48, dt_min=60, seed=11, regime="volatile")
    # No-Fabrication: the synthetic file carries no currency hint, so the operator
    # DECLARES it (as a real one would). Without a declaration it would correctly
    # resolve to UNKNOWN, never a silent USD.
    client.post("/api/v1/audit/file", headers=hdrs,
                files={"file": ("a.csv", twin.to_csv_bytes(df), "text/csv")},
                data={"currency": "USD"})
    r = client.get("/api/v1/audit/pdf/latest", headers=hdrs)
    assert r.status_code == 200
    txt = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "$" not in txt                       # unified currency (code suffix)
    assert "annualis" not in txt.lower()        # recorded-period only
    assert "withdrawn" not in txt.lower()        # rating reserved, not withdrawn
    assert "USD" in txt                          # the DECLARED currency, not a default
    assert "Reserved for EDA Standard v1.0" in txt
    assert "economically achievable value" in txt   # executive verdict line


def test_certificate_json_and_verify(client, token):
    hdrs = token()
    df = twin.build(asset="bess", hours=24, dt_min=60, seed=3, regime="normal")
    client.post("/api/v1/audit/file", headers=hdrs,
                files={"file": ("a.csv", twin.to_csv_bytes(df), "text/csv")})
    cert = client.get("/api/v1/certificate", headers=hdrs).json()
    assert cert.get("certificate_id")
    assert cert.get("dq_score") is not None
