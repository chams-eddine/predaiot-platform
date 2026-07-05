# -*- coding: utf-8 -*-
"""
PREDAIOT MILP microservice.

Wraps `_run_optimizer_storage` — copied VERBATIM from `backend/main.py`
(lines 640-686 at commit fb5e692) — behind a minimal FastAPI surface so the
Node.js core (node-core/) can call the exact production optimizer over HTTP
without any equation being rewritten from memory.

Endpoints:
    GET  /health    -> {"ok": true}
    POST /optimize  -> { status, optimal_discharge, optimal_charge }

Run:  uvicorn main:app --port 8001        (from milp-service/)
"""
from typing import Dict, List, Optional

import pulp
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PREDAIOT MILP Service", version="1.0.0")


class AssetSpecs(BaseModel):
    # Same field names and defaults as backend/main.py AssetSpecs — only the
    # attributes _run_optimizer_storage actually reads.
    p_max:    float = 50.0
    e_max:    float = 100.0
    soc_init: float = 0.2
    eta_ch:   float = 0.95
    eta_dis:  float = 0.95
    deg_cost: float = 5.0


class OptimizeRequest(BaseModel):
    asset: AssetSpecs = AssetSpecs()
    prices: List[float]
    dt_hours: float = 1.0


class OptimizeResponse(BaseModel):
    status: str
    steps: int
    optimal_discharge: Dict[int, float]
    optimal_charge: Dict[int, float]


# ═════════════════════════════════════════════════════════════════════════
# BEGIN VERBATIM COPY from backend/main.py (do not edit — re-copy from the
# source file if the production optimizer ever changes)
# ═════════════════════════════════════════════════════════════════════════

# Last MILP solve telemetry — read by ingestion to disclose time-limited
# (incumbent, not proven-optimal) solves on very large files.
_MILP_LAST = {"status": "Optimal", "steps": 0}


def _run_optimizer_storage(asset: AssetSpecs, prices: List[float], dt_hours: float = 1.0,
                           return_charge: bool = False):
    """
    BESS MILP. dt_hours is the step duration: SoC moves by P × dt / E_max per
    step, so a 5-minute SCADA feed (dt=1/12) no longer lets the model shift
    12× the physically possible energy per step. dt=1.0 reproduces the v1
    reference audit exactly.

    return_charge=True also returns the optimal charge schedule — needed by
    the EDV accounting (Reference Manual Vol II Ch 3: J subtracts the charge
    purchase cost) and by the Ch 8.2 gap-attribution second solve.
    """
    if not prices:
        return ({}, {}) if return_charge else {}
    hours = range(len(prices))
    prob = pulp.LpProblem("PREDAIOT_MILP", pulp.LpMaximize)
    p_dis = pulp.LpVariable.dicts("Discharge", hours, lowBound=0, upBound=asset.p_max)
    p_ch  = pulp.LpVariable.dicts("Charge",    hours, lowBound=0, upBound=asset.p_max)
    soc   = pulp.LpVariable.dicts("SOC",        hours, lowBound=0.1, upBound=0.95)
    is_dis = pulp.LpVariable.dicts("IsDis",     hours, cat='Binary')

    prob += pulp.lpSum([
        (prices[t] * p_dis[t]) - (prices[t] * p_ch[t]) - (asset.deg_cost * p_dis[t])
        for t in hours
    ])
    for t in hours:
        prob += p_dis[t] <= asset.p_max * is_dis[t]
        prob += p_ch[t]  <= asset.p_max * (1 - is_dis[t])
        step_delta = (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) * dt_hours / asset.e_max
        if t == 0:
            prob += soc[t] == asset.soc_init + step_delta
        else:
            prob += soc[t] == soc[t-1] + step_delta
        if t == max(hours):
            prob += soc[t] == asset.soc_init
    # Hard wall-clock cap: a multi-day 5-minute file means thousands of
    # binaries — CBC keeps the best incumbent when the limit hits, and the
    # status below lets ingestion disclose "optimum is a lower bound".
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=45))
    _MILP_LAST["status"] = pulp.LpStatus.get(prob.status, "Unknown")
    _MILP_LAST["steps"] = len(prices)
    dis = {t: (p_dis[t].varValue or 0.0) for t in hours}
    ch  = {t: (p_ch[t].varValue or 0.0) for t in hours}
    return (dis, ch) if return_charge else dis

# ═════════════════════════════════════════════════════════════════════════
# END VERBATIM COPY
# ═════════════════════════════════════════════════════════════════════════


@app.get("/health")
def health():
    return {"ok": True, "service": "milp-service", "last_solve": _MILP_LAST}


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest):
    dis, ch = _run_optimizer_storage(req.asset, req.prices, dt_hours=req.dt_hours,
                                     return_charge=True)
    return OptimizeResponse(
        status=_MILP_LAST["status"],
        steps=len(req.prices),
        optimal_discharge=dis,
        optimal_charge=ch,
    )
