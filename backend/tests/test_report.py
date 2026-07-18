# -*- coding: utf-8 -*-
"""Report rendering snapshot tests — guard app/services/report_service.py against
accidental visual regressions. Assert each section still renders (in order) in
the PDF, and the ledger CSV stays well-formed."""
import io

import twin
from pypdf import PdfReader


def _pdf_text(client, token):
    h = token()
    df = twin.build(asset="bess", hours=24, dt_min=60, seed=7, regime="volatile")
    client.post("/api/v1/audit/file", headers=h,
                files={"file": ("a.csv", twin.to_csv_bytes(df), "text/csv")})
    r = client.get("/api/v1/audit/pdf/latest", headers=h)
    assert r.status_code == 200
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
    return text, h


# Ordered section snapshot: title, exec summary, root causes, opportunity table,
# risk, certificate block, audit confidence, footer email.
_SECTIONS = ["ECONOMIC DECISION AUDIT", "EXECUTIVE SUMMARY", "TOP ROOT CAUSES",
             "TOP OPPORTUNITIES", "Risk Level", "CERTIFICATION",
             "Audit Confidence", "chams@preda-iot.com"]


def test_pdf_section_snapshot(client, token):
    text, _ = _pdf_text(client, token)
    for sec in _SECTIONS:
        assert sec in text, f"PDF section missing: {sec}"
    # stable structural order: title -> executive summary -> certification block
    assert text.find("ECONOMIC DECISION AUDIT") < text.find("EXECUTIVE SUMMARY") < text.find("CERTIFICATION")


def test_ledger_csv_wellformed(client, token):
    _, h = _pdf_text(client, token)
    r = client.get("/api/v1/audit/ledger.csv", headers=h)
    assert r.status_code == 200
    rows = r.content.decode().splitlines()
    assert len(rows) > 1 and "," in rows[0]      # header + data rows
