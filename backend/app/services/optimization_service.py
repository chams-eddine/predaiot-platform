# -*- coding: utf-8 -*-
"""Dispatch optimizers — the perfect-foresight economic CEILING per asset
class (storage MILP, intermittent curtailment, dispatchable merit-order,
load greedy-fill). Extracted VERBATIM from main.py (refactor step 3, svc 1).
ECONOMIC ENGINE FROZEN: the optimization math is byte-for-byte identical.

Public API: run_optimizer, run_optimizer_full, _run_optimizer_storage,
_dispatch_mode, _MILP_LAST (last-solve telemetry, read by ingestion).
"""
from typing import List, Optional  # noqa: F401

import pulp

from app.schemas import AssetSpecs  # noqa: F401


_INTERMITTENT_TYPES = {"solar", "pv", "wind", "tidal", "wave"}
_DISPATCHABLE_TYPES = {"gas", "oilgas", "coal", "thermal", "chp", "nuclear", "geothermal", "hydro"}
_LOAD_TYPES         = {"hydrogen", "electrolyzer", "desalination", "desal"}


def _dispatch_mode(asset_type: Optional[str]) -> str:
    t = (asset_type or "").strip().lower()
    if t in _INTERMITTENT_TYPES: return "intermittent"
    if t in _DISPATCHABLE_TYPES: return "dispatchable"
    if t in _LOAD_TYPES:         return "load"
    # Hybrid labels from real SCADA exports: "Solar+BESS", "Wind + Storage",
    # "PV/Battery". The storage component is the one making dispatch decisions,
    # so storage keywords win over generation keywords.
    if any(k in t for k in ("bess", "battery", "storage")):
        return "storage"
    if any(k in t for k in ("solar", "pv", "wind", "tidal", "wave")):
        return "intermittent"
    if any(k in t for k in ("gas", "coal", "thermal", "nuclear", "geothermal", "chp")):
        return "dispatchable"
    if any(k in t for k in ("hydrogen", "electrolyzer", "desal")):
        return "load"
    return "storage"  # default + explicit storage types


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


def _run_optimizer_intermittent(asset: AssetSpecs, time_series_list: list) -> dict:
    """
    Solar / Wind / Tidal: generation is exogenous (driven by irradiance, wind,
    tide). The only economic decision is curtailment. Available capacity at
    step t = actual_discharge + curtailment_mw (capped by p_max). The optimal
    policy exports all of it when price > 0 and curtails when price ≤ 0.

    Note: this gives a non-trivial audit ONLY when curtailment is logged. If
    `curtailment_mw` is always 0 in the input, the optimal collapses to the
    actual and DQ → 1.0 — which is the correct answer in that case.
    """
    out = {}
    for i, ts in enumerate(time_series_list):
        price = float(ts.get("price", 0))
        actual = float(ts.get("actual_discharge", 0))
        curt = float(ts.get("curtailment_mw", 0))
        available = min(asset.p_max, max(0.0, actual + curt))
        out[i] = available if price > asset.deg_cost else 0.0
    return out


def _run_optimizer_dispatchable(asset: AssetSpecs, prices: List[float]) -> dict:
    """
    Gas / Thermal / Nuclear / Geothermal / non-storage Hydro: the merit-order
    rule. Run at p_max when price exceeds marginal generation cost (`deg_cost`
    is interpreted as $/MWh marginal cost, including fuel/efficiency for gas).
    Idle otherwise. Per-step, no time coupling. (Unit-commitment ramp / min-up
    constraints are deliberately out of scope for v1; the optimal here is an
    economic upper bound, which is the correct ceiling for an audit.)
    """
    return {i: (asset.p_max if p > asset.deg_cost else 0.0) for i, p in enumerate(prices)}


def _load_consumption_series(time_series_list: list) -> List[float]:
    """
    For load-class assets the consumption column is `actual_charge`. Many
    uploads only fill `actual_discharge` though, so we fall back to that if
    charge is uniformly zero — better a working audit than a strict schema
    error at ingest.
    """
    charge = [float(ts.get("actual_charge", 0) or 0) for ts in time_series_list]
    if sum(charge) > 0:
        return charge
    return [float(ts.get("actual_discharge", 0) or 0) for ts in time_series_list]


def _run_optimizer_load(asset: AssetSpecs, time_series_list: list) -> dict:
    """
    Electrolyzer / Desalination / large flexible loads. The load has to meet a
    production target (H₂ tonnes/day, m³/day of water, etc.) — the decision is
    WHEN to consume, not whether to. The audit takes the observed total energy
    consumed as the target and asks: could the same total have been met at a
    lower electricity cost?

    Optimal policy: greedily allocate p_max to the cheapest steps until the
    observed total consumption is met. Any remainder goes into the next-cheapest
    step at a partial rate. No time coupling (no product-storage constraint) —
    this is the merit-order equivalent for loads.
    """
    prices = [float(ts.get("price", 0) or 0) for ts in time_series_list]
    consumption = _load_consumption_series(time_series_list)
    total_needed = sum(consumption)
    n = len(prices)
    optimal = {i: 0.0 for i in range(n)}
    if total_needed <= 0 or n == 0:
        return optimal

    # Ascending-price greedy fill: cheapest hour first, run at p_max until the
    # daily energy target is met, then partial-fill the boundary step.
    order = sorted(range(n), key=lambda i: prices[i])
    remaining = total_needed
    for i in order:
        if remaining <= 0:
            break
        take = min(asset.p_max, remaining)
        optimal[i] = take
        remaining -= take
    return optimal


def run_optimizer(asset: AssetSpecs, time_series_list: list, dt_hours: float = 1.0) -> dict:
    """
    Dispatch router. Picks the right optimizer for the asset class and returns
    `{step_index: optimal_dispatch_mw}`. Defaults to the storage MILP so legacy
    audits (BESS, asset_type unset / 'Generic') produce identical numbers.

    dt_hours only affects the storage MILP (SoC energy balance). The
    intermittent / dispatchable / load optimizers are per-step MW policies —
    step duration cancels out of their dispatch decision, and the money side
    is handled centrally in process_calculation's EDV × dt.
    """
    mode = _dispatch_mode(asset.asset_type)
    if mode == "intermittent":
        return _run_optimizer_intermittent(asset, time_series_list)
    if mode == "load":
        return _run_optimizer_load(asset, time_series_list)
    prices = [float(ts.get("price", 0)) for ts in time_series_list]
    if mode == "dispatchable":
        return _run_optimizer_dispatchable(asset, prices)
    return _run_optimizer_storage(asset, prices, dt_hours=dt_hours)


def run_optimizer_full(asset: AssetSpecs, time_series_list: list, dt_hours: float = 1.0) -> tuple:
    """
    Like run_optimizer but also returns the optimal CHARGE schedule (empty for
    non-storage modes, which have no charging concept). The EDV ledger needs
    both sides: per Reference Manual Vol II Ch 3 the storage objective is
    J = [P·P_dis − P·P_ch]·Δt − C_deg — charging cost is real money.
    """
    mode = _dispatch_mode(asset.asset_type)
    if mode == "storage":
        prices = [float(ts.get("price", 0)) for ts in time_series_list]
        dis, ch = _run_optimizer_storage(asset, prices, dt_hours=dt_hours, return_charge=True)
        return dis, ch
    return run_optimizer(asset, time_series_list, dt_hours=dt_hours), {}
