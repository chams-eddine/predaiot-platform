# -*- coding: utf-8 -*-
"""Time-of-Use (TOU) band analysis (Phase 2, Part 6.2) — higher-precision load
costing from OFFICIAL billed band totals (e.g. Nama OFPK/WDPK/NTPK/WEPK).

THREE LAYERS, always clearly separated (owner-ratified 2026-07-22):

  1. Actual Cost            — from the bill (C_actual, incl. non-energy charges).
  2. Theoretical Opportunity — the MAXIMUM saving, derived ENTIRELY from the data
     (shift every non-off-peak kWh to that month's off-peak rate, capacity
     permitting). No operational judgment. This is a CEILING, not a target.
  3. Recoverable Opportunity — the realistic saving AFTER operational constraints:
     Theoretical × flexibility_factor. The flexibility_factor is a **facility-
     specific DECLARED INPUT** (how much load the plant can actually shift given
     its operating pattern), NEVER a constant inside PREDAIOT. Different facilities
     have different values. If it is not declared, the Recoverable layer is NOT
     computed (None) — the platform does not invent an operational assumption.

No hidden assumptions: the engine/analysis computes only data-derived facts; the
one operational assumption (flexibility) is an explicit, per-facility input.
Currency: Nama rates are Bz/kWh; 1 Bz/kWh = 1 OMR/MWh, and band_kWh × Bz/kWh / 1000
= OMR. No dispatch engine involved — this is a billing-data analysis.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Guidance the UI/API MUST surface wherever a facility declares its shiftability.
# It must reflect THIS plant's reality — not an industry benchmark or optimism —
# and it is always optional (blank ⇒ Theoretical-only).
FLEXIBILITY_GUIDANCE = (
    "Operational shiftability (0–1): the fraction of THIS facility's peak-period load "
    "that can realistically be moved to off-peak, given its OWN operating pattern "
    "(shift schedules, continuous processes, thermal/product buffering). It must reflect "
    "this plant's real operational limits — NOT an industry benchmark, and NOT an "
    "optimistic guess. Leave it blank to receive only the data-derived Theoretical "
    "Opportunity (the ceiling); the Recoverable Opportunity is reported only when you "
    "declare this value."
)


def validate_flexibility(value: Optional[float]) -> Optional[float]:
    """None passes through (not declared). A declared value must be a real number in
    [0,1]. Raises ValueError otherwise (the caller maps it to a 422)."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError("flexibility_factor must be a number in [0,1], or blank.")
    if not (0.0 <= v <= 1.0):
        raise ValueError("flexibility_factor must be between 0 and 1 (fraction of peak "
                         "load realistically shiftable), or blank for Theoretical-only.")
    return v


@dataclass
class TouBandResult:
    # ── Layer 1 — Actual Cost (from the bill) ───────────────────────────────
    c_actual: float                       # OMR — billed total (energy + charges) if given, else energy
    c_actual_energy: float                # OMR — Σ band_kWh × rate (energy only)
    non_energy_charges: float             # OMR — billed − energy (fixed/demand/other); 0 if not billed

    # ── Layer 2 — Theoretical Opportunity (100% data-derived; a CEILING) ────
    theoretical_opportunity: float        # OMR — full band-shift saving
    theoretical_dq: float                 # (C_actual − theoretical) / C_actual  ∈ [0,1]
    theoretical_alp: float                # OMR/yr — theoretical × annualization

    # ── Layer 3 — Recoverable Opportunity (needs a DECLARED flexibility) ────
    flexibility_factor: Optional[float]   # facility-specific DECLARED input; None ⇒ not provided
    flexibility_source: str               # "declared" | "not_provided"
    recoverable_opportunity: Optional[float]   # None unless flexibility declared
    recoverable_dq: Optional[float]
    recoverable_alp: Optional[float]

    # ── Context / corroborating findings ────────────────────────────────────
    annualization_factor: float
    total_kwh: float
    band_shares: Dict[str, float]
    night_peak_month_shares: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Three explicitly-labelled layers for the report/API."""
        return {
            "actual_cost": {"c_actual": self.c_actual,
                            "energy_only": self.c_actual_energy,
                            "non_energy_charges": self.non_energy_charges},
            "theoretical_opportunity": {"amount": self.theoretical_opportunity,
                                        "dq": self.theoretical_dq,
                                        "annual": self.theoretical_alp,
                                        "basis": "full band shift to off-peak — data-derived ceiling"},
            "recoverable_opportunity": {"amount": self.recoverable_opportunity,
                                        "dq": self.recoverable_dq,
                                        "annual": self.recoverable_alp,
                                        "flexibility_factor": self.flexibility_factor,
                                        "flexibility_source": self.flexibility_source,
                                        "basis": "theoretical × declared operational shiftability"},
            "context": {"total_kwh": self.total_kwh, "band_shares": self.band_shares,
                        "night_peak_month_shares": self.night_peak_month_shares,
                        "annualization_factor": self.annualization_factor},
        }


def analyze_tou_bands(
    bands: Dict[str, List[float]],        # band_key → per-month kWh
    rates: Dict[str, List[float]],        # band_key → per-month Bz/kWh
    off_peak_key: str = "off",
    flexibility_factor: Optional[float] = None,   # DECLARED facility input; None ⇒ no Recoverable layer
    c_actual_billed: Optional[float] = None,      # OMR billed total (incl. non-energy charges)
    months: Optional[int] = None,
    night_peak_key: str = "ntpk",
) -> TouBandResult:
    n = months or len(next(iter(bands.values())))
    total_kwh = sum(bands[b][m] for b in bands for m in range(n))
    c_energy = sum(bands[b][m] * rates[b][m] for b in bands for m in range(n)) / 1000.0

    # Layer 2 — theoretical ceiling: shift every non-off-peak kWh to off-peak rate.
    ceiling = 0.0
    for m in range(n):
        off_rate = rates[off_peak_key][m]
        for b in bands:
            if b == off_peak_key:
                continue
            ceiling += bands[b][m] * (rates[b][m] - off_rate) / 1000.0
    ceiling = max(0.0, ceiling)

    c_actual = c_actual_billed if c_actual_billed is not None else c_energy
    non_energy = (c_actual - c_energy) if c_actual_billed is not None else 0.0
    ann = 12.0 / n                                 # quarterly sample → ×4 (Ref Manual ALP)

    theoretical_dq = ((c_actual - ceiling) / c_actual) if c_actual > 0 else 1.0
    theoretical_alp = ceiling * ann

    # Layer 3 — recoverable: ONLY when a flexibility factor is DECLARED. No default
    # assumption (do not invent unlimited or any other shiftability).
    if flexibility_factor is None:
        rec_amt = rec_dq = rec_alp = None
        flex_src = "not_provided"
    else:
        rec_amt = ceiling * float(flexibility_factor)
        rec_dq = ((c_actual - rec_amt) / c_actual) if c_actual > 0 else 1.0
        rec_alp = rec_amt * ann
        flex_src = "declared"

    shares = {b: (sum(bands[b][m] for m in range(n)) / total_kwh) if total_kwh else 0.0
              for b in bands}
    np_month = [(bands[night_peak_key][m] / sum(bands[b][m] for b in bands)) for m in range(n)] \
        if night_peak_key in bands else []

    return TouBandResult(
        c_actual=round(c_actual, 2), c_actual_energy=round(c_energy, 2),
        non_energy_charges=round(non_energy, 2),
        theoretical_opportunity=round(ceiling, 2), theoretical_dq=round(theoretical_dq, 4),
        theoretical_alp=round(theoretical_alp, 2),
        flexibility_factor=(float(flexibility_factor) if flexibility_factor is not None else None),
        flexibility_source=flex_src,
        recoverable_opportunity=(round(rec_amt, 2) if rec_amt is not None else None),
        recoverable_dq=(round(rec_dq, 4) if rec_dq is not None else None),
        recoverable_alp=(round(rec_alp, 2) if rec_alp is not None else None),
        annualization_factor=round(ann, 4), total_kwh=total_kwh,
        band_shares={k: round(v, 4) for k, v in shares.items()},
        night_peak_month_shares=[round(x, 4) for x in np_month],
    )
