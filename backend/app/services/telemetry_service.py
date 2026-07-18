# -*- coding: utf-8 -*-
"""Real-time decision core — shared by the WebSocket + REST live monitor.
Given one live telemetry frame it returns an economic assessment +
recommendation (PREDAIOT is an advisory OBSERVER; it never issues dispatch
commands). Extracted VERBATIM (refactor step 3, service 4). ECONOMIC ENGINE
FROZEN. Depends only on the economic leaf + stdlib — never api/routers/audit.
"""
from typing import Any, Dict  # noqa: F401

from app.services.optimization_service import _classify_decision  # noqa: F401


def _live_decision_core(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core real-time economic decision evaluation.

    PREDAIOT operates as an Economic Advisory Observer (Integration Level 1–2):
    it reads operational + market data and returns an economic assessment and
    recommendation. It does NOT issue dispatch commands directly to the asset.

    Accepted payload (richer PREDAIOT live schema):
      {
        "timestamp": "2026-07-05T14:05:00Z",
        "asset_id": "Ibri2_BESS",
        "market_price": 85.5,        // falls back to "price" if absent
        "actual_charge": 0,
        "actual_discharge": 20,
        "soc": 0.70,
        "p_max": 50,
        "e_max": 200,
        "eta_charge": 0.95,
        "eta_discharge": 0.95,
        "deg_cost": 5,
        "curtailment": 12,           // MW currently being curtailed/spilled
        "forecast_price": 97,        // next-window forecast price
        "forecast_pv": 180,          // optional forecast generation (solar/wind)
        "grid_limit": 50             // export/interconnection cap
      }
    """
    price       = float(data.get("market_price", data.get("price", 0)))
    actual_dis  = float(data.get("actual_discharge", 0))
    actual_chg  = float(data.get("actual_charge", 0))
    soc         = float(data.get("soc", 0.5))
    p_max       = float(data.get("p_max", 50))
    eta_chg     = float(data.get("eta_charge", data.get("eta_ch", 0.95)))
    deg_cost    = float(data.get("deg_cost", 5))
    curtailment = float(data.get("curtailment", data.get("curtailment_mw", 0)))
    forecast_price = data.get("forecast_price")
    grid_limit  = float(data.get("grid_limit", p_max))
    eff_p_max   = max(0.0, min(p_max, grid_limit))

    can_discharge = soc > 0.2
    can_charge    = soc < 0.9
    discharge_thr = deg_cost * 2.0
    charge_thr    = deg_cost * 0.5

    optimal_discharge, optimal_charge = 0.0, 0.0
    action, action_detail = "HOLD", "No Economic Trigger"

    # Curtailment recovery takes priority — always rational to absorb otherwise-wasted energy
    if curtailment > 0 and can_charge:
        optimal_charge = min(eff_p_max, curtailment)
        action, action_detail = "CHARGE", "Curtailment Recovery"
    elif price > discharge_thr and can_discharge:
        optimal_discharge = eff_p_max
        action, action_detail = "DISCHARGE", "Market Arbitrage"
    elif price < charge_thr and can_charge:
        optimal_charge = eff_p_max
        action, action_detail = "CHARGE", "Off-Peak Charging"

    forecast_note = None
    if forecast_price is not None:
        try:
            fp = float(forecast_price)
            if action == "DISCHARGE" and fp > price * 1.15 and soc > 0.5:
                forecast_note = f"Forecast price ${fp:.2f}/MWh exceeds current by >15% — consider partial hold for higher-value window."
            elif fp < price * 0.85 and action != "DISCHARGE":
                forecast_note = f"Forecast price declining to ${fp:.2f}/MWh — current window is comparatively favourable."
        except (TypeError, ValueError):
            pass

    def _value(dis_mw: float, chg_mw: float) -> float:
        v = max(0.0, (price - deg_cost) * dis_mw)
        if chg_mw > 0:
            recovered = min(chg_mw, curtailment)          # curtailed energy — effectively free
            from_grid = max(0.0, chg_mw - curtailment)     # genuine grid purchase
            v += price * recovered * eta_chg               # value of energy rescued from curtailment
            v -= price * from_grid / max(eta_chg, 0.01)    # cost of charging from the grid
        return v

    optimal_value  = _value(optimal_discharge, optimal_charge)
    captured_value = _value(actual_dis, actual_chg)
    economic_gap   = optimal_value - captured_value

    # Same Ch 4.2 domain rules as the offline DQ. The former formula allowed
    # 150% and, in the no-opportunity branch, subtracted MONEY from a PERCENT
    # (100 − |gap|) — scientifically incorrect; corrected here.
    if optimal_value > 0.01:
        decision_quality = max(0.0, min(100.0, (captured_value / optimal_value) * 100))
    elif abs(captured_value) < 0.01:
        decision_quality = 100.0
    else:
        decision_quality = 0.0

    dec_type, conf = _classify_decision(
        optimal_discharge if optimal_discharge > 0 else optimal_charge,
        actual_dis if optimal_discharge > 0 else actual_chg,
        price,
    )

    # Derived, dimensionless step severity: the gap as a share of this step's
    # own optimal value. The former HIGH/MEDIUM/LOW bands used fabricated
    # absolute money thresholds ($100/$20) — currency-blind and arbitrary
    # (docs/REMOVED_HEURISTICS.md).
    gap_pct_of_optimal = round(economic_gap / optimal_value * 100, 1) if optimal_value > 0.01 else 0.0
    rec_power = optimal_discharge if action == "DISCHARGE" else optimal_charge

    recommendation_text = (
        f"{action} {rec_power:.0f} MW — {action_detail}. "
        f"Expected gain {economic_gap:.0f} per hour (market-price units)."
        if economic_gap > 10 else "✓ Current dispatch near-optimal — no action required."
    )
    if forecast_note:
        recommendation_text += f" Note: {forecast_note}"

    return {
        "timestamp":          data.get("timestamp"),
        "asset_id":           data.get("asset_id"),
        "price":              price,
        "optimal_action":     round(optimal_discharge if optimal_discharge > 0 else -optimal_charge, 2),
        "actual_action":      round(actual_dis - actual_chg, 2),
        "optimal_value":      round(optimal_value, 2),
        "captured_value":     round(captured_value, 2),
        "economic_gap":       round(economic_gap, 2),
        "gap_step":           round(economic_gap, 2),   # back-compat alias
        "decision_quality":   round(decision_quality, 1),
        "decision_type":      dec_type,
        # confidence WITHDRAWN (fabricated per-class constants); key kept None
        "confidence":         None,
        # severity replaced by a derived ratio; "alert" = the documented
        # display policy "gap exceeds half of this step's optimal value"
        "gap_pct_of_optimal": gap_pct_of_optimal,
        "severity":           None,
        "alert":              bool(optimal_value > 0.01 and economic_gap > 0.5 * optimal_value),
        "recommended_action": action,
        "recommended_power":  round(rec_power, 2),
        "expected_gain":      round(economic_gap, 2),
        "recommendation":     recommendation_text,
        "advisory_level":     "Level 2 — Advisory (Read-Only Observer)",
        "integration_note":   "PREDAIOT does not control the asset. Output is a recommendation for operator or EMS action.",
    }
