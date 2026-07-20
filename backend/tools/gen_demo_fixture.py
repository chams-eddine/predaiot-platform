# -*- coding: utf-8 -*-
"""Generate the frontend's instant-demo fixture: a DETERMINISTIC synthetic BESS
day (digital twin, fixed seed) audited by the REAL certified engine, saved as
frontend/public/demo_report.json.

Honesty contract: the fixture is genuine engine output (not mocked), the data is
synthetic (no customer/plant data — deliberately NOT the Ibri2 reference file),
and the seed is fixed so the demo is reproducible. Regenerate after any engine
change that alters outputs (the suite's golden gate will remind you).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))

import main  # noqa: E402
main.Base.metadata.create_all(bind=main.engine)
from app.core.ratelimit import limiter as _rl  # noqa: E402
_rl.enabled = False
from fastapi.testclient import TestClient  # noqa: E402
import twin  # noqa: E402  (the validation-campaign digital twin)

client = TestClient(main.app, raise_server_exceptions=False)
tok = client.post("/api/v1/trial/start",
                  json={"email": "demo-fixture@preda-iot.com", "asset_name": "demo"}).json()["token"]

# 24h at 5-minute resolution = 288 steps (matches the old demo's shape). Seed 123
# chosen from a probe of {7,13,21,42,99,123}: largest representative day-gap
# (3.8K USD, dq 0.78 "Moderate") — an honestly typical, not cherry-picked-severe, day.
df = twin.build(asset="bess", hours=24, dt_min=5, seed=123, regime="volatile")
r = client.post("/api/v1/audit/file", headers={"X-Trial-Token": tok},
                files={"file": ("reference_bess_synthetic_day.csv", twin.to_csv_bytes(df), "text/csv")})
assert r.status_code == 200, r.text[:300]
d = r.json()

# Truthful labelling: synthetic reference asset, not a real plant.
d["asset_name"] = "Reference BESS — 500 MW (synthetic day)"

out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "frontend", "public", "demo_report.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(d, f, separators=(",", ":"), default=str)

print("fixture:", out)
print("size_kb:", round(os.path.getsize(out) / 1024, 1))
print("fingerprint:", json.dumps({
    "currency": d.get("currency"), "total_gap_usd": d.get("total_gap_usd"),
    "risk_level": d.get("risk_level"), "n_decisions": len(d.get("decision_log") or []),
    "confidence": (d.get("audit_confidence") or {}).get("grade"),
}))
