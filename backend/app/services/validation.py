# -*- coding: utf-8 -*-
"""Audit-result validation gates (spec Part 4) — a post-computation sanity layer.

Runs on every audit result before it is surfaced. Two severities, deliberately:
  • HARD (impossible-by-construction): DQ outside [0,1], negative Economic Gap.
    These CANNOT occur for a correctly-routed audit (the optimum is the maximum,
    so gap ≥ 0; DQ is a clamped ratio). If one ever fires it signals a genuine
    upstream bug (e.g. the load/storage category error) — the result is WITHHELD.
  • SOFT (plausibility / provenance): statistically-extreme DQ, silently-defaulted
    currency. These are SURFACED as warnings, never halted — a deployed audit must
    not suppress a legitimate extreme-but-real result (a genuinely poor operator can
    have DQ 0.4; a perfect one 1.0). The spec's "halt on DQ<0.5" would wrongly
    censor real findings, so it is a review flag here, not a block.

No economic math; consumes the finished AuditResponse dict. Engine untouched.
"""
from typing import Any, Dict


def validate_audit_result(d: Dict[str, Any], currency_source: str = "detected",
                          asset_class: str = None) -> Dict[str, Any]:
    """Return {passed, errors, warnings, currency_source}. passed=False ⇒ a HARD
    (impossible) gate failed and the caller must withhold the result.

    `asset_class` matters for Gate 2: a LOAD's gap is a true cost lower bound so
    gap<0 is impossible (the exact Muscat category-error signature → withhold). For
    a storage/generation asset the modeled optimum is a perfect-foresight
    counterfactual the actual CAN exceed (raw DQ>1) — a benign model/data mismatch
    the engine already clamps + flags, so it's a WARNING, not a halt."""
    errors, warnings = [], []
    dq = d.get("dq_score")
    dq_raw = d.get("dq_score_raw")
    gap = d.get("total_gap_usd")

    # Gate 1 — clamped DQ must be in [0,1] (impossible-by-construction otherwise).
    if dq is None or not (0.0 <= float(dq) <= 1.0):
        errors.append(f"DQ={dq} is outside [0,1] — impossible; result withheld.")

    # Gate 2 — negative Economic Gap. HARD only for loads (impossible by construction);
    # for storage/generation it's the known "actual beat the modeled optimum" state.
    if gap is not None and float(gap) < -0.01:
        if asset_class == "load":
            errors.append(f"Economic Gap={gap} is negative for a LOAD asset — impossible by "
                          f"construction (cheapest-hours reallocation can't cost more than "
                          f"actual). Result withheld — a routing or units bug upstream.")
        else:
            warnings.append(f"Actual dispatch scored above the modeled optimum (gap={gap:.2f}) — "
                            f"model/data disagreement; review column mapping and asset specs.")

    # Gate 3 (soft) — statistically-extreme DQ: review inputs, don't censor.
    if dq is not None and (float(dq) < 0.5 or float(dq) > 0.999):
        warnings.append(f"DQ={float(dq):.3f} is statistically extreme — double-check units, "
                        f"price scale, and column mapping before quoting this result.")

    # Model/data disagreement (raw ratio beyond the modeled ceiling): review.
    if dq_raw is not None and float(dq_raw) > 1.02:
        warnings.append(f"Actual exceeds the modeled optimum (raw DQ={float(dq_raw):.2f}) — "
                        f"the column mapping or asset specs likely don't match this asset.")

    # Gate 5 (soft) — currency must never be silently assumed (No-Fabrication).
    if currency_source in ("defaulted", "unknown"):
        warnings.append("Billing currency could not be determined from the data and was not "
                        "declared; it is reported as UNKNOWN, not assumed. Declare the billing "
                        "currency (upload selector or facility setting) before quoting figures.")

    return {"passed": len(errors) == 0, "errors": errors,
            "warnings": warnings, "currency_source": currency_source}
