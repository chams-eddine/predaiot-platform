# -*- coding: utf-8 -*-
"""Pytest fixtures for the PREDAIOT characterization suite.

These tests pin the OBSERVABLE BEHAVIOUR of the frozen audit engine so the
modularization refactor can be proven behaviour-preserving. They run the app
in-process via Starlette's TestClient — no network, no external files.
"""
import math
import os
import sys

import pytest

# Import the app the same way uvicorn does (entrypoint: main:app), from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main.limiter.enabled = False  # deterministic; we hammer endpoints on purpose


@pytest.fixture(scope="session")
def client():
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def token(client):
    def _mint():
        import time
        r = client.post("/api/v1/trial/start",
                        json={"email": f"ci-{time.time_ns()}@preda-iot.com", "asset_name": "ci"})
        return {"X-Trial-Token": r.json()["token"]}
    return _mint


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def audit_invariants(d):
    """The economic laws every successful audit must satisfy. Returns []
    when clean, else a list of violation codes."""
    v = []
    dq = d.get("dq_score")
    if not (finite(dq) and 0.0 <= dq <= 1.0):
        v.append("dq_range")
    opt, act, gap = d.get("edv_optimal_total"), d.get("edv_actual_total"), d.get("total_gap_usd")
    if not (finite(opt) and finite(act) and finite(gap)):
        v.append("money_finite")
    else:
        if abs((opt - act) - gap) > max(0.05, abs(gap) * 0.002):
            v.append("gap_identity")
        ledger = sum((s.get("gap_step") or 0) for s in (d.get("decision_log") or []))
        if abs(ledger - gap) > max(0.5, abs(gap) * 0.01):
            v.append("ledger_reconcile")
    tot = 0.0
    for rc in (d.get("root_causes") or []):
        p = rc.get("contribution_pct")
        if p is None or not finite(p) or p < -0.5 or p > 100.5:
            v.append("rootcause_pct_range"); break
        tot += p
    if tot > 101.0:
        v.append("rootcause_pct_sum")
    m = d.get("eda_metrics") or {}
    ede, elr = m.get("economic_decision_efficiency"), m.get("economic_leakage_ratio")
    if finite(ede) and finite(elr) and abs((ede + elr) - 100) > 1.0:
        v.append("ede_elr_complement")
    if d.get("risk_level") not in (None, "Low", "Moderate", "Severe"):
        v.append("risk_enum")
    return v
