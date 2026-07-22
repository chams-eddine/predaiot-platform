# -*- coding: utf-8 -*-
"""Phase 1 load-audit correctness (Muscat Steel category error).

Root cause: a pure-consumption asset (furnace) defaulted to asset_type='Generic'
→ the STORAGE (battery) formula ran on it → negative "captured value", DQ 0.0.
The engine already had a correct LOAD track; it just wasn't routed to. These gates
pin: (1) signal-based archetype classification, (2) the load route yields
non-negative gap + DQ∈[0,1] where the storage route did not, (3) daily resolution
is detected (no more '91 days = 91 hours'), (4) the validation gates.
No engine FORMULA changed — only track selection.
"""
from app.schemas import AssetSpecs
from app.services.audit_service import process_calculation
from app.services.facility.intake import classify_archetype
from app.services.validation import validate_audit_result


_CONSUMPTION_TS = [
    {"hour": 0, "price": 16.0, "actual_charge": 22.0, "actual_discharge": 0.0},
    {"hour": 1, "price": 36.0, "actual_charge": 22.0, "actual_discharge": 0.0},
    {"hour": 2, "price": 46.0, "actual_charge": 22.0, "actual_discharge": 0.0},
]


def test_classify_archetype_from_signals():
    load_cm = {"price": "p", "actual_charge": "c"}
    assert classify_archetype(load_cm, _CONSUMPTION_TS)[0] == "load"
    # battery: charge + discharge + soc → storage
    bess = [{"actual_charge": 5, "actual_discharge": 5, "soc": 0.5}]
    assert classify_archetype({"soc": "s"}, bess)[0] == "storage"
    # curtailable generation → intermittent
    gen = [{"actual_discharge": 10, "curtailment_mw": 1}]
    assert classify_archetype({"curtailment_mw": "cur"}, gen)[0] == "intermittent"
    # nothing decisive → don't override
    assert classify_archetype({}, [{}])[0] is None


def test_load_route_is_sane_where_storage_was_not():
    # Same consumption data, two routes. Storage (the bug) → negative captured.
    storage = process_calculation(AssetSpecs(asset_type="Generic", p_max=32.0, deg_cost=0.0),
                                  _CONSUMPTION_TS, save_to_db=False, dt_hours=24.0, currency="OMR")
    load = process_calculation(AssetSpecs(asset_type="load", p_max=32.0, deg_cost=0.0),
                               _CONSUMPTION_TS, save_to_db=False, dt_hours=24.0, currency="OMR")
    assert storage.edv_actual_total < 0                      # the reported bug
    assert load.edv_actual_total >= 0                        # fixed
    assert load.total_gap_usd >= 0                           # gap non-negative by construction
    assert 0.0 <= load.dq_score <= 1.0


def test_daily_resolution_detected():
    import pandas as pd
    from app.services.ingestion import _detect_and_resample
    df = pd.DataFrame({"hour": pd.date_range("2026-04-01", periods=91, freq="D", tz="UTC"),
                       "price": [16.0] * 91, "actual_charge": [22.0] * 91})
    _, notes = _detect_and_resample(df)
    assert notes["detected_resolution_sec"] == 86400          # not 3600 (the '91h' bug)
    assert notes["detected_resolution_label"] == "daily"


def test_validation_gates():
    # A sane result passes; currency defaulted → soft warning.
    ok = validate_audit_result({"dq_score": 0.7, "dq_score_raw": 0.7, "total_gap_usd": 100.0},
                               currency_source="defaulted")
    assert ok["passed"] is True and any("currency" in w for w in ok["warnings"])
    # Negative gap for a LOAD is impossible-by-construction → HARD fail (withheld).
    bad = validate_audit_result({"dq_score": 0.0, "total_gap_usd": -500.0}, asset_class="load")
    assert bad["passed"] is False and any("negative" in e for e in bad["errors"])
    # Negative gap for STORAGE = actual beat the modeled optimum → WARNING, not halt.
    stor = validate_audit_result({"dq_score": 1.0, "total_gap_usd": -70.0}, asset_class="storage")
    assert stor["passed"] is True
    # Extreme DQ → review warning, not a hard fail.
    extreme = validate_audit_result({"dq_score": 0.2, "total_gap_usd": 10.0})
    assert extreme["passed"] is True and any("extreme" in w for w in extreme["warnings"])
