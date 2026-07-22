# -*- coding: utf-8 -*-
"""Muscat Steel Melting Co. — permanent reference regression (spec Part 7).

Ground truth = the hand-validated audit DELIVERED to the client (Apr–Jun 2026,
91 days of real EAF/LRF data cross-checked against Nama invoices). The platform's
TOU band-level analysis, with the delivered report's disclosed flexibility factor
(0.44), must reproduce the delivered figures:

    C_actual  ≈ 1,051,080 OMR   (billed, energy + non-energy charges)
    Gap       ≈    94,597 OMR   (3-month, recoverable at 0.44 flexibility)
    DQ        ≈    0.91
    ALP       ≈   378,389 OMR/year

It also pins the data-derived THEORETICAL CEILING (full band shift, 214,796 OMR)
and the Night-Peak band share (19.5%–21.5%) as a corroborating finding. If the
platform's output drifts from these, a load-audit change has regressed — do not ship.
"""
from app.services.tou_bands import analyze_tou_bands

# Official Nama TOU band totals (kWh) — April / May / June 2026.
_BANDS = {
    "off":  [10_092_820, 9_850_600, 9_983_380],
    "wdpk": [ 1_327_560, 1_220_300, 1_331_270],
    "ntpk": [ 3_222_150, 2_800_890, 3_223_470],
    "wepk": [   543_640,   492_300,   481_230],
}
# Official Nama rates (Bz/kWh): April flat 16; May–June TOU.
_RATES = {
    "off":  [16, 19, 19], "wdpk": [16, 36, 36],
    "ntpk": [16, 46, 46], "wepk": [16, 28, 28],
}
_BILLED_C_ACTUAL = 1_051_080.410      # OMR, actual bill (incl. non-energy charges)
_FLEXIBILITY = 0.44                   # delivered report's stated shiftability

_R = analyze_tou_bands(_BANDS, _RATES, off_peak_key="off",
                       flexibility_factor=_FLEXIBILITY,
                       c_actual_billed=_BILLED_C_ACTUAL)


def _close(a, b, tol_pct=1.5):
    return abs(a - b) <= abs(b) * tol_pct / 100.0


def test_total_consumption_matches():
    assert _R.total_kwh == 44_569_610                       # exact — validates band inputs


def test_c_actual_billed():
    assert _close(_R.c_actual, 1_051_080, 0.1)
    # the billed total exceeds energy-only by the non-energy (fixed/demand) charges
    assert _close(_R.c_actual_energy, 1_016_060, 0.5)
    assert _R.non_energy_charges > 0


def test_theoretical_ceiling_is_data_derived():
    # Full band shift to off-peak — no operational judgment. ~21% of energy cost.
    assert _close(_R.theoretical_ceiling_gap, 214_796, 0.5)


def test_delivered_gap_dq_alp():
    # Recoverable (at 0.44 flexibility) reproduces the delivered client figures.
    assert _close(_R.recoverable_gap, 94_597, 1.5)          # ≈ 94,597 OMR (3-month)
    assert _close(_R.dq, 0.91, 1.5)                         # ≈ 0.91
    assert _close(_R.alp, 378_389, 1.5)                     # ≈ 378,389 OMR/year
    assert _R.annualization_factor == 4.0                   # quarterly → annual (not ×365 on 1 day)


def test_night_peak_band_share_corroborating_finding():
    # Directly computable from the band data; spec: 19.5% (May) to 21.5% (June).
    assert _close(_R.night_peak_month_shares[1], 0.195, 3)  # May
    assert _close(_R.night_peak_month_shares[2], 0.215, 3)  # June
