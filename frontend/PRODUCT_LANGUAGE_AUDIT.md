# PREDAIOT Product Language Audit — PLA-1.0

**Status:** AUDIT (findings + roadmap). Derives entirely from PREDAIOT-FE-2.0
(RATIFIED); introduces no new philosophy. Governed like the EDA contracts.
**Purpose:** Elevate PREDAIOT from *one screen that speaks the language* (S01,
the six-act Executive Briefing) to *one product that speaks one language* on
every screen — a recognizable operating language of Economic Decision
Intelligence.
**Constraints:** Backend frozen. APIs frozen. Data integrity, evidence
integrity, and all ratified contracts preserved.
**Reference dialect:** S01 (`components/ExecutiveCommandCenter.jsx`) is the
canonical speaker. Every finding is measured against it and its governing
specs.

---

## 1. Method — the Five-Question communication test

A screen *speaks the PREDAIOT language* only if it answers all five, in the
briefing's own voice (SPEC-ST, SPEC-DL, SPEC-AI):

1. **Executive Question** — which registered question (SPEC-QA Q1–Q9) does it answer?
2. **Decision** — what decision does it support?
3. **Evidence** — what verifiable evidence does it expose (SPEC-TM/SX)?
4. **Economic Consequence** — what money does it name, in which value class (SPEC-EV)?
5. **Required Action** — what should follow?

> A screen that cannot answer all five is a *dashboard fragment*, not a
> briefing page. It does not yet speak the language.

Communication is judged, not components: two screens with identical widgets
can speak differently, and the same fact can be a fragment on one screen and a
sentence on another.

---

## 2. The Product Language Matrix

Legend — **Speaks:** ✅ full · ◑ partial · ✖ fragment.
"Instrument" cites the SPEC-CH registry (IN-xx) where one applies.

| Section (group) | Q (SPEC-QA) | Decision | Evidence | Economic Context (SPEC-EV) | Primary Instrument | Narrative Position (SPEC-ST) | Visual Weight | Confidence Surface | Governance Surface | Required Action | Speaks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **01 Executive Summary** (COMMAND) | Q1–Q9 | The whole loop | Full evidence chain (Act V) | lost / recoverable / protected / benchmark | IN-01, IN-04, IN-06, IN-13 | **Six acts, spine** | Dominant per act | DQI/AC grade + INDETERMINATE | provenance badge | Act IV recommendation | ✅ REFERENCE |
| **02 Economic Value Flow** (ANALYSIS) | Q5/Q1 | Understand loss composition | Computed stages, labeled | captured / execution gap / forecast-unreachable / ceiling | IN-04 (unregistered form) | none | centered 560px column | none | none | none | ◑ |
| **03 Decision Audit Trail** (ANALYSIS) | Q5 | Judge individual decisions | Per-decision ledger rows | per-step gap | decision cards (unregistered) | none | flat card stack | none | none | none | ◑ |
| **04 Root Cause Analysis** (ANALYSIS) | Q5 | Target the failure mode | contribution % + loss | root-cause losses | IN-06 Leakage Flow ✓ | none | single exhibit | none | none | none | ◑ |
| **05 Counterfactual Simulation** (ANALYSIS) | Q5 | Trust the benchmark | optimal vs actual series | ceiling vs captured | IN-13 companion (DispatchCurve) | none | 3 KPI cards + chart | none | none | none | ◑ |
| **06 EDA Metrics** (ANALYSIS) | Q3 (weak) | — (none stated) | none | mixed % metrics | 6 metric cards (**widget grid**) | none | equal-weight grid | grade colors only | none | none | ✖ |
| **07 Financial Leakage** (ANALYSIS) | Q1 | Size the loss | financial-impact tiles | lost / recoverable | IN-13 (leakage history) | none | tiles + chart | none | none | none | ◑ |
| **08 Decision Heat Map** (ANALYSIS) | Q5 | See when decisions degrade | per-slot quality | per-slot gap | IN-12 Executive Heatmap | none | grid | color legend only | none | none | ◑ |
| **09 Economic Action Plan** (ACTION) | Q4 | Choose a recovery action | Evidence/Derivation per card | recoverable **+ ANNUALIZED** ⚠ | opportunity cards + KPI header | none | portfolio KPI header + cards | none | none | per-card (implicit) | ◑ (integrity ⚠) |
| **10 Economic Intelligence Report** (ACTION) | Q5/Q6 | Independent assessment | **FABRICATED strip** (99.8% / ✓Yes) ⚠ | mixed | prose block + 5 KPI cards | prose only | KPI grid + report | risk pill | none | "Deep analysis" button | ✖ (integrity ⚠) |
| **11 Governance** (EVIDENCE & GOV) | Q6 | Understand authority tiers | framework description | override impact | framework cards | descriptive | card cluster | none | **verdict language** | none | ◑ |
| **CT EDPC Certificate** (EVIDENCE & GOV) | Q6 | Obtain proof artifact | certificate + registry no. | DQI/ECF on cert | certificate document | none | document | grades on cert | seal | Generate certificate | ◑ |
| **HX Audit History** (EVIDENCE & GOV) | Q8 | Compare periods/assets | history rows | daily gap series | IN-13 / IN-11 (unregistered) | none | table + chart | none | none | Sync history | ◑ |
| **LV Live Monitor** (OPERATIONS) | Q7 | Watch live economics | live buffer, PROVISIONAL | at-risk (provisional) | IN-07/IN-13 (live) | none | strips + charts | live DQ score | PROVISIONAL badge | Connect / simulate | ◑ |
| **RT Real-Time** (OPERATIONS) | Q7 | Provisional intelligence | provisional state | at-risk | strips | none | strips | provisional | PROVISIONAL | none | ◑ |
| **12 Math Appendix** (REFERENCE) | reference | Verify methodology | formulas + versions | (context strip owed) | formula blocks | reference | prose/formulas | methodology versions | none | none | ◑ (reference) |

**Verdict:** exactly **one** section (S01) speaks the language in full. Two
(EDA Metrics, Intelligence Report) are outright fragments. The rest are
*partial* — they answer their Executive Question but drop Narrative, Required
Action, and a consistent Confidence/Evidence voice, and they render in the
legacy widget vocabulary rather than the briefing vocabulary.

---

## 3. Inconsistency register (classified)

Classification: **Critical** (breaks Economic Truth / Evidence integrity, or
makes a screen unintelligible as a briefing) · **Major** (breaks language
coherence across screens) · **Minor** (local voice slip) · **Cosmetic**
(surface detail). Each carries the gap-report fields.

### CRITICAL

**C1 — Fabricated evidence in the Intelligence Report (S10).**
- Current: renders hardcoded constants as evidence — `SCADA Completeness 99.8%`,
  `MILP Validated ✓ Yes`, `Evidence Level HIGH/MEDIUM` (App.jsx S10 evidence strip)
  — none from the API.
- Desired: expose only real artifacts (manifest hash, DQI/AC grades, `log.length`);
  remove invented constants.
- Spec: **P2 Economic Truth, FM-1 "never guesses", SPEC-TR, SPEC-SX**.
- Priority: P0. Impact: highest — it is a truth violation on an "independent
  assessment" screen. Dependencies: none (deletion + real-field swap).

**C2 — Annualized figures presented as headline value (S09, S10).**
- Current: Action Plan portfolio header shows `Annualised (Linear Est.) =
  periodTotal × 365`; each opportunity card shows `annual_gain_usd`; the
  briefing (S01) already bans this.
- Desired: recorded-period value only, with the basis disclaimer; annualized
  numbers removed from display (the API field may exist; it must not render).
- Spec: **SPEC-AI rule 5, SPEC-QA Q9, FM-2 "never exaggerates", SPEC-EV**.
- Priority: P0. Impact: high — inconsistent economic vocabulary and a
  forward-projection the platform disavows. Dependencies: none.

**C3 — Native `alert()` dialogs as the error/empty/success voice.**
- Current: 6 `alert(...)` calls (upload validation, "Run an audit first.",
  "Link copied!", "PDF generation failed…").
- Desired: institutional in-place surfaces — the ratified error strip (already
  built in App shell), inline empty states, quiet confirmations (SPEC-IX).
- Spec: **SPEC-IX rules 2/4, SPEC-ID Error/Success/Empty-State language, P4**.
- Priority: P0. Impact: high — breaks the calm institutional voice instantly.
  Dependencies: reuse the existing `actionError` surface + a toast primitive.

### MAJOR

**M1 — Two money formatters (economic vocabulary fork).**
- Current: legacy `fmtMoney`/`fmtUSD` in App.jsx (compact `$1.2k`) vs the
  design-system `fmtMoney` in `ds.js` (`1.2K USD`). Screens disagree on how
  money reads.
- Desired: one institutional money voice everywhere (the ds.js formatter).
- Spec: **SPEC-DS rule 3 (one formatting path), SPEC-ID Financial Typography**.
- Priority: P1. Impact: high — money is the native language; it must not have
  two accents. Dependencies: none (re-point legacy calls).

**M2 — Legacy widget vocabulary across 15 sections.**
- Current: `Card`/`BigNum`/`Label`/`Pill` + inline `DS` styles render equal-
  weight boxes; S01 uses `Panel`/`.pds-num`/`.pds-kicker` + the act spine.
- Desired: the briefing vocabulary — `Panel`, kickers, mono numerals, the
  standfirst header, alternating containment — as the shared surface language.
- Spec: **SPEC-ID Visual Rhythm/Card/Panel Language, SPEC-CO, SPEC-DL**.
- Priority: P1. Impact: this *is* the "belongs to the same OS" gap.
  Dependencies: SPEC-CO component consolidation (retire the legacy bridge).

**M3 — No Narrative Position or Required Action on any analysis/action screen.**
- Current: sections open with a title and dive into widgets; none states its
  executive question on screen, none closes with an action (SPEC-ST beats 4/6
  absent everywhere but S01).
- Desired: every screen carries a one-line **standfirst** (question stated) and,
  where it supports a decision, a closing action line — the briefing spine at
  section scale.
- Spec: **SPEC-ST, SPEC-DL, SPEC-IA (one primary question), SPEC-PR Existence Test**.
- Priority: P1. Impact: highest for "coherent language". Dependencies: none.

**M4 — Money-First Law unobserved on non-monetary sections.**
- Current: Metrics, Heat Map, Governance, Appendix, History open without the
  Economic Context Strip; money does not lead.
- Desired: a persistent condensed leakage/recoverable/health strip atop every
  non-monetary section (SPEC-DL rule 1).
- Spec: **SPEC-DL Money-First Law**. Priority: P1. Impact: high. Dependencies:
  a shared `EconomicContextStrip` component (SPEC-CO registration).

**M5 — Inconsistent Evidence & Confidence surfaces.**
- Current: S01 = evidence-as-jewelry ledger + DQI/AC grades + INDETERMINATE;
  S09 = gray "Evidence:/Derivation:" inline; S10 = fabricated strip; others =
  nothing. Confidence appears as a grade, a pill, a color, or absent.
- Desired: one Evidence Language (hash chips + grade + honest absence) and one
  Confidence Language (grade + % + INDETERMINATE) reused verbatim.
- Spec: **SPEC-ID Evidence/Confidence Styling, SPEC-TM, SPEC-SX, SPEC-AI**.
- Priority: P1. Impact: high (trust must look the same everywhere).
  Dependencies: `EvidenceBadge`/`EvidenceRow`/`GradeBadge` as shared primitives.

### MINOR

**N1 — SectionHeader casing/voice drift.** Some titles ALL-CAPS ("REAL-TIME
ECONOMIC INTELLIGENCE"), some Title Case; trademarks (™) uneven. Desired: one
title voice (Title Case name + optional kicker), consistent ™ usage. Spec:
SPEC-ID Typography. Priority P2.

**N2 — Loading voice varies.** "OPTIMIZING…", "GENERATING…", "QUERYING…",
"SYNC HISTORY" plus one skeleton (S01). Desired: skeletons shaped like the
incoming content + one engine phrase vocabulary (SPEC-ID Loading language,
SPEC-IX). Priority P2.

**N3 — Empty-state voice varies.** `EmptyMsg` one-liners vs S01's directive
absence. Desired: one empty-state pattern (what's absent + the one action).
Spec: SPEC-ID Empty-State language. Priority P2.

### COSMETIC

**K1 — Residual dingbat glyph `✦` on the Deep-Analysis button** (S10). Spec:
SPEC-ID iconography (no decorative glyphs). Priority P3.
**K2 — Ad-hoc gradient panel backgrounds** (opps portfolio header uses a green
gradient) vs the token surface language. Spec: SPEC-ID Surface/Shadow.
Priority P3.
**K3 — `pre`-formatted report text** (S10) at line-height 2.0 vs the editorial
prose scale. Spec: SPEC-ID Editorial. Priority P3.

---

## 4. The PREDAIOT Product Language (governed, derived from FE-2.0)

Not components, not CSS — the **language**. Each dialect below is *derived*
from a ratified spec (cited); nothing here is new philosophy. These are the
rules every screen must obey to sound like PREDAIOT.

| Language | The rule (how PREDAIOT speaks) | Derives from |
|---|---|---|
| **Executive Typography** | Two voices only — Inter for prose, JetBrains Mono for every number, hash, and grade. Answers are 800-weight; context is 400–600. Money and IDs are always mono. | SPEC-ID, SPEC-DS |
| **Economic Color** | Rose = money lost; green = recovered/verified/protected; amber = caution/provisional; teal = PREDAIOT intelligence speaking; gold = certification. Saturation < 10% of any screen. Color is meaning, never decoration. | SPEC-DS, SPEC-EV, SPEC-ID |
| **Evidence** | Evidence is jewelry: truncated mono hash chips with copy-full, adjacent to the figure they certify; honest absence ("None — JSON audit input") over silence. | SPEC-SX, SPEC-TM, SPEC-ID (P7) |
| **Decision** | A recommendation is never bare: designation + reasoning + evidence + confidence + expected impact + alternatives. A decision is text; its worth and proof follow it. | SPEC-AI |
| **Motion** | Only four verbs: rise (content arrived), count-up (money changed), pulse (live signal), sweep (verdict). Transform/opacity only; loops only on live data; reduced-motion honored. | SPEC-MO |
| **Navigation** | The grouped instrument rail is the map; sections are the ratified taxonomy; one accent primary action; active = accent left-rule. Any section ≤ 2 interactions away. | SPEC-NV, SPEC-IA |
| **Instrument** | No "charts" — only registered Decision Instruments (IN-xx), each answering one question, with quiet hairline grids, mono axes, panel tooltips, axis truth. | SPEC-CH, SPEC-DV |
| **Confidence** | Grade letter + % where present; **INDETERMINATE** is a first-class honest state, neutral-slate, never a fake grade. | SPEC-AI, SPEC-TR, SPEC-ID |
| **Governance** | Verdicts (VERIFIED/REJECTED/INCONCLUSIVE/PENDING) and lifecycle states render as hash-linked chips — the loop as evidence, never as workflow status. | SPEC-TM, SPEC-CH (IN-09) |
| **Attention** | One primary emphasis per screen; the money answer wins the squint test; nothing below the fold competes for attention. | SPEC-DL, SPEC-HM, P10 |
| **Empty-State** | Honest + directive: name what is absent and the single action that fills it. Never sample data, never mascots. | SPEC-ID, SPEC-IX |
| **Loading** | Skeletons shaped like the incoming answer; a quiet engine phrase for compute. No spinners after first paint, no shimmer. | SPEC-ID, SPEC-IX, SPEC-MO |
| **Error** | Institutional candor in place: what failed, its impact, the recovery path. No native alerts, no stack traces, no dead ends. | SPEC-IX, SPEC-ID |
| **Success** | Understated — the artifact (certificate, badge) is the celebration. No confetti, no exclamation. | SPEC-ID |
| **Notification** | Quiet, factual, dismissible; confirms only what the surface already shows; never fabricates urgency. | SPEC-IX, SPEC-NV |
| **Selection** | Selection is a quiet state change (accent rule / tint), reversible in one interaction, keyboard-parity. | SPEC-IX, SPEC-AX |
| **Interaction** | One accent primary per view; quiet neutrals for the rest; no optimistic UI for economic data; hover never sole carrier. | SPEC-IX, SPEC-AX |
| **Information Density** | Dense evidence tables are allowed; dense *answers* are not. Density earns its place only when it reduces total effort. | SPEC-HM, SPEC-LX |
| **Editorial** | Every screen reads answer-first: a standfirst states the question, the dominant figure answers it, support follows, proof closes. Alternating containment — open pages and heavy slates, never a widget grid. | SPEC-ST, SPEC-DL, SPEC-ID, SPEC-LX |

---

## 5. Implementation roadmap — language first, redesign second

Ordered by (a) integrity risk, then (b) highest-frequency user journeys, then
(c) breadth of language coherence. **Consistency of language is prioritized
over visual redesign** — a screen may keep its layout and still be brought into
the language. Each wave is a self-contained, verifiable, committable unit under
the frozen backend.

**Wave 0 — Truth & voice triage (CRITICAL).** C1 fabricated evidence, C2
annualized figures, C3 native alerts. No new components; deletions and one
shared error/toast primitive. Restores Economic Truth and the institutional
voice everywhere at once. *(Journey: every audit path.)*

**Wave 1 — Shared language primitives (SPEC-CO).** Register and build the
reusable voice: `SectionShell` (standfirst = tag + title + question +
optional action), `EconomicContextStrip` (M4), `EvidenceRow`/`EvidenceBadge`
(M5), `GradeBadge`/`ConfidenceLine` (M5), one `fmtMoney` (M1). No screen
redesign yet — this is the vocabulary every wave consumes.

**Wave 2 — The COMMAND→ACTION journey (highest frequency).** The path an
executive walks after every audit: **Action Plan (09)** then **Intelligence
Report (10)** — rebuilt onto `SectionShell` with narrative standfirst, the
context strip, unified evidence/confidence, recorded-period money only, and a
closing action. These two carry the worst integrity + language gaps and are
walked most.

**Wave 3 — The ANALYSIS journey.** Value Flow (02), Decision Audit Trail (03),
Root Cause (04), Counterfactual (05), Financial Leakage (07), Heat Map (08),
EDA Metrics (06) — each gains a standfirst stating its question, the context
strip, registered instruments (SPEC-CH), and the shared evidence voice. Metrics
(the only ✖ fragment here) is recomposed from an equal-weight grid into a
ranked, answer-first exhibit.

**Wave 4 — The EVIDENCE & GOVERNANCE journey.** Governance (11), Certificate
(CT), Audit History (HX) — unify the Evidence/Governance/Confidence languages;
render verdicts and lifecycle as hash-linked chips (IN-09 direction);
certificate as the success artifact.

**Wave 5 — The OPERATIONS journey.** Live Monitor (LV), Real-Time (RT) — one
PROVISIONAL voice, the live instruments (IN-07/IN-13), the pulse motion verb;
never a certified figure on a live surface.

**Wave 6 — Reference + final coherence sweep.** Math Appendix (12) gains the
context strip (Money-First). Then N1–N3 (title/loading/empty voice) and K1–K3
(cosmetic) across the app; a whole-product blind-screenshot recognition pass
(SPEC-ID): every screen must read as PREDAIOT without the logo.

**Governance:** each wave that changes ratified behavior lands with a GOV-AL
amendment; each screen passes the GOV-AC checklist, the **Language Gate**
(PL-1.0 §2), and the Five-Question test before commit; the Product Language
Matrix (§2) is re-scored per wave until every row reads ✅.

**Contract layer (ratify before Wave 1).** The dialects of §4 are elevated to
a governed contract so the waves are mechanical application, not per-screen
taste:
- **`PRODUCT_LANGUAGE_SPEC.md` (PL-1.0)** — the language contract: 19 dialect
  clauses (PL-xx), the One-Language Law, the Language Gate.
- **`LANGUAGE_REGISTRY.md` (LR-1.0)** — the lexicon: canonical terms, API
  bindings, value classes, and the forbidden-synonym grep set.
- **`EDITORIAL_SYSTEM.md` (ED-1.0)** — the style manual: voice, sentence,
  number, unit, order, and per-surface copy templates.
Waves 1–6 implement PL-1.0 / LR-1.0 / ED-1.0; every screen cites the PL-xx,
LR-§, and ED-§ it satisfies.

---

*End of PLA-1.0. This audit derives wholly from PREDAIOT-FE-2.0; it defines no
new philosophy. Implementation proceeds wave by wave under the frozen backend,
prioritizing one coherent operating language over per-screen visual redesign.*
