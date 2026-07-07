# Removed Heuristics Register — C1 No-Fabrication Purge

Every fabricated coefficient, weight, confidence score, magic constant, or arbitrary
multiplier removed from PREDAIOT's customer-facing outputs, with its replacement
derivation. Rule applied: **Recorded Evidence → Mathematical Formula → Reproducible
Calculation → Presentation.** If a value could not be derived from recorded evidence
it was removed or flagged `Experimental – Not part of EDA Standard v1.0`.

Line numbers refer to the file state at commit `c174401` (immediately before the purge).

## Backend — `backend/main.py`

| # | Location | Previous implementation | Why scientifically invalid | Replacement |
|---|---|---|---|---|
| 1 | `_classify_decision` (~821) | Per-class confidence constants 0.96 / 0.85 / 0.92 / 0.78 / 0.70 and `min(0.99, 0.80 + price/200)` | Confidence values invented per class; price term dimensionally meaningless | Confidence = `None` everywhere (ledger column removed). Classification thresholds (0.5 MW tolerance, 5 MW materiality) retained as documented **normative taxonomy definitions** |
| 2 | `_build_root_causes` (~875) | `cats["Curtailment"] += gap * 0.15` secondary tag | 0.15 factor fabricated; double-counted gap already attributed to another category (percentages could exceed 100%) | Exact partition: every positive `gap_step` attributed to exactly one category via `_root_cause_bucket`; `contribution_pct = loss(cat) / Σ loss × 100` (sums to 100.0 by construction). Curtailed energy reported separately as descriptive `curtailed_energy_mwh = Σ curtailment_mw × Δt` |
| 3 | `_build_root_causes` | "SOC Constraint" category (never populated) | Dead category implying an analysis that does not exist | Removed |
| 4 | `_opp` / `_ops_storage` / `_ops_intermittent` / `_ops_dispatchable` / `_ops_load` (~891–1101) | Opportunity values = fixed shares of the gap (0.28/0.35/0.18/0.12/0.07; 0.38/0.24/0.14/0.14/0.10; 0.40/0.18/0.14/0.16/0.12; 0.42/0.22/0.14/0.12/0.10; override 0.08) | Shares invented; the same gap money was allocated to ideas (reserve markets, hedging) that the audited data cannot evidence at all | `period_gain = Σ gap_step` over ledger rows whose classification maps to the opportunity's bucket; each item carries a `derivation` string with the exact filter. Non-derivable ideas kept as text-only, flagged `Experimental – Not part of EDA Standard v1.0`, **no numbers** |
| 5 | same | `confidence_pct = min(99.5, 85 + (missed/total)·15)` and 9 similar formulas; static values 92.4/97.1/88.7/91.0/88.6/86.2/81.4/91.7/90.4/89.0/83.0/90.5/87.2/84.6/82.0/94.2 | Statistical-confidence formulas with no statistical basis | Field withdrawn (`None`) |
| 6 | same | `priority_score` (100/98/94/92/88/85/84/82/80/78/76/72/68/64/62), `priority_stars` (3–5), `payback_days` (0–730), `operational_risk` labels | Investment-grade priority and payback figures invented per card | Fields withdrawn (`None`); items ordered by derived `period_gain` |
| 7 | `_opp` | `efficiency_gain_pct = annual·share / total_gap × 100` | Percentage of a fabricated allocation | Withdrawn; replaced by `share_of_positive_gap_pct = period_gain / Σ positive gap × 100` (derived) |
| 8 | `_build_heat_map` (~1155) | Severity bands `gap < price×1` / `gap < price×5` | Multipliers 1 and 5 fabricated; banding not comparable across datasets | Percentile banding from the audit's own positive-gap distribution: acceptable ≤ P50, poor ≤ P90, critical > P90 (documented in the function) |
| 9 | `_build_eda_metrics` (~1183) | EIS composite `0.45·EDE + 0.30·DA + 0.15·FUI + 0.10·(1−ELR)` | Weights unvalidated; EDE ≡ DQ made the composite a DQ-weighted-twice signal | Withdrawn (`economic_intelligence_score = None`) |
| 10 | same | `decision_delay_index = overrides/total × 10` | ×10 scale invented; name implies latency measurement that never happened | Withdrawn; replaced by derived `override_rate_pct = overrides/total × 100` |
| 11 | same | `revenue_stacking_index = 2 if fui > 0.3 else 1` | Ordinal invented from an unrelated ratio with a fabricated 0.3 threshold | Withdrawn (`None`) |
| 12 | same | `battery_opportunity_capture = dispatch_accuracy` (BESS/Hydro only) | Existing metric re-published under a misleading name | Withdrawn (`None`) |
| 13 | same | `curtailment_recovery_ratio = Σ curtailment_mw` labeled "MWh potentially rescued" | Unit error (MW·steps, not MWh) and "rescuable" claim unsupported | Replaced by `curtailed_energy_mwh = Σ curtailment_mw × Δt`, labeled descriptive |
| 14 | `_build_ai_commentary` (~1252) | `recoverable = pct × 0.68`; "Annual Recovery" = gap × 365 × 0.68 | 0.68 underived | Recoverable = exact Ch 8.2 execution gap when a forecast column exists; otherwise stated as not isolatable |
| 15 | same (~1251) | `rating_word` CRITICAL/MODERATE/STRONG at dq 0.4/0.7 | Ad-hoc thresholds duplicating the published risk bands | Uses the published `_risk_level` DQ thresholds (Ref. Manual Vol III) |
| 16 | same (~1255) | `top_cause_pct` fallback `35` | Invented default percentage | `None`, with honest empty-state sentence |
| 17 | same | "No hardware limitations were detected"; "asset is operationally healthy" | Claims outside the audit's evidence base | Rewritten: hardware/availability causes explicitly out of scope |
| 18 | `_eda_rating` (~2932) | AAA–CCC composite: weights 40/30/20/10, governance fallback `8.0`, `gov = 10 − delay×2`, rating thresholds every 10 points | Entire construct unvalidated | **Rating withdrawn entirely** (per hardening constraint 4 it is NOT re-derived from DQ). All rating keys return `None` / "Withdrawn — pending EDA Standard v1.0 definition". Certificate & UI display the withdrawal notice; DQ (validated) shown instead |
| 19 | `_build_certificate` | `rating_components` (40/30/20/10 breakdown), `eis_score`, grading narratives ("Outstanding"… "Critical") | Followed the withdrawn rating | Removed; factual narrative states DQ, ceiling gap, recoverable gap, risk band, and the withdrawal |
| 20 | `_build_certificate` | `"methodology": "… (patent-pending)"` | No evidence of a patent filing | Claim removed |
| 21 | `_live_decision_core` (~2968) | `decision_quality = min(150, ratio·100)`; else-branch `100 − |gap|` | 150% cap arbitrary; else-branch subtracts money from a percentage (dimensional error) | Ch 4.2 domain rules, clamped [0, 100] |
| 22 | same (~2978) | `severity = HIGH/MEDIUM/LOW` at gap > $100 / > $20; `alert = gap > 100` | Absolute money thresholds fabricated and currency-blind | Severity withdrawn; derived `gap_pct_of_optimal` published; `alert` redefined as the documented display policy "gap > 50% of the step's own optimal value" |
| 23 | ledger CSV export | `confidence` column | Carried heuristic #1 | Column removed |

## Frontend — `frontend/src/App.jsx`

| # | Location | Previous implementation | Why invalid | Replacement |
|---|---|---|---|---|
| 24 | S02 Economic Value Flow | Stages ×0.92 ("grid constraints"), ×0.87 ("SOC range"), ×0.97 ("settlement losses"), ×0.12 ("unrecoverable") | Multipliers fabricated; presented as computed pipeline stages | Only computed stages: Theoretical Ceiling, Forecast-Unreachable / Recoverable Execution (Ch 8.2) or Ceiling Gap, Captured Value |
| 25 | `AssetPerformanceTiles` | `availability = max(85, 100 − override%)`; `MTD Revenue = period × 30`; discharge/charge ratio (structurally undefined for file audits) | Availability formula and 85 floor invented; "MTD" implies actuals; ratio divides by a column that is always ~0 | Tiles: EDE, Override Rate, Curtailed Energy (MWh), Captured Value (period) — all ledger-derived |
| 26 | S01 telemetry | Placeholder SoC 68%, Power 120 MW, Temp 24 °C | Fabricated sensor readings | '—' when the channel is absent |
| 27 | S09 header | "Portfolio Confidence" = mean of fabricated per-item confidences; "1–8 weeks"/"1–3 months" timelines | Aggregating invented numbers; invented timelines | Period gap attributed (Σ), annualised (labeled linear est.), quantified-action / interval / advisory counts |
| 28 | S09 cards | Confidence, Priority Score /100, Payback days, Risk chips | Displayed heuristics #5–6 | Period value, annualised (linear est.), intervals, share of positive gap, derivation string, EXPERIMENTAL badge |
| 29 | S10 status box | "Recoverable Revenue" = (100 − capture)·0.68; "Annual Recovery" = gap×365×0.68; "Audit Confidence" = dispatch accuracy relabeled | 0.68 underived; metric mislabeled as confidence | Ch 8.2 recoverable execution gap (or ceiling gap labeled as such); Dispatch Accuracy and Forecast Coverage under their real names |
| 30 | S11 "Compliance Checklist" | PASS verdicts for "Market rules observed", "SOC limits respected" (hard-coded true), "Dispatch policy followed" (dq > 0.6), "Revenue optimization active" (dq > 0.5) | Verdicts on properties never checked; invented DQ thresholds | "Recorded Audit Facts": counts and percentages read from the ledger, no verdicts |
| 31 | S13 live tiles | "Confidence %" and "SEVERITY" pills | Displayed heuristics #1/#22 | "Gap % of Step Optimum" (derived) + documented alert policy pill |
| 32 | S14 certificate view | AAA badge, composite /100, 40/30/20/10 composition bars, EIS score | Displayed heuristic #18–19 | DQ dial + risk band + explicit "Rating withdrawn pending EDA Standard v1.0" panel |
| 33 | Math Appendix S12 | EIS formula presented as methodology | Documented a withdrawn construct as current | Entry marked WITHDRAWN with the reason |
| 34 | Methodology modal | "ranks … by payback period and confidence score"; "Patent-Pending … patent filing" | Described removed heuristics; unverified patent claim | Describes ledger-derived ranking; patent claim removed |

## Landing — `landing/`

| # | Location | Previous | Why invalid | Replacement |
|---|---|---|---|---|
| 35 | `SocialProofSection` | Five invented company names under "Trusted by…" | Implies customers that do not exist | Asset-class capability chips under "Built for…" |
| 36 | `ProofSection` | "-$1,205 / hour Live Leakage Detected" implying a measurement | Illustrative number presented as live data | Caption added: "Illustrative demo figure — not measured data" |
| 37 | `HeroSection` / `i18n.ts` (fixed in commit b7ee031/98a3ae7) | "ISO 27001 Compliant", "Bank-Level Encryption" | Certification claim without certification | "ISO 27001-Aligned Controls", "TLS-Encrypted Transfers" (EN/FR/AR) |

## Retained parameters (documented policy, not fabricated results)

- Classification thresholds 0.5 MW / 5 MW — **normative taxonomy definitions**, published.
- `_risk_level` DQ bands 0.90 / 0.70 — published War-Room thresholds (Ref. Manual Vol III).
- MILP SoC bounds [0.10, 0.95] and CBC time cap 45 s — optimization model parameters, disclosed.
- Live advisory hold/dispatch hints at forecast ±15% — advisory policy text triggers (produce words, not numbers); documented in code.
- Demo simulator constants — synthetic by declaration, never presented as measurements.
