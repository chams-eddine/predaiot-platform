# -*- coding: utf-8 -*-
"""Engine-math characterization: hard economic invariants + regression guards
for defects fixed by the validation campaign."""
from conftest import audit_invariants


def _audit_csv(client, hdrs, csv):
    return client.post("/api/v1/audit/file", headers=hdrs,
                       files={"file": ("t.csv", csv.encode(), "text/csv")})


def test_zero_price_day_no_opportunity(client, token):
    rows = "\n".join(f"2024-07-01 {h:02d}:00:00,0,0,0" for h in range(24))
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw,bess_charge_mw\n" + rows)
    d = r.json()
    assert r.status_code == 200
    assert d["dq_score"] == 1.0 and d["total_gap_usd"] == 0.0


def test_constant_price_no_arbitrage(client, token):
    rows = "\n".join(f"2024-07-01 {h:02d}:00:00,50.0,0,0" for h in range(24))
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw,bess_charge_mw\n" + rows)
    assert r.status_code == 200 and r.json()["dq_score"] == 1.0


def test_gap_identity_and_ledger(client, token):
    rows = "\n".join(f"2024-07-01 {h:02d}:00:00,{10 + h},{25 if h == 20 else 0},0" for h in range(24))
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw,bess_charge_mw\n" + rows)
    assert r.status_code == 200
    assert audit_invariants(r.json()) == []


def test_header_only_is_clean_4xx_not_500(client, token):
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw\n")
    assert r.status_code == 400


def test_offset_timestamps_do_not_500(client, token):
    # regression guard: off-the-hour uniform data (every real SCADA export)
    rows = "\n".join(f"2024-07-01 {h:02d}:09:00,{20 + (h * 7) % 60},{25 if h == 20 else 0},0" for h in range(24))
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw,bess_charge_mw\n" + rows)
    assert r.status_code == 200
    assert audit_invariants(r.json()) == []


def test_corrupt_secondary_column_does_not_500(client, token):
    # regression guard: '#REF!' in a non-load-bearing column must not crash
    rows = "\n".join(f"2024-07-01 {h:02d}:00:00,{20 + h},0,{'#REF!' if h == 5 else 3.0}" for h in range(24))
    r = _audit_csv(client, token(), "timestamp,spot_price,bess_discharge_mw,grid_demand\n" + rows)
    assert r.status_code == 200


def test_determinism(client, token):
    rows = "\n".join(f"2024-07-01 {h:02d}:00:00,{10 + h},{25 if h in (19, 20) else 0},0" for h in range(24))
    csv = "timestamp,spot_price,bess_discharge_mw,bess_charge_mw\n" + rows
    g1 = _audit_csv(client, token(), csv).json()["total_gap_usd"]
    g2 = _audit_csv(client, token(), csv).json()["total_gap_usd"]
    assert abs(g1 - g2) < 1e-6
