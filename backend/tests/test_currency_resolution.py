# -*- coding: utf-8 -*-
"""No-Fabrication currency resolution (owner-ratified).

An undeclared, undetectable currency must be reported as UNKNOWN — never silently
assumed to be USD. A declared currency (upload selector / facility) is honoured.
Precedence: data-detected > [bill] > facility > organization > operator-declared > UNKNOWN.
"""
import twin


def test_undeclared_currency_resolves_to_unknown_not_usd(client, token):
    hdrs = token()
    df = twin.build(asset="bess", hours=24, dt_min=60, seed=5, regime="normal")
    r = client.post("/api/v1/audit/file", headers=hdrs,
                    files={"file": ("a.csv", twin.to_csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    d = r.json()
    assert d["currency"] == "UNKNOWN"                       # never a silent USD
    assert d["validation"]["currency_source"] == "unknown"


def test_operator_declared_currency_is_honoured(client, token):
    hdrs = token()
    df = twin.build(asset="bess", hours=24, dt_min=60, seed=5, regime="normal")
    r = client.post("/api/v1/audit/file", headers=hdrs,
                    files={"file": ("a.csv", twin.to_csv_bytes(df), "text/csv")},
                    data={"currency": "OMR"})
    assert r.status_code == 200
    d = r.json()
    assert d["currency"] == "OMR"
    assert d["validation"]["currency_source"] == "declared"
