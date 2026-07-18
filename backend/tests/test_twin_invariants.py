# -*- coding: utf-8 -*-
"""Digital-twin campaign (CI subset): drive many simulated scenarios through
the engine and assert invariants + never-500 on parseable input."""
import itertools

import pytest
from conftest import audit_invariants
import twin

ASSETS = ["bess", "solar"]
REGIMES = ["normal", "volatile", "negative", "flat"]
FAULTSETS = [(), ("offset_timestamps",), ("negative_prices",), ("price_spike",),
             ("duplicate_events",), ("out_of_order",), ("corrupted_packets",),
             ("offset_timestamps", "price_spike")]

SCENARIOS = [(a, rg, f) for a, rg, f in itertools.product(ASSETS, REGIMES, FAULTSETS)]


@pytest.mark.parametrize("asset,regime,faults", SCENARIOS)
def test_scenario_never_500_and_invariants_hold(client, token, asset, regime, faults):
    df = twin.build(asset=asset, hours=24, dt_min=60, seed=hash((asset, regime, faults)) % 9999,
                    regime=regime, faults=faults)
    r = client.post("/api/v1/audit/file", headers=token(),
                    files={"file": ("s.csv", twin.to_csv_bytes(df), "text/csv")})
    assert r.status_code != 500, r.text[:200]
    if r.status_code == 200:
        # infeasible/corrupt telemetry is allowed to produce a negative gap; the
        # remaining economic laws must still hold.
        v = [x for x in audit_invariants(r.json()) if x != "gap_identity" or True]
        assert audit_invariants(r.json()) == [], f"{asset}/{regime}/{faults} -> {v}"
