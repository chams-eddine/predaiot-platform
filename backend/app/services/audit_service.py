# -*- coding: utf-8 -*-
"""Audit orchestration service — the central calculation engine.

process_calculation composes the audit pipeline for an ALREADY-PARSED time series:
optimization (MILP dispatch) -> per-step EDV/gap loop -> Ch 8.2 gap attribution ->
economic findings (domain.economics) -> AuditResponse assembly. Pure calc
orchestrator: no auth/tenant coupling (the route caches under the trial token), no
file parsing (ingestion runs upstream in the route).

Purpose        : orchestrate optimization + economics into an AuditResponse.
Public API     : process_calculation(asset, time_series_list, save_to_db, dt_hours,
                 currency).
Dependencies   : app.services.optimization_service (run_optimizer_full,
                 _run_optimizer_storage, _dispatch_mode, _classify_decision - economic
                 leaf, domain-by-intent); app.domain.economics (findings builders);
                 app.utils.formatting._fmt_money; app.schemas (AssetSpecs,
                 DecisionRecord, FinancialLeakage, AuditResponse); app.models.
                 DecisionAuditLog (ORM); app.core.config.SessionLocal.
Dependency dir : api -> SERVICES(this) -> {domain, utils, core, models, schemas}. All
                 downward or domain-tier (arch_graph 0/0). Structural extraction; the
                 inline DB write stays for now (-> repositories layer; debt D5).
Used by        : main.py routes (audit / live / twin) via import-back.
"""
from datetime import datetime  # noqa: F401

from app.core.config import SessionLocal  # noqa: F401
from app.models import DecisionAuditLog  # noqa: F401
from app.schemas import (  # noqa: F401
    AssetSpecs, DecisionRecord, FinancialLeakage, AuditResponse,
)
from app.utils.formatting import _fmt_money  # noqa: F401
from app.services.optimization_service import (  # noqa: F401
    run_optimizer_full, _run_optimizer_storage, _dispatch_mode, _classify_decision,
)
from app.domain.economics import (  # noqa: F401
    _build_eda_metrics, _build_root_causes, _build_opportunities,
    _build_heat_map, _build_ai_commentary, _risk_level,
)


def process_calculation(asset: AssetSpecs, time_series_list: list, save_to_db: bool = True,
                        dt_hours: float = 1.0, currency: str = "USD"):
    """
    Runs the MILP + EDV + EDA pipeline. Does NOT touch the per-token cache —
    the endpoint handler is responsible for caching the result under its
    trial token. Keeping the tenant-scoping outside this function preserves
    it as a pure calc engine (no auth coupling).

    dt_hours = duration of one time step. All monetary EDV terms are
    price × MW × dt (money = energy × price, not power × price), and the
    storage MILP's SoC balance uses the same dt. Default 1.0 keeps every
    pre-existing hourly audit byte-identical.
    """
    dt_hours = float(dt_hours) if dt_hours and dt_hours > 0 else 1.0
    optimal_actions, optimal_charges = run_optimizer_full(asset, time_series_list, dt_hours=dt_hours)
    total_edv_opt, total_edv_act = 0.0, 0.0
    decision_log = []
    db = SessionLocal() if save_to_db else None

    # Dispatch-mode-dependent EDV computation. For generation modes (storage,
    # intermittent, dispatchable) EDV = (price − marginal_cost) × dispatch —
    # positive = value captured, negative = uneconomic dispatch. For LOAD mode
    # the asset consumes, so EDV = (peak_price − price) × consumption —
    # positive = "savings vs the worst-price hour of the day." Same-signed,
    # comparable, and the gap arithmetic downstream (edv_opt − edv_act) still
    # reads as "recoverable value."
    mode = _dispatch_mode(asset.asset_type)
    is_load = (mode == "load")
    is_storage = (mode == "storage")
    peak_price = max((float(ts.get("price", 0) or 0) for ts in time_series_list), default=0.0)

    try:
        for i, ts in enumerate(time_series_list):
            opt_dis  = optimal_actions.get(i, 0.0)
            opt_ch   = optimal_charges.get(i, 0.0)
            # Load-class inputs may put consumption in actual_charge; other
            # modes use actual_discharge. Fall back if the caller only filled one.
            if is_load:
                act_dis = float(ts.get("actual_charge", 0) or 0) or float(ts.get("actual_discharge", 0) or 0)
            else:
                act_dis = float(ts.get("actual_discharge", 0) or 0)
            price    = float(ts.get("price", 0))
            curtail  = float(ts.get("curtailment_mw", 0))
            override = bool(ts.get("operator_override", False))
            fc_price = ts.get("forecast_price", None)
            soc_val  = ts.get("soc", None)
            demand   = ts.get("grid_demand", None)

            if is_load:
                edv_opt_step = (peak_price - price) * opt_dis * dt_hours
                edv_act_step = (peak_price - price) * act_dis * dt_hours
            elif is_storage:
                # Reference Manual Vol II Ch 3: J = [P·P_dis − P·P_ch]·Δt − C_deg.
                # Charging is paid for at the market price — omitting it (the
                # old formula) reported gross discharge margin, overstating the
                # optimal by the whole charge bill (observed: 536 vs ~209 OMR
                # on the Ibri2 reference file).
                act_ch = float(ts.get("actual_charge", 0) or 0)
                edv_opt_step = ((price - asset.deg_cost) * opt_dis - price * opt_ch) * dt_hours
                edv_act_step = ((price - asset.deg_cost) * act_dis - price * act_ch) * dt_hours
            else:
                edv_opt_step = ((price * opt_dis) - (asset.deg_cost * opt_dis)) * dt_hours
                edv_act_step = ((price * act_dis) - (asset.deg_cost * act_dis)) * dt_hours
            gap_step     = edv_opt_step - edv_act_step
            total_edv_opt += edv_opt_step
            total_edv_act += edv_act_step

            dec_type, confidence = _classify_decision(opt_dis, act_dis, price)

            if db:
                db.add(DecisionAuditLog(
                    asset_id=asset.asset_id,
                    timestamp=datetime.utcnow(),
                    market_price=price,
                    optimal_action=opt_dis,
                    actual_action=act_dis,
                    economic_gap=gap_step
                ))

            decision_log.append(DecisionRecord(
                hour=ts.get("hour", i),
                price=price,
                optimal_action=round(opt_dis, 2),
                actual_action=round(act_dis, 2),
                edv_optimal_step=round(edv_opt_step, 2),
                edv_actual_step=round(edv_act_step, 2),
                gap_step=round(gap_step, 2),
                decision_type=dec_type,
                confidence=confidence,
                operator_override=override,
                curtailment_mw=curtail,
                soc=soc_val,
                grid_demand=demand,
                forecast_price=fc_price
            ))
        if db:
            db.commit()
    finally:
        if db:
            db.close()

    # DQ Score per Reference Manual Ch. 4.2: when no arbitrage opportunity
    # existed (EDV_opt ≈ 0) and the operator correctly captured none
    # (EDV_act ≈ 0), nothing was missed — DQ is 1.0, not 0. Falling through
    # to 0 here was scoring flat-price periods as "Severe risk".
    _EDV_EPS = 1e-9
    if total_edv_opt > _EDV_EPS:
        dq_score = total_edv_act / total_edv_opt
    elif abs(total_edv_act) <= _EDV_EPS:
        dq_score = 1.0
    else:
        dq_score = 0.0
    # DQ is a ratio against a modeled UPPER BOUND, so raw > 1.0 means the
    # model disagrees with reality — wrong column mapping, wrong asset specs,
    # or actual dispatch exceeding p_max. Clamp for display (Ch. 4.2 defines
    # DQ ∈ [0,1]) but keep the raw value so ingestion can flag the mismatch
    # instead of silently reporting a perfect score.
    dq_score_raw = dq_score
    dq_score = max(0.0, min(1.0, dq_score))
    total_gap = total_edv_opt - total_edv_act

    # ── Gap Attribution per Reference Manual Ch 8.2 ─────────────────────
    # G_total = G_forecast + G_execution. d_rec = what the MILP recommends
    # using the FORECAST prices; evaluating d_rec under realized prices
    # telescopes the gap exactly:
    #   G_forecast  = J(d*|P_act) − J(d_rec|P_act)  (forecast imperfection)
    #   G_execution = J(d_rec|P_act) − J(d_act|P_act) (not following the rec)
    # Storage-only (the MILP mode) and only when a forecast column exists.
    gap_attribution = None
    if is_storage and time_series_list:
        fc_raw = [ts.get("forecast_price") for ts in time_series_list]
        n_ok = sum(1 for f in fc_raw if f is not None and f == f)
        if n_ok >= 0.9 * len(time_series_list):
            try:
                fc_prices = [float(f) if (f is not None and f == f) else 0.0 for f in fc_raw]
                rec_dis, rec_ch = _run_optimizer_storage(asset, fc_prices, dt_hours=dt_hours,
                                                         return_charge=True)
                j_rec_actual = sum(
                    ((float(ts.get("price", 0)) - asset.deg_cost) * rec_dis.get(i, 0.0)
                     - float(ts.get("price", 0)) * rec_ch.get(i, 0.0)) * dt_hours
                    for i, ts in enumerate(time_series_list)
                )
                gap_attribution = {
                    "forecast_gap":  round(total_edv_opt - j_rec_actual, 2),
                    "execution_gap": round(j_rec_actual - total_edv_act, 2),
                    "recommended_value": round(j_rec_actual, 2),
                    "method": ("Ch 8.2 telescoping split under realized prices: "
                               "G = [J(d*|P) - J(d_rec|P)] + [J(d_rec|P) - J(d_act|P)]"),
                }
            except Exception:
                gap_attribution = None  # attribution is enrichment, never fatal

    # Build EDA intelligence layers. Annualisation uses the span actually
    # audited (8760 / span_hours) — for a 24h hourly file this is exactly the
    # legacy ×365, for a 5-minute SCADA day it stops over-scaling 12×.
    span_hours_eda = len(time_series_list) * dt_hours
    annual_factor = (8760.0 / span_hours_eda) if span_hours_eda > 0 else 365.0
    eda_metrics  = _build_eda_metrics(decision_log, total_edv_opt, total_edv_act, asset.asset_type,
                                      dt_hours=dt_hours)
    root_causes  = _build_root_causes(decision_log, total_gap, total_edv_opt)
    opportunities = _build_opportunities(total_gap, asset.asset_type, decision_log,
                                         annual_factor=annual_factor, currency=currency)
    heat_map     = _build_heat_map(decision_log)
    ai_commentary = _build_ai_commentary(
        asset.asset_name, total_gap, total_edv_opt, decision_log, dq_score,
        eda_metrics=eda_metrics, opportunities=opportunities, root_causes=root_causes,
        annual_factor=annual_factor, currency=currency, gap_attribution=gap_attribution,
    )
    if gap_attribution:
        ai_commentary += (
            "\n\nGAP ATTRIBUTION (Ref. Manual Ch 8.2)\n"
            f"Theoretical Ceiling Gap    {_fmt_money(total_gap, currency)}"
            "  — vs the perfect-foresight upper-bound benchmark.\n"
            f"  Forecast-Unreachable     {_fmt_money(gap_attribution['forecast_gap'], currency)}"
            "  — capturable only with perfect price foresight (not operator-attributable).\n"
            f"  Recoverable Execution    {_fmt_money(gap_attribution['execution_gap'], currency)}"
            "  — achievable with information available at decision time "
            "(operator / automation attributable)."
        )

    top_sources = []
    for rc in root_causes[:5]:
        top_sources.append({"name": rc.category, "usd": rc.loss_usd, "pct": rc.contribution_pct})

    # Annualise from the actual span covered, not "×365 days" — a 5-minute
    # file covering 24h and an hourly file covering 48h both scale correctly.
    span_hours = span_hours_eda
    projection_12m = total_gap * annual_factor if span_hours > 0 else 0.0
    financial_leakage = FinancialLeakage(
        period_24h=round(total_gap, 2),
        projection_12m=round(projection_12m, 2),
        top_sources=top_sources
    )

    result = AuditResponse(
        # UNCHANGED core fields
        edv_optimal_total=round(total_edv_opt, 2),
        edv_actual_total=round(total_edv_act, 2),
        dq_score=round(dq_score, 4),
        dq_score_raw=round(dq_score_raw, 4),
        gap_attribution=gap_attribution,
        total_gap_usd=round(total_gap, 2),
        # Presentation hierarchy: same verified numbers under honest names.
        theoretical_ceiling_gap=round(total_gap, 2),
        recoverable_execution_gap=(round(gap_attribution["execution_gap"], 2)
                                   if gap_attribution else None),
        headline_gap_basis=("execution" if gap_attribution else "ceiling"),
        decision_log=decision_log,
        # Extended EDA
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        audit_period_label=f"{len(time_series_list)} Steps ({span_hours:g}h)",
        risk_level=_risk_level(dq_score),
        eda_metrics=eda_metrics,
        root_causes=root_causes,
        opportunities=opportunities,
        heat_map=heat_map,
        financial_leakage=financial_leakage,
        ai_commentary=ai_commentary,
        currency=(currency or "USD").upper(),
        counterfactual_summary=(
            f"Against the Theoretical Economic Ceiling (perfect-foresight upper-bound "
            f"benchmark), {asset.asset_name} could have captured {_fmt_money(total_edv_opt, currency)} "
            f"vs actual {_fmt_money(total_edv_act, currency)} — a ceiling gap of "
            f"{_fmt_money(total_gap, currency)}. "
            + (
                f"Of this, the Recoverable Execution Gap — value achievable using information "
                f"available at decision time — is {_fmt_money(gap_attribution['execution_gap'], currency)}; "
                f"the remaining {_fmt_money(gap_attribution['forecast_gap'], currency)} was reachable "
                f"only with perfect price foresight."
                if gap_attribution else
                "The ceiling gap is an upper bound: it includes value reachable only with perfect "
                "price foresight. A day-ahead forecast column is required to isolate the "
                "operationally recoverable portion."
            )
        ),
        # Echo ISSUED TO fields from AssetSpecs
        asset_id=asset.asset_id,
        asset_location=asset.location,
        client_name=asset.client_name,
        client_company=asset.client_company,
    )
    return result
