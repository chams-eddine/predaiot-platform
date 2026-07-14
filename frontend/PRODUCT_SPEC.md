# PREDAIOT Frontend Product Specification — PREDAIOT-FE-1.0

**Status:** PROPOSED — awaiting ratification.
**Class:** Governing architectural contract. The frontend equivalent of the
certified EDA architecture. No frontend implementation may contradict this
document; deviations require a ratified amendment first.
**Authority chain:** PLATFORM_BLUEPRINT.md → this document → implementation.
**Backend:** FROZEN. Every specification below consumes existing production
APIs only. No spec may require backend change beyond what UI rendering
strictly demands (per the standing mission constraints).

---

# 0. Governing Principles

Every UI decision must be traceable to at least one principle. **If an
element cannot cite a principle, it does not exist.** Implementation reviews
reject any element without a traceable justification.

| ID | Principle | Meaning | Test |
|----|-----------|---------|------|
| **P1** | Executive Clarity | The screen answers an executive question before it does anything else | A named question is answered in < 5 seconds |
| **P2** | Economic Truth | Every number originates in the frozen audit engine; nothing fabricated, projected, or smoothed | Each figure traces to an API field; provisional vs certified always disclosed |
| **P3** | Decision Confidence | Uncertainty, evidence, and grades are visible and honest | Grades/hashes/badges present; absent data renders as absent, never invented |
| **P4** | Visual Hierarchy | One primary element per view; money > context > chrome | Squint test: the money number wins |
| **P5** | Institutional Trust | Quiet, premium, consistent; never noisy, never template-like | No rainbow palettes, no decoration without meaning |
| **P6** | Operational Efficiency | Fast to load, fast to read, fast to act | Budgets in SPEC-PF met; primary action reachable in ≤ 2 interactions |

## 0.1 Governance & amendment process

1. Specifications are versioned (`SPEC-XX x.y`) and append-only after
   ratification, exactly like EDA metric contracts.
2. Changes happen through **ratified amendments** recorded in §17 of this
   document (id, date, what changed, why).
3. Every implementation change must be able to state which SPEC-IDs and
   principles it satisfies. A change that satisfies none is rejected.
4. A screen ships only when it passes its spec's Acceptance Criteria and the
   global compliance checklist (§16).

## 0.2 Specification index

| ID | Specification | Version | Status |
|----|---------------|---------|--------|
| SPEC-DS | Design System | 1.0 | PROPOSED |
| SPEC-WS | Workspace | 1.0 | PROPOSED (normative annex: `WORKSPACE_SPEC.md`) |
| SPEC-IA | Information Architecture | 1.0 | PROPOSED |
| SPEC-EX | Executive Experience | 1.0 | PROPOSED |
| SPEC-RB | Role-Based Experience | 1.0 | PROPOSED |
| SPEC-DV | Data Visualization | 1.0 | PROPOSED |
| SPEC-MO | Motion | 1.0 | PROPOSED |
| SPEC-AX | Accessibility | 1.0 | PROPOSED |
| SPEC-RS | Responsive | 1.0 | PROPOSED |
| SPEC-PF | Performance | 1.0 | PROPOSED |
| SPEC-SX | Security UX | 1.0 | PROPOSED |
| SPEC-IX | Interaction | 1.0 | PROPOSED |
| SPEC-CO | Component | 1.0 | PROPOSED |
| SPEC-NV | Navigation | 1.0 | PROPOSED |
| SPEC-DB | Dashboard | 1.0 | PROPOSED |

---

# 1. SPEC-DS — Design System Specification 1.0
**Principles:** P4, P5

**Purpose.** One visual language for the entire product: color, typography,
spacing, radii, elevation, and motion tokens, with economic semantics baked
into color.

**Scope.** `src/design/tokens.css` (CSS variables `--pds-*`, dark theme +
light scaffold), `src/design/ds.js` (JS mirror + semantic resolvers),
`src/design/components.jsx` (primitives). The legacy `DS` object in App.jsx
is a **bridge** whose hex values mirror the tokens until migration removes it.

**Responsibilities.**
- Define every color, type, spacing, radius, shadow, and duration token.
- Bind color to economic meaning: loss `#FF5C7A`, recover `#2FD69B`,
  warn `#F3B24C`, accent teal `#34E0C8`, grades A–E, decision types,
  verified/provisional/seal.
- Provide the semantic resolvers (`gradeColor`, `decisionColor`,
  `severityColor`, `riskColor`) and institutional formatters
  (`fmtMoney` compact B/M/K, `fmtPct`, en-US digit grouping).

**Boundaries.** Does not define layout (SPEC-WS), chart construction
(SPEC-DV), motion choreography (SPEC-MO), or component behavior (SPEC-CO/IX).

**Inputs.** Brand identity; principles P4/P5; contrast requirements from
SPEC-AX.

**Outputs.** Token files; primitive components; the palette bridge for legacy
inline styles.

**Rules.**
1. No hardcoded color, font, spacing, or radius outside token definitions.
2. Color carries meaning first, decoration never: a red element means
   economic loss or danger — nothing else.
3. Typography: Inter (UI), JetBrains Mono (numerals, hashes, evidence).
   Money and hashes are always mono (`.pds-num`).
4. Spacing is the 8pt scale; radii from the `--pds-r-*` set only.
5. Dark theme is primary; the light scaffold keeps identical semantic names.

**Acceptance criteria.** A grep for hex literals outside `tokens.css` /
`ds.js` / the documented `DS` bridge returns zero; contrast audits pass
SPEC-AX; a themed screenshot review shows one coherent language.

**Non-goals.** Page layout, data fetching, chart internals, white-label
theming (future).

**Future extensions.** Light theme completion; customer white-labeling;
density (comfortable/compact) variants.

---

# 2. SPEC-WS — Workspace Specification 1.0
**Principles:** P1, P4, P6

**Purpose.** One workspace architecture for every screen: shell, sidebar,
header, executive workspace, zones, grid, density tiers, and ultra-wide /
4K / video-wall behavior.

**Scope & normative detail.** The full contract — tier table T1–T5, sidebar
`clamp(248px, 18vw, 400px)`, zone catalog Z1–Z10, zone-visibility matrix,
macro/zone/card grids, scroll policy — lives in **`WORKSPACE_SPEC.md`
(WS-1.0)**, which is a normative annex of this document.

**Responsibilities.** Own all horizontal space allocation; guarantee "space
reveals intelligence, not larger rectangles"; supersede and remove the
interim 1720px Executive cap.

**Boundaries.** Does not choose which questions zones answer (SPEC-IA), nor
zone content design (SPEC-EX/DB), nor component internals (SPEC-CO).

**Inputs.** Viewport via `useWorkspaceTier()` (matchMedia); ratified zone
catalog; tokens.

**Outputs.** `<Workspace>`, `<Region>`, `<Zone>` primitives; `--ws-*` layout
tokens; the tier signal consumed by every other spec.

**Rules.** (Summary — annex is authoritative.)
1. No artificial max-width container around the workspace; no centered
   content column. Readable-width caps apply to prose (≤72ch) and cards
   (≤560px), never to the workspace.
2. Wider tiers add zones (T3 adds AI Reasoning + Evidence; T4 adds the
   Intelligence Rail, decision stream, live telemetry, portfolio comparison;
   T5 co-locates everything, zero-scroll target).
3. Whitespace grows between zones by tier; horizontal scroll never exists.

**Acceptance criteria.** At 1440/1920/2560/3440 the measured workspace share
is ≥ 80% of viewport (sidebar expanded); zone matrix renders per tier; no
horizontal scroll at any width; the 1720px cap is gone.

**Non-goals.** Mobile-first patterns; content design; navigation taxonomy.

**Future extensions.** User-arrangeable zones (drag layout persistence);
multi-monitor split workspaces.

---

# 3. SPEC-IA — Information Architecture Specification 1.0
**Principles:** P1, P2, P4

**Purpose.** Define the sequence of questions the product answers and map
every screen, section, and zone to exactly one primary question.

**Scope.** The question hierarchy, the sidebar section taxonomy, and the
zone-to-question mapping. Applies to all current 16 sections and any future
screen.

**Responsibilities.** The canonical question ladder:

| # | Question | Primary surface | Data (existing) |
|---|----------|-----------------|------------------|
| Q1 | How much are we losing? | Z2 KPI (Financial Leakage) | `total_gap_usd` |
| Q2 | How much can we recover? | Z2 KPI (Recoverable Value) | `recoverable_execution_gap` / `gap_attribution.execution_gap` |
| Q3 | How healthy are our decisions? | Z2 KPI (Decision Health) | `dq_score` (ECF) + `risk_level` (+ `audit_confidence` when present) |
| Q4 | What should we do next? | Z3b Opportunity | `opportunities[]`, `root_causes[]` |
| Q5 | Why is value leaking? | Root Cause / Z4 chart | `root_causes[]`, ledger series |
| Q6 | Can we prove it? | Evidence / Governance | `audit_manifest`, certificate, governance records |
| Q7 | What is happening right now? | Live / Z8 telemetry | `/ws/live`, live state (PROVISIONAL) |
| Q8 | How do assets compare? | Portfolio (T4+) | `/api/v1/audits` history |

- Section taxonomy (groups, replacing the flat 16-item list):
  **COMMAND** (Executive Summary) · **ANALYSIS** (Value Flow, Audit Trail,
  Root Cause, Counterfactual, EDA Metrics, Leakage, Heat Map) ·
  **ACTION** (Economic Action Plan, Intelligence Report) ·
  **EVIDENCE & GOVERNANCE** (Governance, Certificate, Audit History) ·
  **OPERATIONS** (Live Monitor, Real-Time) · **REFERENCE** (Math Appendix).

**Boundaries.** Does not style the sidebar (SPEC-NV renders the taxonomy);
does not compose zones (SPEC-DB).

**Inputs.** The frozen API surface; the executive brief's four questions.

**Outputs.** Question registry (above); section grouping; each screen's
declared primary question.

**Rules.**
1. Every screen declares exactly one primary question; its answer renders
   first (top-left reading order) before any secondary content.
2. Q1–Q4 are never displaced from the first screen (SPEC-EX).
3. A screen that answers no question from the registry may not exist
   without a ratified registry amendment.

**Acceptance criteria.** For each section a reviewer can name its question
without help; navigation groups match the taxonomy; Q1–Q4 answered on S01
without scrolling at T2+.

**Non-goals.** Copywriting; localization structure (future).

**Future extensions.** Q9 "What did our decisions earn us?" (Outcome/GOV
aggregate ROI view) once portfolio outcome history accumulates.

---

# 4. SPEC-EX — Executive Experience Specification 1.0
**Principles:** P1, P2, P3, P4

**Purpose.** Contract for the first screen: an Executive Command Center that
answers Q1–Q4 instantly and makes "this software manages millions" felt.

**Scope.** Section S01 (`ExecutiveCommandCenter` + its zones Z1–Z4, plus
Z5/Z6 at T3+ per the WS matrix).

**Responsibilities.**
- Z1 Command Header: asset identity, period, risk, evidence badge
  (CERTIFIED green / PROVISIONAL amber) — trust before numbers.
- Z2 KPI row: Financial Leakage (loss color), Recoverable Value (recover
  color, % of leakage), Decision Health (ECF gauge + risk verdict).
- Z3: Decision Intelligence + Recommended Action with Value at Stake,
  always labeled "historical basis — no forward projection".
- Z4: the historical economic chart (per SPEC-DV).

**Boundaries.** Consumes zones; does not define tiers (SPEC-WS), charts
(SPEC-DV), or role variants (SPEC-RB).

**Inputs.** One audit response object (live or historical); `dataSource`
signal (demo/upload/live).

**Outputs.** The reference implementation every other dashboard is measured
against (SPEC-DB).

**Rules.**
1. Q1–Q4 visible without scroll at T2+ (1440×900 reference).
2. Money numerals are the largest elements on screen (P4).
3. Confidence values render only when the API provides them; the ECF-based
   Decision Health card is the permanent fallback (P2/P3 — no fabrication).
4. Every value-at-stake statement carries its basis disclaimer.

**Acceptance criteria.** 5-second test passes with an uninitiated executive;
no-scroll at 1440×900; every figure traceable to a named API field; evidence
badge state matches the data source.

**Non-goals.** Editing/config workflows; onboarding flows.

**Future extensions.** Multi-asset executive rollup as Z9 matures.

---

# 5. SPEC-RB — Role-Based Experience Specification 1.0
**Principles:** P1, P6

**Purpose.** Adapt emphasis — not truth — per executive archetype:
CFO, CEO, Operations Manager, Engineer, Administrator.

**Scope.** Archetype presets that re-weight zone emphasis and section
ordering. Presentation only.

**Responsibilities.** Archetype → emphasis matrix:

| Archetype | Leads with | Elevated zones/sections | De-emphasized |
|-----------|-----------|--------------------------|----------------|
| CFO | Q1/Q2 money | Z2, Value Flow, Leakage, Certificate | Live telemetry |
| CEO | Q3/Q8 health & portfolio | Z2, Portfolio, Governance verdicts | Engineering detail |
| Operations | Q4/Q7 act now | Z3b, Live Monitor, Decision Stream | Math Appendix |
| Engineer | Q5/Q6 why & proof | Root Cause, Counterfactual, EDA Metrics, Appendix | — |
| Administrator | System state | Audit History, security/session surfaces | — |

**Boundaries.** RBAC **enforcement stays in the backend** (existing
owner/admin/asset_manager model). Archetypes are a UI lens; they never
grant or imply data access.

**Inputs.** Authenticated account role (existing API) as the default
archetype hint; explicit user selection persisted client-side.

**Outputs.** An `archetype` preference consumed by SPEC-DB compositions and
SPEC-NV ordering.

**Rules.**
1. No archetype hides evidence or alters numbers — emphasis only (P2).
2. Switching archetypes is one interaction and instantly reversible.
3. Default without selection: CFO lens (money-first), because the platform's
   moat is economic truth.

**Acceptance criteria.** Same audit, two archetypes → identical figures,
different ordering/emphasis; preference survives reload; no API change.

**Non-goals.** New permission models; per-role feature gating.

**Future extensions.** Org-level default archetypes; saved custom lenses.

---

# 6. SPEC-DV — Data Visualization Specification 1.0
**Principles:** P2, P4, P5

**Purpose.** A proprietary PREDAIOT chart language — every chart reads as
economic evidence, not as a library default.

**Scope.** All charts: recharts-based (theming wrapper) and hand-rolled SVG
(Sparkline, gauges). Applies to Z4, section charts, live telemetry.

**Responsibilities.**
- One `ChartTheme` wrapper: quiet hairline grids, `--pds-text-3` axes,
  panel-styled tooltips, gradient area fills (accent → transparent),
  loss/recover shading semantics (value below benchmark shades loss).
- Canonical chart set: economic timeline (area+line), benchmark-vs-actual,
  gap attribution (stacked), decision heat strip, confidence gauge,
  sparkline. Each maps to named API series.

**Boundaries.** Colors come from SPEC-DS; sizes from SPEC-WS tier heights;
entrance animation from SPEC-MO.

**Inputs.** Real series only (audit ledger, live buffer, history). 

**Outputs.** Chart wrapper components + a per-chart data contract (series →
API field).

**Rules.**
1. No default library styling may remain visible (fonts, colors, grid).
2. Axis truth: no truncated axes that exaggerate movement without an explicit
   break marker (P2).
3. Every chart carries its unit and period label; money axes use `fmtMoney`.
4. Empty/insufficient data renders an honest empty state, never sample data.
5. Max one accent series per chart; comparisons use the semantic palette.

**Acceptance criteria.** Screenshot review finds no default-recharts look;
each chart's series traceable to API fields; tooltips styled; axes labeled.

**Non-goals.** 3D, decorative animation, exotic chart types without a
question to answer.

**Future extensions.** Canvas/WebGL rendering for T5 walls; brush-zoom
synced across zones.

---

# 7. SPEC-MO — Motion Specification 1.0
**Principles:** P5, P6

**Purpose.** Motion that communicates state change — expensive, physical,
purposeful; never decorative noise.

**Scope.** All animation: numeric count-ups, panel entrances, live pulses,
gauge sweeps, hover/focus transitions.

**Responsibilities.** One motion vocabulary from tokens: durations 140 /
260 / 520 ms; easing `cubic-bezier(0.22,1,0.36,1)` family; keyframes
(`pds-rise`, `pds-pulse`, `pds-breathe`, `pds-sheen`).

**Boundaries.** Token values live in SPEC-DS; chart-specific entrances in
SPEC-DV; loading states in SPEC-IX.

**Inputs.** State changes (data arrival, tier change, user action),
`prefers-reduced-motion`.

**Outputs.** The animation classes/utilities; AnimatedNumber behavior.

**Rules.**
1. Animate only `transform` and `opacity` (compositor-only; 60 fps — P6);
   count-ups via rAF.
2. Motion must encode meaning: money changed (count-up), evidence is live
   (pulse), content arrived (rise). Looping animation is reserved for
   genuinely live signals.
3. Reduced-motion disables all non-essential animation (already in tokens).
4. Nothing bounces, spins, or parallaxes. Ever (P5).

**Acceptance criteria.** DevTools performance trace shows no layout thrash
from animation; reduced-motion audit passes; every animation names its
meaning in review.

**Non-goals.** Route transitions, skeleton shimmer theatrics, Lottie.

**Future extensions.** Choreographed T5 wall transitions (zone-stagger).

---

# 8. SPEC-AX — Accessibility Specification 1.0
**Principles:** P3, P5

**Purpose.** WCAG 2.2 AA — institutional software must be operable by every
executive and operator, including under floor/field conditions.

**Scope.** All screens, components, charts, and motion.

**Responsibilities.** Contrast, keyboard operability, semantics/landmarks,
focus management, alternative encodings for color.

**Boundaries.** Token contrast values fixed in SPEC-DS; motion opt-out in
SPEC-MO; touch targets shared with SPEC-RS.

**Inputs.** Design tokens; component catalog; axe-core audits.

**Outputs.** Per-screen audit results; documented exceptions (if ever) with
amendments.

**Rules.**
1. Text contrast ≥ 4.5:1 (≥ 3:1 for ≥24px bold); verify `--pds-text-2/3`
   on panels.
2. Color is never the sole carrier: grades keep letters, badges keep words
   (CERTIFIED/PROVISIONAL), trends keep direction glyphs.
3. Full keyboard path: sidebar, header actions, interactive cards; visible
   `:focus-visible` ring in accent.
4. Landmarks: `header/nav/main`; charts get text alternatives (the KPI
   values already present satisfy summary duty).
5. Touch targets ≥ 44px on T1 (already policy in mobile nav).

**Acceptance criteria.** axe-core: zero critical/serious on every section;
keyboard-only walkthrough completes demo → audit → certificate; contrast
report archived per release.

**Non-goals.** WCAG AAA; screen-reader-optimized data tables for 288-step
ledgers (virtualized summary + CSV export covers it).

**Future extensions.** High-contrast theme via the token scaffold.

---

# 9. SPEC-RS — Responsive Specification 1.0
**Principles:** P1, P6

**Purpose.** Desktop-first adaptation: the same truth from a 49-inch wall to
a phone, degrading co-presence — never content integrity.

**Scope.** Component-level adaptation inside the SPEC-WS tiers: how cards,
tables, headers, and charts reflow at T1/T2 vs T3+.

**Responsibilities.** Stack order on T1 (Q1→Q4 preserved), table→card
transforms for ledgers, header condensation (existing mobile pattern),
`clamp()` numeral scaling.

**Boundaries.** Zone visibility is SPEC-WS's matrix; this spec governs what
happens *inside* a zone at small sizes.

**Inputs.** Tier signal; `useIsMobile` (720px drawer threshold, existing).

**Outputs.** Responsive rules per component class (KPI, table, chart,
header, modal).

**Rules.**
1. Desktop is the design origin; T1 is a faithful reduction, not a separate
   product.
2. No horizontal scroll; no clipped numerals (clamp scale is mandatory).
3. Reading order on T1 = question order Q1→Q4 (P1).
4. Touch affordances on T1: 44px targets, drawer nav, no hover-dependent
   information.

**Acceptance criteria.** 390 / 768 / 1024 / 1440 / 1920 / 2560 / 3440 render
clean (no overflow, no clipping); T1 shows all four answers in first two
screenfuls.

**Non-goals.** Native apps; print styles (PDF export already exists).

**Future extensions.** Compact-density mode for control rooms.

---

# 10. SPEC-PF — Performance Specification 1.0
**Principles:** P6

**Purpose.** The product must feel instantaneous — latency erodes
institutional trust.

**Scope.** Bundle, runtime rendering, data streaming, animation cost.

**Responsibilities.** Budgets and the techniques to hold them.

**Boundaries.** Backend latency is out of scope (frozen); this spec owns
everything after the response arrives.

**Inputs.** Vite build stats; runtime profiles; live WS message rate.

**Outputs.** Enforced budgets; lazy-loading map; virtualization inventory.

**Rules (budgets).**
1. Initial JS ≤ 250 kB gzip (current: ~214 kB — regression gate).
2. Code-split heavy, rarely-first surfaces: charts vendor chunk, Math
   Appendix, Certificate/PDF flows, Live Monitor.
3. Long lists (288-step ledgers, audit history, decision stream) are
   virtualized or paginated at > 100 rows.
4. Live feed renders are throttled/batched (≤ 4 state commits/s); memoized
   zone boundaries stop re-render storms.
5. Interaction cost: < 16 ms/frame during animation (compositor-only rule
   from SPEC-MO); tier switch < 200 ms.
6. Lighthouse desktop performance ≥ 90 on S01 with demo data.

**Acceptance criteria.** CI check on bundle size; profiled trace of live
mode shows bounded commits; Lighthouse report archived per release.

**Non-goals.** SSR/SEO work (authenticated product); service workers
(future).

**Future extensions.** WebGL chart offload at T5; worker-side series
downsampling.

---

# 11. SPEC-SX — Security UX Specification 1.0
**Principles:** P2, P3, P5

**Purpose.** Make the platform's real security architecture *visible* —
trust must be perceivable — without security theater.

**Scope.** Evidence badges, hashes, certificates, session/trial states,
error surfaces, data-sensitivity presentation.

**Responsibilities.**
- Evidence chain surfaces: truncated SHA-256 with copy-full affordance;
  certificate verification URL; hash-chain integrity indicators from
  existing endpoints.
- State honesty: CERTIFIED (green) vs PROVISIONAL (amber) never conflated;
  live states always provisional until reconciled (EDA-RECON semantics).
- Session surfaces: signed-in identity, trial state, expiry — quiet, factual.

**Boundaries.** Actual security (RBAC, headers, encryption, rate limits) is
backend-owned and frozen; this spec renders it.

**Inputs.** Existing fields: `audit_manifest.input_sha256`, certificate
records, governance verdicts, session/trial tokens, roles.

**Outputs.** Badge/indicator components (EvidenceBadge exists), error-view
patterns, masking rules.

**Rules.**
1. Secrets and tokens never render in URLs or full plaintext; emails masked
   where shown.
2. Errors state what failed and the next step — never stack traces or
   internal identifiers (P5).
3. Every economic figure sits within reach of its evidence (badge, hash, or
   link) — the P3 "prove it" affordance.
4. No fake security ornamentation (padlock icons without meaning).

**Acceptance criteria.** Trust-surface inventory complete on every screen
with data; token/secret leak audit clean; provisional/certified states
verified against data source in E2E.

**Non-goals.** New auth flows; changing backend security.

**Future extensions.** In-UI certificate verifier (calls existing verify
endpoint); governance-chain visual explorer.

---

# 12. SPEC-IX — Interaction Specification 1.0
**Principles:** P1, P5, P6

**Purpose.** Uniform interaction grammar: every control behaves predictably
in all states.

**Scope.** Buttons, cards, nav items, inputs, modals, uploads, toasts,
loading/empty/error states.

**Responsibilities.** The state matrix — every interactive element defines
default / hover / focus / active / disabled / loading; every data surface
defines loading / empty / error / populated.

**Boundaries.** Visual tokens from SPEC-DS; motion from SPEC-MO; component
inventory in SPEC-CO.

**Inputs.** User events; request lifecycle.

**Outputs.** Interaction patterns adopted by all components.

**Rules.**
1. One accent primary action per view (header: RUN DEMO); all secondary
   actions quiet neutral (ratified in Phase 2 work).
2. **No optimistic UI for economic data** — figures render only from server
   truth (P2); loading states are explicit.
3. Empty states are honest and directive ("Run an audit to populate…"),
   never sample data.
4. Errors are recoverable in place (retry affordance) and never modal-trap.
5. Destructive or irreversible actions require explicit confirmation;
   uploads validate before submit (existing pattern).
6. Loading: skeleton panels for zones (> 300 ms expected), inline spinners
   for actions; never full-screen blockers after first paint.

**Acceptance criteria.** State-matrix audit per component passes; demo→
audit→certificate flow has zero dead-end states; keyboard parity per
SPEC-AX.

**Non-goals.** Undo infrastructure; collaborative cursors.

**Future extensions.** Command palette (⌘K) for section jumps (feeds
SPEC-NV future).

---

# 13. SPEC-CO — Component Specification 1.0
**Principles:** P4, P5, P6

**Purpose.** A governed component catalog — the UI equivalent of
METRIC_REGISTRY. New components enter by registration, not improvisation.

**Scope.** All reusable UI units.

**Responsibilities.** The registry:

| Component | Status | Spec owner |
|-----------|--------|------------|
| Panel, KpiCard, AnimatedNumber, GradeBadge, EvidenceBadge, StatusDot, SectionTitle, Sparkline, Trend, Divider | EXISTS (`design/components.jsx`) | SPEC-DS/CO |
| SectionHeader (App), Pill, BtnOutline, ProgressBar, Card (legacy) | EXISTS (bridge — migrate to design/) | SPEC-CO |
| Workspace, Region, Zone, useWorkspaceTier | PLANNED (SPEC-WS) | SPEC-WS |
| ChartTheme + canonical charts | PLANNED (SPEC-DV) | SPEC-DV |
| Button family (primary/quiet/danger), Skeleton, Toast, EmptyState | PLANNED | SPEC-IX |
| ArchetypeSwitcher | PLANNED (SPEC-RB) | SPEC-RB |

**Boundaries.** Components consume tokens only; they never fetch data
(data flows in as props from screens/zones).

**Inputs.** Tokens; interaction grammar; accessibility rules.

**Outputs.** `src/design/` as the single component home; legacy duplicates
retired on migration.

**Rules.**
1. A new component requires: registry entry, principle citation, state
   matrix (SPEC-IX), and token-only styling.
2. One component, one responsibility; composition over configuration.
3. Props are semantic (`grade`, `provisional`, `live`) — never raw colors.
4. Legacy bridge components may not gain new features; feature work happens
   in `design/`.

**Acceptance criteria.** No unregistered reusable component in the tree;
`design/` components have zero data-fetching imports.

**Non-goals.** Publishing an external component library (future);
Storybook (Phase 9 decides).

**Future extensions.** Extraction into a versioned package for future
PREDAIOT products.

---

# 14. SPEC-NV — Navigation Specification 1.0
**Principles:** P1, P6

**Purpose.** Navigation as an instrument rail: grouped, quiet, instant.

**Scope.** Sidebar, header actions, section switching, mobile drawer.

**Responsibilities.** Render the SPEC-IA taxonomy as grouped navigation
(COMMAND / ANALYSIS / ACTION / EVIDENCE & GOVERNANCE / OPERATIONS /
REFERENCE) with the EDA-xx numbering preserved as mono tags; active state =
accent left rule (existing pattern, kept).

**Boundaries.** Taxonomy owned by SPEC-IA; widths by SPEC-WS; archetype
ordering by SPEC-RB.

**Inputs.** Section registry; tier; archetype.

**Outputs.** Sidebar component (grouped), header action bar, drawer.

**Rules.**
1. Groups are labeled with kickers; items keep number + name; ⚡/🏆 style
   glyph tags are replaced by consistent mono tags (P5).
2. Sections never nest deeper than one group level.
3. Section switch is instant (no data refetch if state unchanged) — P6.
4. Header carries at most: primary action, quiet utilities, identity,
   session badge. Anything else moves into menus.
5. Mobile: drawer with 44px targets (existing), same grouping.

**Acceptance criteria.** Any section reachable in ≤ 2 interactions; grouped
sidebar matches SPEC-IA table exactly; keyboard navigable per SPEC-AX.

**Non-goals.** Multi-level trees; breadcrumbs; URL routing rework (future).

**Future extensions.** Deep links per section (`#/section/exec`); ⌘K
palette (with SPEC-IX).

---

# 15. SPEC-DB — Dashboard Specification 1.0
**Principles:** P1, P2, P4, P6

**Purpose.** The assembly contract: how any dashboard is composed from
workspace zones, so every future page is a composition, not an invention.

**Scope.** All current sections and future dashboards (role lenses,
portfolio, live operations).

**Responsibilities.** Every dashboard declares a manifest:

```
Dashboard manifest (required before implementation)
- id, title, primary question (from SPEC-IA registry)
- zones used (from WS catalog) + tier matrix row
- data endpoints consumed (existing API only)
- archetype emphasis (if any)
- acceptance evidence: screenshot set per tier + checklist result
```

**Boundaries.** Zones/tiers from SPEC-WS; questions from SPEC-IA; visuals
from SPEC-DS/DV.

**Inputs.** Ratified zone catalog, question registry, component registry.

**Outputs.** Dashboard manifests (S01 Executive is the reference
implementation and first manifest).

**Rules.**
1. No dashboard without a manifest; no zone outside the catalog.
2. The primary question's answer occupies the visual apex (P4).
3. Dashboards degrade by tier via the WS matrix — never by ad-hoc CSS.
4. All data honest: provisional marked, empty states directive, basis
   disclaimers on any value framing (P2).

**Acceptance criteria.** Manifest exists and matches implementation; tier
screenshots archived; compliance checklist (§16) passes.

**Non-goals.** User-built custom dashboards (future).

**Future extensions.** Manifest-driven rendering (dashboards as data).

---

# 16. Global compliance checklist (every screen, every release)

- [ ] Cites its SPEC-IDs and principles (P1–P6) — unjustifiable elements removed
- [ ] Composes `<Workspace>`; no bespoke layout; no max-width container
- [ ] Primary question answered first; Q1–Q4 never displaced from S01
- [ ] All data from frozen production APIs; no fabrication; provisional/certified honest
- [ ] Tokens only — no stray hex/px conventions outside the system
- [ ] Chart language applied; no library-default styling
- [ ] State matrix complete (loading/empty/error/populated)
- [ ] axe-core clean; keyboard path complete; reduced-motion honored
- [ ] No horizontal scroll 390→5120px; numerals never clip
- [ ] Bundle and render budgets hold (SPEC-PF)
- [ ] Evidence affordance within reach of every economic figure

# 17. Amendments log

| # | Date | Spec | Change | Ratified by |
|---|------|------|--------|-------------|
| — | — | — | (none — initial proposal) | — |

# 18. Implementation order (after ratification — the nine phases)

1. **Workspace System** — primitives (`useWorkspaceTier`, Workspace/Region/
   Zone), remove 1720px cap, migrate all 16 sections onto the workspace.
2. **Information Architecture** — grouped navigation, question registry
   applied, section manifests drafted.
3. **Executive Dashboard** — S01 rebuilt to full SPEC-EX + WS matrix
   (T3/T4/T5 zones activate).
4. **Role-Based Dashboards** — archetype lenses (SPEC-RB).
5. **Chart Language** — ChartTheme + canonical charts replace defaults
   (SPEC-DV).
6. **Motion System** — vocabulary applied product-wide (SPEC-MO).
7. **Accessibility & Responsiveness** — audits + fixes to AA (SPEC-AX/RS).
8. **Performance & Load Testing** — budgets enforced, live-feed profiling
   (SPEC-PF).
9. **Design Documentation** — component registry docs, dashboard manifests,
   contribution guide (makes the system survivable beyond any engineer).

Phases execute strictly in order. No phase begins before the previous one's
acceptance criteria pass.
