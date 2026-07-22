# PREDAIOT EDA Quality Metrics — v1 (pre-EDA-Standard)

Versioned, asset-agnostic, self-describing quality metrics. Every value is
computed from integer evidence counts (the **Data Quality Manifest**) by a
published deterministic formula, and is independently reproducible. No metric
assumes any asset-specific variable (SoC, forecast, curtailment, battery
state); a dimension that does not apply to a dataset is **Not Applicable (N/A)**
and is excluded from aggregation — never scored zero.

Source of truth: `backend/eda_metrics.py` (pure module) + `GET /api/v1/metrics/registry`.

---

## 1. Data Quality Index (DQI) — `EDA-DQI-1.0`

**Notation.** For a dataset of `N` ingested rows, let the integer evidence
counts of the Data Quality Manifest be `n_expected, n_present, n_unparseable,
n_dup, n_price_missing, n_soc_present, n_soc_violation, n_comms, n_comms_bad,
n_fc_present`.

**Components** (each dimensionless, domain: counts ≥ 0, range **[0,1] ∪ {N/A}**):

| Component | Symbol | Equation | N/A when |
|---|---|---|---|
| Completeness | C | `n_present / n_expected` | no parseable timeline |
| Timestamp Integrity | T | `1 − (n_unparseable + n_dup)/N` | no timestamp column |
| Sensor Validity | S | `1 − n_soc_violation / n_soc_present` | no state-of-charge column *(v1 limitation: SoC-physics only)* |
| Telemetry Health | H | `1 − n_comms_bad / n_comms` | no telemetry-status column |
| Price Integrity | P | `1 − n_price_missing / N` | never (price required) |
| Forecast Availability | F | `n_fc_present / N` | no forecast column |

Market-plausibility signals (frozen feed, negative prices) and out-of-order
rows are **disclosed as flags, not scored**, so no detection threshold enters a
KPI.

**Aggregation.** Let `A = { applicable components }` (`|A| ≥ 1` always):

    DQI = ( ∏_{x∈A} x )^(1/|A|)          (geometric mean)

- **Units:** dimensionless. **Domain:** each `x ∈ [0,1]∪{N/A}`. **Range:** `[0,1]∪{N/A}`.
- **Why geometric, not arithmetic:** quality dimensions are conjunctive; DQI=1
  iff every applicable component=1, and any weak component drives it toward 0.
  Equal treatment (exponent `1/|A|`) is the non-informative choice — the *absence*
  of an invented importance ranking, not a fabricated weight.
- **Assumptions:** uniform step interval (else C,T→N/A); price required.
- **Edge cases:** all-N/A impossible for a runnable audit (P always applies).
- **Failure cases:** any applicable component `= 0` ⟹ `DQI = 0` (by definition).
- **Reproducibility:** recompute each component from manifest counts, take the
  geometric mean of the non-N/A set. Verified in `smoke_pdf_ibri2` to 4 dp.

## 2. Audit Confidence — `EDA-AC-1.0`

Confidence in the audit **process** — independent of forecast accuracy.

    Model Consistency:  M = 1                if dq_raw ≤ 1
                        M = 1 / dq_raw        if dq_raw > 1
        where dq_raw = EDV_actual / EDV_optimal (unclamped)

    Solver gate:  σ = proven-optimal? → normal;  unproven incumbent → INDETERMINATE

    Audit Confidence:  AC = DQI × M           (σ proven)
                       AC = INDETERMINATE      (σ unproven)

- **Units:** dimensionless. **Domain:** `DQI,M ∈ [0,1]∪{N/A}`. **Range:** `[0,1]∪{None}`.
- **Derivation of M:** `dq_raw > 1` means the actual "beat" the theoretical
  optimum — physically impossible, signalling wrong mapping/specs. The fraction
  of the reported actual that is physically explainable is exactly
  `EDV_optimal/EDV_actual = 1/dq_raw`. Derived, not a constant. Negative
  `dq_raw` (value-destructive dispatch) is a legitimate finding → `M=1`.
- **Why product, not geometric mean (correction, v1):** `geomean(DQI,1)=√DQI > DQI`
  would let perfect consistency RAISE confidence above data quality — indefensible.
  The product gives the correct boundaries: `M=1 ⟹ AC=DQI` (data-limited);
  `M→0 ⟹ AC→0`; `AC ≤ min(DQI,M)`. It is a product of **two** evidence factors
  (not DQI alone).
- **Independence:** AC never references Forecast Reliability.
- **Edge/failure:** unproven solver ⟹ INDETERMINATE (no invented penalty for an
  unknown MIP gap). `DQI None` (direct-JSON audit) ⟹ AC falls back to `M`.

## 2A. Decision Quality (DQ) — archetype-aware definition (Phase 2 amendment)

DQ measures how close the *actual* operation was to the *cost/value-optimal* one.
Its algebraic form depends on the physics archetype, because a generation asset
earns **revenue** while a consumption asset avoids **cost**:

    Generation (storage / intermittent / dispatchable) — value/revenue space:
        DQ = EDV_actual / EDV_optimal          (unchanged; v1 definition)
        where EDV = (price − marginal_cost) · dispatch

    Load (consumption — furnaces, motors, pumps, electrolyzers, desalination) —
    COST space:
        DQ = C_optimal / C_actual              (Phase 2)
        C_x = Σ_t price(t) · load_x(t) · Δt
        C_optimal = min-cost delivery of the SAME total energy, reallocated to the
                    cheapest feasible hours (capacity-constrained greedy fill).

- **Bounds:** load DQ ∈ [0,1] by construction — the cheapest-hours reallocation can
  never cost MORE than actual, so `C_optimal ≤ C_actual`. DQ=1 ⟺ perfect timing.
- **Economic Gap is invariant:** `G = C_actual − C_optimal ≡ EDV_optimal − EDV_actual`
  (the savings gap), because total energy is conserved so the peak-price reference
  terms cancel in aggregate. Only the DQ *ratio* differs between the two spaces.
- **Why the amendment:** the v1 savings-ratio (`EDV_act/EDV_opt`, value-vs-worst-hour)
  and the cost-ratio answer different questions for a load. The cost-ratio is the
  definition used in the hand-validated Muscat Steel Melting Co. audit (DQ 0.91), and
  is the intuitive "what fraction of the theoretical-minimum bill did you achieve?".
- **Scope:** LOAD archetype only. Generation DQ is unchanged. `AC`'s Model-Consistency
  `M` still reads `dq_raw`; for loads `dq_raw = C_optimal/C_actual ≤ 1 ⟹ M = 1`.

## 3. Forecast Reliability — `EDA-FR-1.0-experimental` (REPORT-ONLY)

    FR = 1 − min(1, MAPE),   MAPE = mean( |forecast − price| / max(|price|, ε) )

- Measures accuracy of a **supplied** forecast model. **N/A** when no forecast
  column. **Not** used to weight Audit Confidence in v1 (pending multi-asset
  validation). Flagged `Experimental – Not part of EDA Standard v1.0`.

## 4. Grade scale — `EDA-GRADE-1.0` (declared, normative)

`A ≥ 0.90 · B ≥ 0.75 · C ≥ 0.60 · D ≥ 0.40 · E < 0.40 · N/A · INDETERMINATE`

These cut-points are a **declared grading scale** (a communication layer over
the numeric value, analogous to a conformity-grade scale) — **not** empirically
derived and carrying no statistical claim. The numeric value is the primary
reproducible quantity. Band A aligns with the published 0.90 risk threshold.
Revisable in EDA Standard v1.0.

## 5. Data Quality Manifest

The raw integer evidence every metric above is derived from. Emitted on every
file audit (`AuditResponse.data_quality_manifest`), linked to the C2 chain of
custody by `dataset_sha256`. Keys: `n_rows_raw, n_expected_steps,
n_present_steps, n_missing_steps, n_unparseable_timestamps,
n_duplicate_timestamps, n_out_of_order_timestamps, n_price_missing_interpolated,
n_negative_price_steps, n_soc_present, n_soc_physics_violations,
n_telemetry_rows, n_telemetry_degraded, n_forecast_present,
detected_interval_sec, timezone_assumed, span_hours, dataset_sha256`.

## 6. Asset-agnostic conformance

The equations are identical for BESS, Solar, Wind, CHP, Gas Turbine, Combined
Cycle, Hydro, Pumped Hydro, Grid and industrial loads. Worked N/A cases:
- **Solar (no SoC/comms/forecast):** `A = {C,T,P}`; S,H,F = N/A.
- **Direct-JSON (no timestamps):** `A = {P}` (+ any present optional); C,T = N/A.
- **Ibri2 (all present):** all six applicable → DQI 98.7% / Grade A.

## 7. Versioning & reproduction

Every metric exposes `name, version, equation, inputs, outputs, dependencies,
validation_rules` via `GET /api/v1/metrics/registry`. To independently
reproduce any published DQI/AC: read the Data Quality Manifest, apply §1–§2.
