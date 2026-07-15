# PREDAIOT Language Registry — LR-1.0

**Status:** PROPOSED — awaiting ratification. Normative annex of PL-1.0 (the
lexicon). Append-only after ratification.
**Purpose:** The single source of truth for every word the product speaks. It
fixes the **canonical term** for each concept, its **API binding** (frozen
backend), its **value class / state**, and the **forbidden synonyms** it
replaces. Under L1 (one meaning, one word), a concept has exactly one term.
**Rule of registration:** No term renders in the product unless it appears
here as *canonical* or *allowed*. A term without an API binding cannot be
canonical (L3). New terms enter only by ratified amendment.
**Enforcement:** the "Forbidden" column is a grep set for the Language Gate
(PL-1.0 §2).

---

## 1. Economic terms (money) — bound to value classes (SPEC-EV)

| Concept | Canonical term | API field | Value class | Forbidden synonyms |
|---|---|---|---|---|
| Money lost this period | **Financial Leakage** / "value left unrealized" | `total_gap_usd` | lost | "Destroyed Value", "Gap" (bare), "wasted value", "money burned" |
| Winnable value | **Recoverable Value** / "recoverable execution gap" | `recoverable_execution_gap` · `gap_attribution.execution_gap` | recoverable | "savings", "potential", "opportunity value" (bare) |
| Not operator-attributable | **Forecast-unreachable** | `gap_attribution.forecast_gap` | benchmark context | "unavoidable loss", "noise" |
| Value actually captured | **Captured Value** / "protected" | `edv_actual_total` | protected | "earned", "realized revenue" (bare) |
| Perfect-foresight bound | **Theoretical ceiling** (always: "benchmark, not a target") | `edv_optimal_total` | **not a value class — context** | "target", "goal", "achievable" (bare), "potential revenue" |
| Realized post-execution value | **Realized value** | EDA-OUT outcome record | saved / verified | "actual savings" (before governance) |
| Live provisional exposure | **Money at risk** (PROVISIONAL) | live economic state | at-risk | "current loss" (as certified) |
| Governance-confirmed value | **Verified value** | EDA-GOV verified outcome | verified | "confirmed savings" (before verdict) |

Money is formatted per ED-1.0 §3. Currency from `currency` (default USD).

## 2. Decision-health & state terms

| Concept | Canonical term | API field | Color (PL-CO) | Forbidden |
|---|---|---|---|---|
| Capture efficiency | **Economic Capture Fraction (ECF)** / "% of achievable value captured" | `dq_score` (0–1) | risk-band | "efficiency" (bare), "score" (bare), "DQ" as money |
| Decision posture | **Decision Health** + risk band | `risk_level` (Low/Moderate/Severe) | recover/warn/loss | "status", "grade" (for risk) |
| Risk band values | **Low** / **Moderate** / **Severe** risk | `risk_level` | recover/warn/loss | "Critical" (use Severe), "OK", "Good" |
| Data quality | **Data Quality — Grade {A–E} · {n}%** | `data_quality_index.{grade,value_pct}` | grade | "DQ Score" (as money), "completeness %" (fabricated) |

## 3. Decision & governance terms

| Concept | Canonical term | API field | Forbidden |
|---|---|---|---|
| Machine recommendation | **PREDAIOT Recommendation** | `opportunities[0]` (non-experimental) | "AI suggests", "we recommend" (bare), "tip" |
| Decision type | **CORRECTIVE / OPTIMIZATION / RECOVERY / MONITORING** | decision `decision_type` | ad-hoc type names |
| Non-quantified action | **EXPERIMENTAL** (quarantined) | `opportunities[].experimental` | "beta", "advanced", hiding it |
| Alternatives | **Alternative Decisions** | remaining `opportunities[]` | "other options" (bare) |
| Lifecycle state | **PROPOSED / ACCEPTED / IN_EXECUTION / EXECUTED / DEFERRED / REJECTED** | EDA-DEC-LIFE record | "pending", "done", "cancelled" |
| Governance verdict | **VERIFIED / REJECTED / INCONCLUSIVE / PENDING** | EDA-GOV record verdict | "approved", "passed", "OK" |
| Recommended value | **Expected Impact / Expected Outcome** ("recorded this period") | `opportunities[].period_gain` | "Expected Annual Gain", "projected return" |

## 4. Confidence & evidence terms

| Concept | Canonical term | API field | Forbidden |
|---|---|---|---|
| Audit confidence | **Audit Confidence — Grade {A–E} · {n}%** | `audit_confidence.{grade,value_pct}` | fabricated "Evidence Level HIGH/MEDIUM" |
| Indeterminate confidence | **INDETERMINATE** (honest state) | `audit_confidence.grade === 'INDETERMINATE'` | inventing a grade, hiding it |
| Grade scale | **Grade A / B / C / D / E** | `*.grade` | stars, numeric 1–5 for grades |
| Dataset identity | **Dataset SHA-256** (truncated + copy-full) | `audit_manifest.input_sha256` · `data_quality_manifest.dataset_sha256` | "checksum" (bare), full hash inline |
| Evidence line | **Evidence ·** {recorded ledger basis} | `opportunities[].evidence`, `root_causes[]` | invented evidence, "proven" |
| Method line | **Method ·** {derivation} (footnote) | `opportunities[].derivation` | "formula", presenting as headline |
| Provenance | **CERTIFIED** (batch) / **PROVISIONAL** (live) | dataSource + EDA-RECON semantics | conflating the two |
| Certificate | **EDPC — Economic Decision Performance Certificate™** | `/api/v1/certificate` | "score card", "rating badge" (bare) |
| No artifact | **"None — JSON audit input (no file manifest)"** | (absence of `input_sha256`) | silence, fabricated hash |

## 5. Temporal & projection terms (the C2 lexicon)

| Allowed (recorded) | Forbidden (forward / projected) |
|---|---|
| "recorded this period", "this period", "the audited period" | "annualised", "annual", "per year", "/yr", "12-month" (as headline) |
| "recorded rate", "recorded recoverable value" | "projected", "forecast" (as a claim), "expected to", "will lose" |
| the mandated basis line (ED-1.0 §8) | "× 365", "linear estimate" (as a displayed value on a decision surface) |

Exception: the **Math Appendix** may *document* the ALP annualization formula
as disclosed methodology (basis-labeled), never as a headline economic claim.

## 6. Product-identity terms (SPEC-CA)

| Allowed | Forbidden as self-description |
|---|---|
| "Economic Decision Intelligence", "Executive Economic Command Center", "Executive Briefing" | "dashboard", "analytics", "monitoring", "BI", "SCADA", "EMS", "IoT", "digital twin" |
| "Decision Instrument" (IN-xx) | **"chart"**, "graph", "widget", "visualization" (in product copy) |
| "Decision", "Evidence", "Audit", "Recommendation" | "KPI" (as a displayed noun), "metric card", "tile" |

## 7. Banned constructs (grep set)

- **Emoji & dingbats** in product surfaces (`✦ ✔ ⚡ 🏆 🟢 🟡 🔴 ⬇ ⎆ ⎋ ☰ 📊`) — icons are minimal geometric line forms with a text label (SPEC-ID iconography).
- **Exclamation marks** in product copy (ED-1.0 §1).
- **Hype adjectives**: "massive", "huge", "amazing", "incredible", "game-changing".
- **First-person AI**: "I found", "I think", "Let me" — the platform *states*, it does not chat (SPEC-AI voice).
- **Fabricated constants** rendered as data: any literal % / "Yes" / label not sourced from an API field (P2/FM-1).
- **Native `alert()` / `confirm()`** — institutional surfaces only (PL-ER).
- **Bare `$` for non-USD** currencies; **parenthesized negatives** for loss (use the loss color).

## 8. Registration & change

Every new term: propose → bind to an API field (or mark reference-only) →
classify (canonical / allowed / forbidden) → ratify → append here. The
registry never redefines a canonical term in place; superseded terms move to
the Forbidden column with a pointer to their replacement.

---

*End of LR-1.0. The words the product is permitted to speak — bound to truth,
one meaning to one word.*
