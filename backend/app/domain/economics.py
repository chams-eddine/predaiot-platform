# -*- coding: utf-8 -*-
"""Economic-narrative domain — the audit's economic findings builders: root-cause
attribution (exact partition), the evidence-derived opportunity/action plan,
severity heat-map, EDA metrics, the Economic Intelligence Report(TM) narrative, and
the DQ risk-band. Extracted VERBATIM from main.py (refactor step 3, service 5
part 2); this is the FIRST domain-layer module.

Purpose        : single home for the economic *findings* logic under the
                 No-Fabrication rule (every number reproduces from ledger rows;
                 see docs/REMOVED_HEURISTICS.md).
Public API     : _build_root_causes, _build_opportunities, _build_heat_map,
                 _build_eda_metrics, _build_ai_commentary, _risk_level.
Private        : _root_cause_bucket + wording catalogs _BUCKET_ACTIONS,
                 _ADVISORY_IDEAS, _EXPERIMENTAL_NOTE.
Dependencies   : app.schemas (models, rank 0); app.utils.formatting._fmt_money
                 (utils, rank 1); app.services.optimization_service._dispatch_mode
                 (economic leaf, domain-by-intent - debt D2). NO api / no service
                 orchestration / NO persistence / NO I/O.
Dependency dir : api -> services -> DOMAIN(this) -> {schemas, utils}. Structural
                 domain only - no entities/value objects/aggregates yet (P6).
Used by        : main.process_calculation (import-back).
"""
from typing import List  # noqa: F401

from app.schemas import (  # noqa: F401
    DecisionRecord, RootCauseItem, OpportunityItem, HeatMapCell, EDAMetrics,
)
from app.utils.formatting import _fmt_money  # noqa: F401
from app.services.optimization_service import _dispatch_mode  # noqa: F401


def _root_cause_bucket(decision_type: str) -> str:
    """Mutually exclusive mapping from step classification to gap category —
    every positive gap_step is attributed to EXACTLY ONE category, so the
    category losses partition Σ positive gap exactly (no double counting)."""
    dt = decision_type or ""
    if "Missed Arbitrage" in dt:
        return "Missed Arbitrage"
    if "Partial" in dt:
        return "Partial Capture"
    if "Over" in dt:
        return "Over-Dispatch"
    return "Schedule-based Dispatch"


def _build_root_causes(
    decision_log: List[DecisionRecord],
    total_gap: float,
    total_edv_opt: float,
) -> List[RootCauseItem]:
    """
    Attribute the ceiling gap to categories via an EXACT PARTITION:

        loss(cat)            = Σ gap_step over rows with gap_step > 0
                               whose classification maps to cat
        contribution_pct(cat)= loss(cat) / Σ_cat loss(cat) × 100

    The percentages therefore sum to 100.0 by construction, and every figure
    reproduces from ledger rows by filtering on decision_type. The former
    "Curtailment += gap × 0.15" secondary tag was removed — the 0.15 factor
    was fabricated and double-counted gap already attributed to another
    category (docs/REMOVED_HEURISTICS.md). Curtailed energy is reported
    separately as a descriptive quantity in EDAMetrics.curtailed_energy_mwh.
    """
    cats: dict = {}
    for rec in decision_log:
        gap = rec.gap_step or 0
        if gap <= 0:
            continue
        cats[_root_cause_bucket(rec.decision_type)] = \
            cats.get(_root_cause_bucket(rec.decision_type), 0.0) + gap

    total_positive = sum(cats.values())
    result = []
    for cat, loss in cats.items():
        if loss > 0 and total_positive > 0:
            result.append(RootCauseItem(
                category=cat,
                contribution_pct=round(loss / total_positive * 100.0, 1),
                loss_usd=round(loss, 2),
            ))
    result.sort(key=lambda x: x.contribution_pct, reverse=True)
    return result

# ── Economic Action Plan under the No-Fabrication rule ──────────────────────
# QUANTIFIED items derive every number from ledger rows:
#     period_gain(cat) = sum of gap_step over rows with gap_step > 0 whose
#                        classification maps to cat (_root_cause_bucket)
#     annual_gain      = period_gain x annual_factor (linear extrapolation,
#                        labeled as such everywhere it is shown)
#     share%           = period_gain / sum of positive gap_step x 100
# Each carries a `derivation` string stating the exact filter + formula, so
# any reader can reproduce it from the exported ledger CSV.
#
# ADVISORY items (market/strategy ideas that CANNOT be quantified from the
# audited dataset) carry NO numbers and are flagged
# "Experimental - Not part of EDA Standard v1.0".
#
# The former implementation allocated fixed shares of the gap
# (0.28/0.35/0.18/0.12/0.07 ...) with invented confidence/priority/payback
# figures - removed; see docs/REMOVED_HEURISTICS.md.

_EXPERIMENTAL_NOTE = ("Experimental - Not part of EDA Standard v1.0. "
                      "Not quantifiable from the audited dataset; no value figure is given.")

# Mode-aware recommendation wording per evidence bucket. Text is advice;
# numbers always come from the ledger.
_BUCKET_ACTIONS = {
    "storage": {
        "Missed Arbitrage":        ("Dynamic dispatch trigger",
                                    "Respond to high-price windows instead of holding charge - replace static "
                                    "thresholds with a price-responsive trigger."),
        "Partial Capture":         ("Raise dispatch to the available optimum",
                                    "During priced windows the asset dispatched below the feasible optimum - "
                                    "review threshold conservatism and power-limit settings."),
        "Schedule-based Dispatch": ("Replace fixed-schedule logic",
                                    "Dispatch followed a predefined schedule rather than market signals during "
                                    "these intervals."),
        "Over-Dispatch":           ("Stop dispatch below marginal economics",
                                    "Discharge occurred when the price did not cover marginal cost."),
    },
    "intermittent": {
        "Missed Arbitrage":        ("Export available generation during priced windows",
                                    "Available power was not exported while prices exceeded marginal cost."),
        "Partial Capture":         ("Reduce unnecessary curtailment",
                                    "Output was partially curtailed while export remained economic."),
        "Schedule-based Dispatch": ("Price-responsive curtailment logic",
                                    "Curtailment decisions did not track market signals in these intervals."),
        "Over-Dispatch":           ("Negative-price curtailment discipline",
                                    "Export continued into intervals where it destroyed value."),
    },
    "dispatchable": {
        "Missed Arbitrage":        ("Merit-order compliance",
                                    "The plant idled while price exceeded marginal generation cost."),
        "Partial Capture":         ("Dispatch to full economic capacity",
                                    "Output was below the economic optimum during priced windows."),
        "Schedule-based Dispatch": ("Replace fixed-schedule logic",
                                    "Dispatch followed a schedule rather than the merit-order rule."),
        "Over-Dispatch":           ("Stop uneconomic dispatch",
                                    "Generation ran while price was below marginal cost."),
    },
    "load": {
        "Missed Arbitrage":        ("Shift consumption into cheapest windows",
                                    "Consumption was scheduled outside the day's lowest-price windows."),
        "Partial Capture":         ("Deepen load-shifting into cheap windows",
                                    "Only part of the shiftable load moved to low-price intervals."),
        "Schedule-based Dispatch": ("Price-responsive consumption scheduling",
                                    "Consumption timing ignored market prices in these intervals."),
        "Over-Dispatch":           ("Avoid consumption in peak-price windows",
                                    "Load ran during the day's most expensive intervals."),
    },
}

# Advisory catalog: strategy directions worth investigating, explicitly not
# quantified by this audit.
_ADVISORY_IDEAS = {
    "storage": [
        ("Reserve / frequency-market stacking",
         "Idle capacity may qualify for FCR / spinning-reserve products in markets that offer them."),
        ("Curtailment-absorption charging",
         "Where colocated generation is curtailed, charging against curtailed energy may add value."),
    ],
    "intermittent": [
        ("Storage colocation for time-shift",
         "A colocated BESS could move midday oversupply into evening peaks."),
        ("Ancillary-services enrolment",
         "IBR-capable inverters may qualify for voltage-support or reactive-power products."),
    ],
    "dispatchable": [
        ("Spinning-reserve enrolment",
         "Synchronised idle capacity may qualify for operating-reserve products."),
        ("Fuel-cost hedging",
         "Forward fuel contracts could stabilise the marginal-cost input of the merit-order rule."),
    ],
    "load": [
        ("Demand-response enrolment",
         "The flexible load may qualify for interruptible-load or DR programmes."),
        ("Product-storage buffer sizing",
         "A larger downstream buffer would widen the feasible load-shifting window."),
    ],
}


def _build_opportunities(total_gap: float, asset_type: str, decision_log: list = None,
                         annual_factor: float = 365.0, currency: str = "USD") -> List[OpportunityItem]:
    """Evidence-derived action plan. See the block comment above for the
    derivation rules; every number reproduces from the exported ledger."""
    log = decision_log or []
    sums, counts = {}, {}
    for d in log:
        g = d.gap_step or 0
        if g <= 0:
            continue
        b = _root_cause_bucket(d.decision_type)
        sums[b] = sums.get(b, 0.0) + g
        counts[b] = counts.get(b, 0) + 1
    total_positive = sum(sums.values())

    mode = _dispatch_mode(asset_type)
    actions = _BUCKET_ACTIONS.get(mode, _BUCKET_ACTIONS["storage"])

    ops: List[OpportunityItem] = []
    for bucket, gain in sorted(sums.items(), key=lambda kv: kv[1], reverse=True):
        name, description = actions.get(bucket, (bucket, ""))
        ops.append(OpportunityItem(
            name=name,
            description=description,
            period_gain=round(gain, 2),
            annual_gain_usd=round(gain * annual_factor, 0),
            share_of_positive_gap_pct=round(gain / total_positive * 100.0, 1) if total_positive > 0 else None,
            intervals_observed=counts[bucket],
            evidence=(f"{counts[bucket]} ledger row(s) classified '{bucket}' with positive gap; "
                      f"sum of gap_step = {_fmt_money(gain, currency)} for the audited period."),
            derivation=(f"period_gain = sum of gap_step over ledger rows where decision_type maps to "
                        f"'{bucket}' and gap_step > 0 (recorded period only; no forward projection)."),
        ))

    # Operator-override governance - derived from override-flagged rows only.
    ovr_gain = sum((d.gap_step or 0) for d in log if d.operator_override and (d.gap_step or 0) > 0)
    ovr_count = sum(1 for d in log if d.operator_override and (d.gap_step or 0) > 0)
    if ovr_count > 0:
        ops.append(OpportunityItem(
            name="Operator override governance",
            description="Manual interventions coincided with value loss - require an economic "
                        "justification record for each override.",
            period_gain=round(ovr_gain, 2),
            annual_gain_usd=round(ovr_gain * annual_factor, 0),
            share_of_positive_gap_pct=round(ovr_gain / total_positive * 100.0, 1) if total_positive > 0 else None,
            intervals_observed=ovr_count,
            evidence=(f"{ovr_count} override-flagged ledger row(s) with positive gap; "
                      f"sum of gap_step = {_fmt_money(ovr_gain, currency)}. NOTE: these rows are also "
                      "counted in their classification bucket above - this item is a cross-cut "
                      "view, not additional value."),
            derivation="period_gain = sum of gap_step over ledger rows where operator_override = True "
                       "and gap_step > 0 (cross-cut of the buckets above; do not sum with them).",
        ))

    # Advisory ideas - explicitly experimental, never quantified.
    for name, description in _ADVISORY_IDEAS.get(mode, []):
        ops.append(OpportunityItem(
            name=name,
            description=description,
            experimental=True,
            experimental_note=_EXPERIMENTAL_NOTE,
        ))
    return ops

def _build_heat_map(decision_log: List[DecisionRecord]) -> List[HeatMapCell]:
    """
    Severity banding derived from the audit's OWN gap distribution — the
    former bands (gap < price×1 / price×5) used fabricated multipliers
    (docs/REMOVED_HEURISTICS.md). Definition:
        optimal    : gap_step ≤ 0
        acceptable : 0 < gap_step ≤ P50 of this audit's positive gaps
        poor       : P50 < gap_step ≤ P90
        critical   : gap_step > P90
    Percentiles are computed from the ledger itself, so the legend is
    reproducible for any dataset.
    """
    positive = sorted((rec.gap_step or 0) for rec in decision_log if (rec.gap_step or 0) > 0)

    def _pct(p: float) -> float:
        if not positive:
            return 0.0
        k = max(0, min(len(positive) - 1, int(round(p * (len(positive) - 1)))))
        return positive[k]

    p50, p90 = _pct(0.50), _pct(0.90)

    cells = []
    for rec in decision_log:
        h = rec.hour or 0
        label = f"{h // 12:02d}:{(h % 12) * 5:02d}"
        gap = rec.gap_step or 0
        if gap <= 0:
            status = "optimal"
        elif gap <= p50:
            status = "acceptable"
        elif gap <= p90:
            status = "poor"
        else:
            status = "critical"
        cells.append(HeatMapCell(
            hour=h, label=label, status=status,
            gap_usd=round(gap, 2), price=rec.price or 0,
            action_taken=rec.decision_type or "Unknown"
        ))
    return cells

def _build_eda_metrics(
    decision_log: List[DecisionRecord],
    total_opt: float, total_act: float,
    asset_type: str,
    dt_hours: float = 1.0,
) -> EDAMetrics:
    """
    Only ledger-derivable ratios. The former EIS composite (weights
    45/30/15/10), decision_delay_index (×10 scale), revenue_stacking_index
    (2-if-fui>0.3) and battery_opportunity_capture (dispatch accuracy under a
    misleading name) were fabricated constructs and are withdrawn — the model
    keeps their keys as None for API compatibility (docs/REMOVED_HEURISTICS.md).
    """
    total = len(decision_log)
    correct = sum(1 for d in decision_log if "Correct" in (d.decision_type or ""))
    with_forecast = sum(1 for d in decision_log if d.forecast_price is not None)
    overrides = sum(1 for d in decision_log if d.operator_override)
    curtailed_mwh = sum((d.curtailment_mw or 0) for d in decision_log) * dt_hours

    # Same Ch. 4.2 rule as dq_score: no opportunity + nothing captured = full
    # efficiency (no leakage), not the literal 0/0 → 0 fallback.
    _EDV_EPS = 1e-9
    if total_opt > _EDV_EPS:
        ede = total_act / total_opt
    elif abs(total_act) <= _EDV_EPS:
        ede = 1.0
    else:
        ede = 0.0
    ede = max(0.0, min(1.0, ede))
    elr = 1 - ede
    dispatch_acc = (correct / total) if total > 0 else 0
    fui = (with_forecast / total) if total > 0 else 0

    return EDAMetrics(
        economic_decision_efficiency=round(ede * 100, 2),
        economic_leakage_ratio=round(elr * 100, 2),
        dispatch_accuracy=round(dispatch_acc * 100, 2),
        forecast_utilization_index=round(fui * 100, 2),
        override_rate_pct=round(overrides / total * 100, 2) if total > 0 else None,
        curtailed_energy_mwh=round(curtailed_mwh, 2),
    )

def _build_ai_commentary(
    asset_name: str, total_gap: float, total_opt: float,
    decision_log: List[DecisionRecord], dq: float,
    eda_metrics=None, opportunities: list = None, root_causes: list = None,
    annual_factor: float = 365.0, currency: str = "USD",
    gap_attribution: dict = None,
) -> str:
    """
    Generates the default (non-Claude) Economic Intelligence Report™.
    Structured like a McKinsey / Big-4 audit finding — used as fallback when
    /api/v1/ai-enhance is not configured, and as the base prompt context for Claude.
    """
    missed = [d for d in decision_log if d.decision_type == "Missed Arbitrage"]
    top3 = sorted(missed, key=lambda x: x.gap_step or 0, reverse=True)[:3]
    top_times = ", ".join([f"{(r.hour or 0)//12:02d}:{((r.hour or 0) % 12)*5:02d}" for r in top3])

    pct          = round((total_gap / total_opt * 100), 1) if total_opt > 0 else 0
    capture_pct  = round(100 - pct, 1)
    # risk band per the published War-Room thresholds (Ref. Manual Vol III):
    # a documented banding of DQ, not an invented composite rating.
    risk_band    = _risk_level(dq)
    top_opp      = (opportunities[0].name if opportunities else None)
    top_cause    = (root_causes[0].category if root_causes else None)
    top_cause_pct = (root_causes[0].contribution_pct if root_causes else None)

    L = []
    L.append("EXECUTIVE ASSESSMENT")
    L.append(
        f"During the audit period, {asset_name} captured {capture_pct}% of its Theoretical "
        f"Economic Ceiling (perfect-foresight upper-bound benchmark). Decision-quality risk "
        f"band per the published DQ thresholds: {risk_band}."
    )
    L.append(
        "Although the asset remained technically available, dispatch decisions failed to fully respond to "
        "market conditions, causing material value destruction."
        if dq < 0.7 else
        "The asset's dispatch decisions tracked the optimal counterfactual strategy closely throughout "
        "the audit period, with only minor deviations from peak economic performance."
    )
    L.append("")
    L.append("KEY FINDINGS")
    L.append(f"✔ Decision Quality (ECF)             {round(dq * 100, 1)} / 100")
    L.append(f"✔ Ceiling Gap (upper bound)          {_fmt_money(total_gap, currency)}")
    if gap_attribution:
        L.append(f"✔ Recoverable Execution Gap          {_fmt_money(gap_attribution['execution_gap'], currency)}")
    L.append(f"✔ Missed High-Value Intervals         {len(missed)}")
    if top_opp:
        L.append(f"✔ Largest Evidence-Backed Action      {top_opp}")
    L.append("")
    L.append("ROOT CAUSE ANALYSIS")
    if top_cause is not None:
        L.append(
            f"The largest gap category is '{top_cause}' — {top_cause_pct}% of the positive "
            "step-gap (exact partition of ledger rows by decision classification)."
        )
    else:
        L.append("No positive gap steps were recorded — no root-cause attribution applies.")
    if missed:
        L.append(
            f"The ledger records {len(missed)} high-price windows classified 'Missed Arbitrage'"
            + (f" — largest at {top_times}" if top_times else "")
            + " — where dispatch remained below the feasible optimum. Whether hardware, availability "
              "or contractual constraints contributed is OUTSIDE the scope of this data-only audit; "
              "the figures quantify the economic difference, not its operational cause."
        )
    L.append("")
    L.append("OPERATIONAL IMPACT")
    if gap_attribution:
        L.append(
            f"The Recoverable Execution Gap for the audited period is "
            f"{_fmt_money(gap_attribution['execution_gap'], currency)} — value that was achievable "
            f"using the day-ahead forecast available at decision time, with no additional hardware. "
            f"The remaining {_fmt_money(gap_attribution['forecast_gap'], currency)} of the ceiling gap "
            f"was reachable only with perfect price foresight and is NOT operator-attributable."
        )
    else:
        L.append(
            f"The gap of {_fmt_money(total_gap, currency)} is measured against the Theoretical "
            f"Economic Ceiling — a perfect-foresight upper-bound benchmark. It includes value that "
            f"no forecast-based operation could fully capture; the operationally recoverable portion "
            f"cannot be isolated for this dataset because no day-ahead forecast column was provided."
        )
    L.append("")
    L.append("AUDITOR CONCLUSION")
    L.append(
        f"Based solely on the audited dataset, the asset captured {round(dq * 100, 1)}% of its "
        f"perfect-foresight ceiling (risk band: {_risk_level(dq)} per the published DQ thresholds). "
        "This audit evaluates dispatch economics only; asset health, availability and contractual "
        "constraints are outside its evidence base."
    )
    L.append("")
    L.append("RECOMMENDED ACTIONS (evidence-derived)")
    quantified = [op for op in (opportunities or []) if not op.experimental and op.period_gain]
    advisory   = [op for op in (opportunities or []) if op.experimental]
    if quantified:
        for i, op in enumerate(quantified[:5], 1):
            L.append("")
            L.append(f"Recommendation {i} — {op.name}")
            L.append(f"  Value at Stake          {_fmt_money(op.period_gain, currency)}  (recorded period)")
            L.append(f"  Ledger Intervals        {op.intervals_observed}")
            L.append(f"  Derivation              {op.derivation}")
    else:
        L.append("  No positive-gap intervals were recorded — no quantified actions apply.")
    if advisory:
        L.append("")
        L.append("ADVISORY DIRECTIONS — Experimental, not part of EDA Standard v1.0; not "
                 "quantifiable from the audited dataset:")
        for op in advisory:
            L.append(f"  • {op.name}: {op.description}")

    return "\n".join(L)

def _risk_level(dq: float) -> str:
    # War Room thresholds per Reference Manual Vol III Part 1, Screen 1:
    # green > 0.9, yellow > 0.7, red below.
    if dq >= 0.90:
        return "Low"
    elif dq >= 0.70:
        return "Moderate"
    return "Severe"
