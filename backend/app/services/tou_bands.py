# -*- coding: utf-8 -*-
"""Time-of-Use (TOU) band analysis (Phase 2, Part 6.2) — higher-precision load
costing from OFFICIAL billed band totals (e.g. Nama OFPK/WDPK/NTPK/WEPK), rather
than a flat monthly-average estimate.

Two-tier gap (matches the platform's theoretical_ceiling vs recoverable structure
and the owner-ratified 'ceiling + disclosed flexibility factor' decision):

  • theoretical_ceiling_gap — shift EVERY non-off-peak kWh to that month's off-peak
    rate (capacity permitting). Data-derived; no operational judgment. Per spec
    Part 3.3 this is a CEILING, not a realistic target.
  • recoverable_gap = ceiling × flexibility_factor — the realistically-shiftable
    fraction, given the plant's operating pattern. flexibility_factor is a DISCLOSED
    per-facility input (the plant can't idle during peak if it runs near-24/7), NOT a
    fabricated constant. Muscat delivered report ⇒ 0.44.

Currency note: Nama rates are Bz/kWh; 1 Bz/kWh = 1 OMR/MWh, and band_kWh × Bz/kWh /
1000 = OMR. No engine involvement — this is a billing-data analysis, not dispatch.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TouBandResult:
    c_actual: float                       # OMR — billed total (energy + charges) if given, else energy
    c_actual_energy: float                # OMR — Σ band_kWh × rate (energy only)
    non_energy_charges: float             # OMR — billed − energy (fixed/demand/other), 0 if not billed
    theoretical_ceiling_gap: float        # OMR — full band-shift ceiling savings
    flexibility_factor: float             # disclosed shiftability (0..1)
    recoverable_gap: float                # OMR — ceiling × flexibility
    c_optimal: float                      # OMR — c_actual − recoverable_gap
    dq: float                             # C_optimal / C_actual ∈ [0,1]
    alp: float                            # OMR/yr — recoverable × annualization
    annualization_factor: float
    total_kwh: float
    band_shares: Dict[str, float]         # band → fraction of total consumption
    night_peak_month_shares: List[float] = field(default_factory=list)


def analyze_tou_bands(
    bands: Dict[str, List[float]],        # band_key → per-month kWh
    rates: Dict[str, List[float]],        # band_key → per-month Bz/kWh
    off_peak_key: str = "off",
    flexibility_factor: float = 1.0,
    c_actual_billed: Optional[float] = None,   # OMR billed total (incl. non-energy charges)
    months: Optional[int] = None,
    night_peak_key: str = "ntpk",
) -> TouBandResult:
    n = months or len(next(iter(bands.values())))
    total_kwh = sum(bands[b][m] for b in bands for m in range(n))
    c_energy = sum(bands[b][m] * rates[b][m] for b in bands for m in range(n)) / 1000.0

    # Ceiling: shift every non-off-peak kWh to that month's off-peak rate.
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

    recoverable = ceiling * float(flexibility_factor)
    c_optimal = c_actual - recoverable
    dq = (c_optimal / c_actual) if c_actual > 0 else 1.0
    ann = 12.0 / n                                 # quarterly sample → ×4 (Ref Manual ALP)
    alp = recoverable * ann

    shares = {b: (sum(bands[b][m] for m in range(n)) / total_kwh) if total_kwh else 0.0
              for b in bands}
    np_month = [(bands[night_peak_key][m] / sum(bands[b][m] for b in bands)) for m in range(n)] \
        if night_peak_key in bands else []

    return TouBandResult(
        c_actual=round(c_actual, 2), c_actual_energy=round(c_energy, 2),
        non_energy_charges=round(non_energy, 2),
        theoretical_ceiling_gap=round(ceiling, 2),
        flexibility_factor=float(flexibility_factor),
        recoverable_gap=round(recoverable, 2), c_optimal=round(c_optimal, 2),
        dq=round(dq, 4), alp=round(alp, 2), annualization_factor=round(ann, 4),
        total_kwh=total_kwh, band_shares={k: round(v, 4) for k, v in shares.items()},
        night_peak_month_shares=[round(x, 4) for x in np_month],
    )
