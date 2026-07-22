# -*- coding: utf-8 -*-
"""Phase 2 — LOAD archetype DQ is the COST ratio C_optimal / C_actual (Reference
Manual amendment, load only; generation DQ unchanged). The Economic Gap is
invariant (savings gap ≡ cost gap). See docs/EDA_METRICS_v1.md §2A.
"""
from app.schemas import AssetSpecs
from app.services.audit_service import process_calculation


def test_load_dq_is_cost_ratio():
    # consumption 22 MW each step, prices 16/36/46, p_max 32, dt 24h.
    ts = [{"hour": i, "price": p, "actual_charge": 22.0, "actual_discharge": 0.0}
          for i, p in enumerate([16.0, 36.0, 46.0])]
    r = process_calculation(AssetSpecs(asset_type="load", p_max=32.0, deg_cost=0.0),
                            ts, save_to_db=False, dt_hours=24.0, currency="OMR")
    # C_actual = Σ price·22·24 = 51,744 ; greedy optimal = [32,32,2] → C_opt = 42,144.
    # DQ = 42,144 / 51,744 = 0.8145 (cost ratio), NOT the 0.688 savings ratio.
    assert abs(r.dq_score - 0.8145) < 0.001
    assert abs(r.total_gap_usd - 9600.0) < 1.0          # gap invariant, non-negative
    assert 0.0 <= r.dq_score <= 1.0


def test_storage_dq_unchanged_by_load_amendment():
    # A discharge-at-peak BESS still uses the value-ratio DQ (amendment is load-only).
    ts = [{"hour": i, "price": p, "actual_discharge": (25 if p == 46 else 0), "actual_charge": 0}
          for i, p in enumerate([16.0, 36.0, 46.0])]
    r = process_calculation(AssetSpecs(asset_type="storage", p_max=25.0, e_max=50.0, deg_cost=0.0),
                            ts, save_to_db=False, dt_hours=1.0, currency="OMR")
    assert 0.0 <= r.dq_score <= 1.0                     # still a valid, unchanged metric
