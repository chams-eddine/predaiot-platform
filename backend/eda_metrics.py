# -*- coding: utf-8 -*-
"""
PREDAIOT EDA quality metrics — versioned, asset-agnostic, self-describing.

DESIGN CONTRACT (enforced by the review-board hardening phase):
  * No invented coefficients. Every value is computed from integer evidence
    counts by a published, deterministic formula. The ONLY declared constants
    are the grade-band cut-points, which are a normative DEFINITION of the
    EDA grading scale (a communication layer over the numeric value), not an
    empirical measurement — versioned and revisable in EDA Standard v1.0.
  * Asset-agnostic. No metric assumes SoC, forecast, curtailment or any
    battery/asset-specific variable. A dimension that does not apply to the
    dataset is Not Applicable (None) and is EXCLUDED from the aggregate —
    it is never scored zero. Works identically for BESS, Solar, Wind, CHP,
    Gas Turbine, Combined Cycle, Hydro, Pumped Hydro, Grid, Industrial loads.
  * Audit Confidence is independent of Forecast Reliability. Audit Confidence
    measures confidence in the audit PROCESS (evidence quality + model
    consistency, gated by solver optimality). Forecast Reliability measures
    the accuracy of a supplied forecast model and is REPORT-ONLY in v1.
  * Every metric is versioned and self-describing via METRIC_REGISTRY:
    name, version, equation, inputs, outputs, dependencies, validation rules.
  * Every result is independently reproducible from the Data Quality Manifest
    (raw counts) using the formulas below.

This module is PURE: no I/O, no framework, no asset physics. Unit-testable in
isolation. main.py imports it; the numeric optimizer is untouched.
"""
from typing import Dict, List, Optional

# ── Versions (future EDA Standard v1.0 compatibility) ───────────────────────
DQI_VERSION         = "EDA-DQI-1.0"
AC_VERSION          = "EDA-AC-1.0"
GRADE_SCALE_VERSION = "EDA-GRADE-1.0"
FORECAST_REL_VERSION = "EDA-FR-1.0-experimental"

_EPS = 1e-9  # floating-point guard only (not a modelling coefficient)


# ── Grade scale (declared normative definition, versioned) ──────────────────
# These cut-points are NOT derived from data and carry no statistical claim.
# They are a declared grading scale — analogous to a conformity-grade or
# rating scale — that communicates the numeric value, which remains the
# primary reproducible quantity. Band A aligns with the 0.90 risk threshold
# already published for DQ, for internal consistency.
_GRADE_BANDS = [
    (0.90, "A", "High reliability"),
    (0.75, "B", "Good"),
    (0.60, "C", "Acceptable — review flags"),
    (0.40, "D", "Low — treat with caution"),
    (0.00, "E", "Insufficient data quality"),
]


def grade(value: Optional[float]) -> Dict[str, Optional[str]]:
    """
    Map a [0,1] score to the declared EDA grade scale.
    Domain: value ∈ [0,1] or None. Range: {A,B,C,D,E} or "N/A".
    Edge/failure: None → N/A; values are clamped by callers, but a stray
    out-of-range value still resolves via the ordered bands.
    """
    if value is None:
        return {"grade": "N/A", "interpretation": "Not applicable", "scale_version": GRADE_SCALE_VERSION}
    for lo, g, interp in _GRADE_BANDS:
        if value >= lo:
            return {"grade": g, "interpretation": interp, "scale_version": GRADE_SCALE_VERSION}
    return {"grade": "E", "interpretation": "Insufficient data quality", "scale_version": GRADE_SCALE_VERSION}


def _ratio(numer: Optional[int], denom: Optional[int]) -> Optional[float]:
    """
    Deterministic bounded ratio. Returns None (Not Applicable) when the
    denominator is None or 0 — an undefined ratio must stay Unknown, never 0.
    Otherwise numer/denom clamped to [0,1].
    """
    if denom is None or denom == 0 or numer is None:
        return None
    return max(0.0, min(1.0, numer / denom))


# ── DQI components — each ∈ [0,1] or None (N/A). All asset-agnostic. ─────────
# Notation:  n_* are non-negative integer evidence counts.
# Units:     dimensionless fraction.  Domain: counts ≥ 0.  Range: [0,1] ∪ {None}.

def completeness(n_present: Optional[int], n_expected: Optional[int]) -> Optional[float]:
    """
    C = n_present / n_expected  — fraction of expected time steps present.
    N/A when the dataset has no parseable timeline (n_expected is None).
    Reproducibility: n_expected = round(span_seconds / step_interval) + 1.
    """
    return _ratio(n_present, n_expected)


def timestamp_integrity(n_rows: Optional[int], n_unparseable: int, n_duplicate: int) -> Optional[float]:
    """
    T = 1 − (n_unparseable + n_duplicate) / n_rows.
    Out-of-order rows are excluded (sorting is lossless; disclosed as a flag).
    N/A when there is no timestamp column (n_rows is None).
    """
    if n_rows is None or n_rows == 0:
        return None
    return max(0.0, min(1.0, 1.0 - (n_unparseable + n_duplicate) / n_rows))


def sensor_validity(n_present: Optional[int], n_violation: int) -> Optional[float]:
    """
    S = 1 − n_violation / n_present  — fraction of state-variable readings that
    pass the applicable physical-plausibility test.
    v1 LIMITATION: the only implemented plausibility test is the storage
    SoC-vs-power bound; for assets without a state-of-charge variable this
    metric is Not Applicable (n_present is None) — never zero.
    """
    return _ratio((n_present - n_violation) if n_present is not None else None, n_present)


def telemetry_health(n_rows: Optional[int], n_degraded: int) -> Optional[float]:
    """
    H = 1 − n_degraded / n_rows  — fraction of steps whose telemetry/comms
    status is healthy. N/A when no telemetry-status column exists.
    """
    if n_rows is None or n_rows == 0:
        return None
    return max(0.0, min(1.0, 1.0 - n_degraded / n_rows))


def price_integrity(n_rows: Optional[int], n_missing: int) -> Optional[float]:
    """
    P = 1 − n_missing / n_rows  — fraction of price samples that were genuinely
    provided (not absent/interpolated). Market-plausibility signals
    (frozen feed, negative prices) are DISCLOSED as flags, not scored, so no
    detection threshold enters the number. Price is a required input, so this
    component always applies (never N/A) for a runnable audit.
    """
    if n_rows is None or n_rows == 0:
        return None
    return max(0.0, min(1.0, 1.0 - n_missing / n_rows))


def forecast_availability(n_rows: Optional[int], n_present: Optional[int]) -> Optional[float]:
    """
    F = n_present / n_rows  — completeness of a SUPPLIED forecast column.
    N/A when the dataset carries no forecast column (n_present is None) — the
    absence of an optional dimension must not reduce data quality.
    NOTE: this measures forecast PRESENCE, not forecast accuracy. Accuracy is
    Forecast Reliability (separate, report-only).
    """
    return _ratio(n_present, n_rows)


# Ordered component keys (stable presentation order across all assets)
DQI_COMPONENT_KEYS = [
    "completeness", "timestamp_integrity", "sensor_validity",
    "telemetry_health", "price_integrity", "forecast_availability",
]

DQI_COMPONENT_LABELS = {
    "completeness":         "Completeness",
    "timestamp_integrity":  "Timestamp Integrity",
    "sensor_validity":      "Sensor Validity",
    "telemetry_health":     "Telemetry Health",
    "price_integrity":      "Price Integrity",
    "forecast_availability": "Forecast Availability",
}


def _geomean(values: List[float]) -> float:
    """
    Geometric mean of n values (equal treatment — the non-informative choice;
    the exponent 1/n is the DEFINITION of the geometric mean, not a weight).
    If any value is exactly 0, the result is 0 by definition (a single fully
    corrupt dimension yields zero trust) — computed without log(0).
    """
    if not values:
        return 0.0
    if any(v <= 0.0 for v in values):
        return 0.0
    prod = 1.0
    for v in values:
        prod *= v
    return prod ** (1.0 / len(values))


def data_quality_index(components: Dict[str, Optional[float]]) -> Optional[float]:
    """
    DQI = geometric mean over the APPLICABLE components (None excluded).

    Domain: each component ∈ [0,1] ∪ {None}.  Range: [0,1] ∪ {None}.
    Assumptions: components are conjunctive (a dataset is trustworthy only if
      every applicable dimension is good) → geometric, not arithmetic, mean.
    Edge cases: |applicable| ≥ 1 in any runnable audit (price_integrity always
      applies). If all were None (not reachable for a runnable audit), DQI=None.
    Failure cases: any applicable component 0 → DQI 0.
    Reproducibility: recompute each component from the Data Quality Manifest
      counts, then take the geometric mean of the non-None set.
    """
    applicable = [v for v in components.values() if v is not None]
    if not applicable:
        return None
    return _geomean(applicable)


def build_dqi(components: Dict[str, Optional[float]]) -> dict:
    """Assemble the full, presentation-ready DQI object (numeric + grade + parts)."""
    value = data_quality_index(components)
    out = {
        "metric": "DataQualityIndex", "version": DQI_VERSION,
        "value": (round(value, 4) if value is not None else None),
        "value_pct": (round(value * 100, 1) if value is not None else None),
        "components": {
            k: {
                "label": DQI_COMPONENT_LABELS[k],
                "value": (round(components.get(k), 4) if components.get(k) is not None else None),
                "value_pct": (round(components.get(k) * 100, 1) if components.get(k) is not None else None),
                "applicable": components.get(k) is not None,
            } for k in DQI_COMPONENT_KEYS
        },
        "components_applicable": [k for k in DQI_COMPONENT_KEYS if components.get(k) is not None],
        "components_na":         [k for k in DQI_COMPONENT_KEYS if components.get(k) is None],
        "aggregation": "geometric_mean(applicable components)",
    }
    out.update(grade(value))
    return out


# ── Audit Confidence — independent of Forecast Reliability ──────────────────

def model_consistency(dq_score_raw: Optional[float]) -> Optional[float]:
    """
    M — agreement between the modeled feasible optimum and the observed actual.

    M = 1                      if dq_raw ≤ 1            (actual within the optimum)
      = 1 / dq_raw             if dq_raw > 1            (actual "beat" the optimum)

    where dq_raw = EDV_actual / EDV_optimal (unclamped). dq_raw > 1 is
    physically impossible and signals wrong column mapping or asset specs; the
    fraction of the reported actual that is physically explainable is exactly
    EDV_optimal / EDV_actual = 1/dq_raw — a DERIVED quantity, not a constant.
    Negative dq_raw (value-destructive dispatch) is a legitimate finding, M=1.

    Domain: dq_raw ∈ ℝ ∪ {None}.  Range: (0,1] ∪ {None}.
    Edge/failure: dq_raw None → None; dq_raw → ∞ → M → 0.
    """
    if dq_score_raw is None:
        return None
    if dq_score_raw <= 1.0 + _EPS:
        return 1.0
    return 1.0 / dq_score_raw


def audit_confidence(dqi_value: Optional[float],
                     model_consistency_value: Optional[float],
                     solver_proven: bool) -> dict:
    """
    Audit Confidence — confidence in the audit PROCESS (NOT the forecast).

    Gate (Solver Integrity): if the optimizer returned an unproven incumbent
      (time-cap hit, no MIP gap available) the optimum — hence the gap — is
      only a lower bound, so confidence is INDETERMINATE. We do NOT invent a
      numeric penalty for an unknown optimality gap (unknown stays unknown).

    Otherwise:  AC = DQI × ModelConsistency   (multiplicative attenuation).

    Derivation of the aggregation: Audit Confidence is the evidence quality
    (DQI) REDUCED by any model–data inconsistency (M ≤ 1). A geometric mean
    was rejected: geomean(DQI, 1) = √DQI > DQI would let a perfect-consistency
    factor RAISE confidence ABOVE the data quality — indefensible, since
    confidence in a result cannot exceed the quality of the evidence it rests
    on. The product has the correct boundary conditions:
        M = 1  ⟹  AC = DQI     (data-limited: only data quality constrains it)
        M → 0  ⟹  AC → 0       (a model/data contradiction destroys confidence)
        AC ≤ min(DQI, M)       (bounded by both factors)
    This is NOT a function of DQI alone — it incorporates Model Consistency
    and is gated by Solver Integrity. If DQI is None (e.g. a direct-JSON audit
    with no manifest) AC falls back to M so a value is still produced.

    Forecast Reliability is deliberately EXCLUDED (report-only in v1).

    Domain: dqi, M ∈ [0,1] ∪ {None}.  Range: [0,1] ∪ {None (INDETERMINATE/N/A)}.
    Units: dimensionless.  Reproducibility: AC = DQI × M from the two factors.
    """
    factors = {"data_quality_index": dqi_value, "model_consistency": model_consistency_value,
               "solver_proven": solver_proven}
    if not solver_proven:
        return {
            "metric": "AuditConfidence", "version": AC_VERSION,
            "value": None, "value_pct": None,
            "grade": "INDETERMINATE",
            "interpretation": "Solver returned an unproven incumbent; the optimum is a lower bound.",
            "scale_version": GRADE_SCALE_VERSION,
            "aggregation": "DQI × ModelConsistency, solver-gated",
            "factors": factors,
        }
    applicable = [v for v in (dqi_value, model_consistency_value) if v is not None]
    if not applicable:
        value = None
    else:
        value = 1.0
        for v in applicable:
            value *= v          # product of the applicable evidence factors
    out = {
        "metric": "AuditConfidence", "version": AC_VERSION,
        "value": (round(value, 4) if value is not None else None),
        "value_pct": (round(value * 100, 1) if value is not None else None),
        "aggregation": "DQI × ModelConsistency, solver-gated",
        "factors": factors,
    }
    out.update(grade(value))
    return out


# ── Forecast Reliability — REPORT ONLY (experimental, not in AC v1) ─────────

def forecast_reliability(mape: Optional[float]) -> Optional[dict]:
    """
    FR = 1 − min(1, MAPE),  MAPE = mean(|forecast − actual| / max(|actual|, ε)).
    Measures accuracy of a SUPPLIED forecast model. Independent of Audit
    Confidence. Report-only in v1 pending multi-asset-class validation.
    Domain: MAPE ≥ 0 ∪ {None}.  Range: [0,1] ∪ {None}.  N/A when no forecast.
    """
    if mape is None:
        return None
    value = max(0.0, 1.0 - min(1.0, mape))
    return {
        "metric": "ForecastReliability", "version": FORECAST_REL_VERSION,
        "value": round(value, 4), "value_pct": round(value * 100, 1),
        "mape": round(mape, 4),
        "status": "Experimental – Not part of EDA Standard v1.0; report-only, "
                  "not used to weight Audit Confidence.",
    }


# ── Self-describing metric registry (future EDA Standard v1.0) ──────────────
METRIC_REGISTRY = {
    "DataQualityIndex": {
        "name": "Data Quality Index (DQI)", "version": DQI_VERSION,
        "equation": "DQI = (∏_{x∈A} x)^(1/|A|), A = applicable components ⊆ "
                    "{Completeness, TimestampIntegrity, SensorValidity, "
                    "TelemetryHealth, PriceIntegrity, ForecastAvailability}",
        "inputs": "Data Quality Manifest integer counts (see manifest keys).",
        "outputs": "value ∈ [0,1] ∪ {None}; grade ∈ {A..E,N/A}; per-component vector.",
        "dependencies": ["DataQualityManifest"],
        "validation_rules": [
            "Each component ∈ [0,1] or None (Not Applicable).",
            "Non-applicable components are excluded from the geometric mean, never scored 0.",
            "Any applicable component = 0 ⟹ DQI = 0.",
            "Asset-agnostic: no component assumes SoC/forecast/curtailment; missing → N/A.",
        ],
    },
    "AuditConfidence": {
        "name": "Audit Confidence", "version": AC_VERSION,
        "equation": "AC = DQI × ModelConsistency (solver-gated; INDETERMINATE if "
                    "solver optimum unproven). ModelConsistency M = 1 if dq_raw≤1 "
                    "else 1/dq_raw. Product, not geometric mean, so AC ≤ min(DQI,M) "
                    "(confidence never exceeds evidence quality).",
        "inputs": "DQI value; dq_score_raw = EDV_actual/EDV_optimal; solver_proven flag.",
        "outputs": "value ∈ [0,1] ∪ {None}; grade ∈ {A..E, INDETERMINATE, N/A}.",
        "dependencies": ["DataQualityIndex", "dq_score_raw", "solver_status"],
        "validation_rules": [
            "Independent of Forecast Reliability.",
            "Unproven solver incumbent ⟹ INDETERMINATE (no invented penalty).",
            "Not a function of DQI alone (incorporates Model Consistency + solver gate).",
        ],
    },
    "ForecastReliability": {
        "name": "Forecast Reliability (Experimental)", "version": FORECAST_REL_VERSION,
        "equation": "FR = 1 − min(1, MAPE); MAPE = mean(|f−p|/max(|p|,ε))",
        "inputs": "Supplied forecast column vs realized price.",
        "outputs": "value ∈ [0,1] ∪ {None}.",
        "dependencies": ["forecast column"],
        "validation_rules": [
            "Report-only in v1; NOT used to weight Audit Confidence.",
            "N/A when no forecast column is supplied.",
        ],
    },
    "GradeScale": {
        "name": "EDA Grade Scale", "version": GRADE_SCALE_VERSION,
        "equation": "A≥0.90, B≥0.75, C≥0.60, D≥0.40, E<0.40",
        "inputs": "A score ∈ [0,1].",
        "outputs": "Letter grade + interpretation.",
        "dependencies": [],
        "validation_rules": [
            "Declared normative definition — NOT empirically derived.",
            "Communication layer over the numeric value; the number is primary.",
            "Revisable in EDA Standard v1.0.",
        ],
    },
}
