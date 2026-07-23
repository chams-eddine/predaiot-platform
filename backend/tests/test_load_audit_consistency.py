# -*- coding: utf-8 -*-
"""Daily load-audit INTERNAL CONSISTENCY (the Muscat Steel regression).

The reported failure: a priced daily steel file produced a self-contradictory
report — EDE 100%, ELR 0%, No action, yet a multi-million Economic Gap. Root cause:
kWh/day consumption ingested as MW, and the load optimizer capped below the actual
total (Σ_opt ≠ Σ_act), so EDV_actual ≫ EDV_optimal (clamped to EDE 100%) while the
cost gap ballooned. This gate pins the fix end-to-end through /audit/file:
units→MW, Σ_opt=Σ_act (gap identity), one coherent efficiency (EDE==DQ), and the
facility recognized as a Steel Plant. Self-contained data (no external file).
"""
import time
from types import SimpleNamespace

# 8 days, day-Month-year dates (→ daily resolution), a varying tariff, a dedicated
# EAF channel (→ EAF recognition), and Total Power Consumption in kWh/DAY.
_ROWS = [
    ("01-April-2026", 16, 365369, 530950),
    ("02-April-2026", 19, 360673, 536150),
    ("03-April-2026", 36, 338025, 515910),
    ("04-April-2026", 46, 340156, 515530),
    ("05-April-2026", 28, 261213, 427010),
    ("06-April-2026", 16, 354714, 528240),
    ("07-April-2026", 36, 351020, 521300),
    ("08-April-2026", 46, 349880, 519870),
]
_CSV = "Date,price,Power Con. EAF (KWH/Day),Total Power Consumption (KWH/Day)\n" + \
       "\n".join(f"{d},{p},{eaf},{tot}" for d, p, eaf, tot in _ROWS)


def _run(client):
    import main
    from app.core.dependencies import require_audit_runner
    main.app.dependency_overrides[require_audit_runner] = \
        lambda: SimpleNamespace(token=f"t-{time.time_ns()}", email="ci@x.com", user_id=None)
    try:
        return client.post("/api/v1/audit/file",
                           files={"file": ("steel_daily.csv", _CSV, "text/csv")})
    finally:
        main.app.dependency_overrides.pop(require_audit_runner, None)


def test_daily_load_audit_internally_consistent(client):
    r = _run(client)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    m = d.get("eda_metrics") or {}

    # Item 1 — units: kWh/day → MW (tens of MW, not hundreds of thousands).
    assert d["asset_class"] == "load"
    assert abs(d["decision_log"][0]["actual_action"]) < 1000

    # Item 2 — energy conservation ⇒ gap identity holds.
    assert abs((d["edv_optimal_total"] - d["edv_actual_total"]) - d["total_gap_usd"]) < 1.0

    # Item 3 — one coherent efficiency; no EDE-100%-with-huge-gap contradiction.
    assert 0.0 <= d["dq_score"] <= 1.0
    assert d["total_gap_usd"] >= -1.0
    assert m["economic_decision_efficiency"] <= 100.0
    assert abs(m["economic_decision_efficiency"] - d["dq_score"] * 100) < 0.05      # EDE == DQ
    assert abs(m["economic_leakage_ratio"] - (100.0 - m["economic_decision_efficiency"])) < 0.05
    # the exact pathological state must be impossible:
    assert not (m["economic_decision_efficiency"] >= 99.5 and d["total_gap_usd"] > 1000)

    # Item 4 — the audit FUE recognizes the facility (same as the engineering path).
    assert d["facility_profile"]["facility_type"]["value"] == "Steel Plant"
    assert d["facility_profile"]["equipment"][0]["identity"]["value"] == "electric_arc_furnace"

    assert (d.get("validation") or {}).get("passed") is True
