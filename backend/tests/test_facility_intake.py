# -*- coding: utf-8 -*-
"""Understand-first upload (file classification) gate.

A Facility Definition / nameplate file (Equipment, Rated MW, Transformer MVA,
Voltage Primary …) must NOT fail the audit. It is classified `engineering`, run
through the Facility Understanding Engine ONLY, and returned as a successful
`facility_understanding` result — recognized equipment/capabilities/topology +
guidance requesting operational data. No economic engine, no fabricated numbers.
An operational file still classifies `operational` (full audit path unchanged).
"""
import pandas as pd

from app.services.ingestion.columns import _resolve_columns_verbose
from app.services.facility.intake import (
    classify, extract_nameplate_facts, understand_engineering_file,
)


def _cm(cols):
    return _resolve_columns_verbose(list(cols))["resolved"]


def _steel_nameplate_df():
    # The exact shape from the reported bug: row-per-equipment nameplate export.
    return pd.DataFrame([
        {"Equipment": "Transformer", "Rated (MW)": None, "Transformer (MVA)": 30,
         "Voltage Primary (V)": 33000, "Voltage Secondary Range (V)": "700-1100"},
        {"Equipment": "Electric Arc Furnace", "Rated (MW)": 27, "Transformer (MVA)": None,
         "Voltage Primary (V)": None, "Voltage Secondary Range (V)": None},
    ])


def test_operational_file_classifies_operational():
    cm = _cm(["timestamp", "price", "bess_discharge_mw", "charge_mw", "soc_pct"])
    assert classify(cm) == "operational"


def test_nameplate_file_classifies_engineering():
    cm = _cm(["Equipment", "Rated (MW)", "Transformer (MVA)", "Voltage Primary (V)"])
    assert classify(cm) == "engineering"


def test_nameplate_facts_extracted_across_rows():
    facts, consumed = extract_nameplate_facts(_steel_nameplate_df())
    assert facts["transformer_mva"] == 30.0
    assert facts["voltage_primary"] == 33000.0
    assert facts["rated_power_mw"] == 27.0          # from the EAF row (first non-null)
    assert "Voltage Secondary Range (V)" not in consumed


def test_engineering_file_understood_as_steel_plant():
    df = _steel_nameplate_df()
    r = understand_engineering_file(df, _cm(df.columns), list(df.columns),
                                    input_sha256="deadbeef", filename="ibri_steel_nameplate.csv",
                                    rows_parsed=2, columns_parsed=5)
    assert r["mode"] == "facility_understanding"
    assert r["recognized"] is True
    assert r["facility_type"] == "Steel Plant"
    eq = r["facility_profile"]["equipment"][0]
    assert eq["identity"]["value"] == "electric_arc_furnace"
    caps = [c["value"] for c in eq["capabilities"]]
    assert "flexible_load" in caps and "thermal" in caps
    assert len(r["facility_profile"]["topology"]) > 0          # digital twin generated
    assert r["guidance"]["operational_data_required"] is True


def test_engineering_response_has_no_fabricated_economics():
    df = _steel_nameplate_df()
    r = understand_engineering_file(df, _cm(df.columns), list(df.columns),
                                    input_sha256="x", filename="f.csv")
    for k in ("edv_optimal_total", "edv_actual_total", "dq_score", "total_gap_usd",
              "decision_log", "gap_attribution"):
        assert k not in r


def test_unrecognized_nameplate_still_succeeds_as_unknown():
    # A nameplate file the ontology can't place: still a 200 understanding result,
    # honestly Unknown (No Guess Without Evidence) — never an error.
    df = pd.DataFrame([{"widget_id": "A1", "colour": "blue", "mass_kg": 12}])
    r = understand_engineering_file(df, _cm(df.columns), list(df.columns),
                                    input_sha256="y", filename="widgets.csv")
    assert r["mode"] == "facility_understanding"
    assert r["recognized"] is False
    assert r["facility_type"] == "Unknown"
    assert r["guidance"]["operational_data_required"] is True


# ── Endpoint-level: the exact prod path (auth-free inspect + gated audit/file) ──
_NAMEPLATE_CSV = (
    "Equipment,Rated (MW),Transformer (MVA),Voltage Primary (V),Voltage Secondary Range (V)\n"
    "Transformer,,30,33000,700-1100\n"
    "Electric Arc Furnace,27,,,\n"
)


def _client():
    from fastapi.testclient import TestClient
    from main import app
    return app, TestClient(app)


def test_inspect_endpoint_classifies_engineering_and_is_json_safe():
    # Regression: a sparse nameplate row carries NaN; the inspect response must
    # sanitize NaN→null (not 500). This reproduces the reported production error.
    _app, c = _client()
    r = c.post("/api/v1/audit/inspect",
               files={"file": ("steel_nameplate.csv", _NAMEPLATE_CSV, "text/csv")})
    assert r.status_code == 200
    d = r.json()
    assert d["file_kind"] == "engineering"
    assert d["will_understand"] is True and d["will_succeed"] is False


def test_audit_file_endpoint_returns_facility_understanding():
    # The full upload path: an engineering file must NOT 400; it returns a 200
    # facility_understanding result (recognized Steel Plant), no economic engine.
    from app.core.dependencies import require_audit_runner
    app, c = _client()
    app.dependency_overrides[require_audit_runner] = lambda: object()
    try:
        r = c.post("/api/v1/audit/file",
                   files={"file": ("steel_nameplate.csv", _NAMEPLATE_CSV, "text/csv")})
    finally:
        app.dependency_overrides.pop(require_audit_runner, None)
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "facility_understanding"
    assert d["facility_type"] == "Steel Plant"
    assert "decision_log" not in d and "total_gap_usd" not in d
