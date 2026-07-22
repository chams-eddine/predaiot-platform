# -*- coding: utf-8 -*-
"""Muscat Steel Melting Co. — permanent reference regression (spec Part 7).

Ground truth = the hand-validated audit DELIVERED to the client (Apr–Jun 2026,
91 days of real EAF/LRF data cross-checked against Nama invoices). Tests the THREE
layers PREDAIOT must expose (owner-ratified):

  1. Actual Cost           — the bill: C_actual ≈ 1,051,080 OMR.
  2. Theoretical Opportunity — data-derived ceiling ≈ 214,796 OMR (DQ ≈ 0.80).
  3. Recoverable Opportunity — ONLY with a DECLARED, facility-specific flexibility
     factor (Muscat = 0.44, an INPUT, not a platform constant):
     Gap ≈ 94,597 OMR (3-mo) · DQ ≈ 0.91 · ALP ≈ 378,389 OMR/yr.

No-Fabrication guard: with NO flexibility declared, the Recoverable layer is None —
the platform never invents an operational assumption. 0.44 lives here as a test
INPUT; it is nowhere in PREDAIOT's engine/analysis logic.
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
_MUSCAT_FLEXIBILITY = 0.44            # facility-specific DECLARED input (from the delivered report)


def _close(a, b, tol_pct=1.5):
    return abs(a - b) <= abs(b) * tol_pct / 100.0


# ── Layer 1 — Actual Cost ───────────────────────────────────────────────────
def test_layer1_actual_cost():
    r = analyze_tou_bands(_BANDS, _RATES, c_actual_billed=_BILLED_C_ACTUAL)
    assert r.total_kwh == 44_569_610                       # exact — validates band inputs
    assert _close(r.c_actual, 1_051_080, 0.1)
    assert _close(r.c_actual_energy, 1_016_060, 0.5)
    assert r.non_energy_charges > 0                        # billed − energy = fixed/demand charges


# ── Layer 2 — Theoretical Opportunity (data-derived; no flexibility needed) ──
def test_layer2_theoretical_ceiling_is_data_derived():
    r = analyze_tou_bands(_BANDS, _RATES, c_actual_billed=_BILLED_C_ACTUAL)  # NO flexibility
    assert _close(r.theoretical_opportunity, 214_796, 0.5)
    assert _close(r.theoretical_dq, 0.796, 2)             # (1,051,080 − 214,796)/1,051,080
    assert _close(r.theoretical_alp, 859_185, 0.5)


# ── No-Fabrication guard — no declared flexibility ⇒ no Recoverable layer ────
def test_no_flexibility_means_no_recoverable_layer():
    r = analyze_tou_bands(_BANDS, _RATES, c_actual_billed=_BILLED_C_ACTUAL)
    assert r.flexibility_factor is None
    assert r.flexibility_source == "not_provided"
    assert r.recoverable_opportunity is None
    assert r.recoverable_dq is None and r.recoverable_alp is None


# ── Layer 3 — Recoverable Opportunity (with DECLARED facility flexibility) ───
def test_layer3_recoverable_reproduces_delivered_figures():
    r = analyze_tou_bands(_BANDS, _RATES, c_actual_billed=_BILLED_C_ACTUAL,
                          flexibility_factor=_MUSCAT_FLEXIBILITY)
    assert r.flexibility_source == "declared" and r.flexibility_factor == 0.44
    assert _close(r.recoverable_opportunity, 94_597, 1.5)  # ≈ 94,597 OMR (3-month)
    assert _close(r.recoverable_dq, 0.91, 1.5)             # ≈ 0.91
    assert _close(r.recoverable_alp, 378_389, 1.5)         # ≈ 378,389 OMR/year
    assert r.annualization_factor == 4.0                   # quarterly → annual (not ×365 on 1 day)


def test_night_peak_band_share_corroborating_finding():
    r = analyze_tou_bands(_BANDS, _RATES, c_actual_billed=_BILLED_C_ACTUAL)
    # Directly computable from the band data; spec: 19.5% (May) to 21.5% (June).
    assert _close(r.night_peak_month_shares[1], 0.195, 3)  # May
    assert _close(r.night_peak_month_shares[2], 0.215, 3)  # June
