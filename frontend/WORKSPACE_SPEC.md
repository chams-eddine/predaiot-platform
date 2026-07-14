# PREDAIOT Workspace Specification — WS-1.0

**Status:** PROPOSED — awaiting ratification.
**Position:** Normative annex of `PRODUCT_SPEC.md` (PREDAIOT-FE-2.0,
Part I, SPEC-WS). Ratification of SPEC-WS ratifies this annex (GOV-RP
rule 2). Interim note: the 1720px executive cap referenced in §1.1 is
formally superseded and scheduled for removal in Phase 1 migration.
**Scope:** Every screen in the PREDAIOT frontend. No page may define its own
layout architecture after ratification; all pages compose this workspace.
**Authority:** Subordinate to PLATFORM_BLUEPRINT.md and the frozen backend.
Zones bind to existing production APIs only — a zone with no data renders an
honest empty state, never fabricated content.
**Class of software:** Premium executive desktop software. Not responsive web
design. The canvas is the product.

---

## 1. Principles

1. **The workspace owns the canvas.** No artificial max-width containers, no
   centered content columns, no unused canvas. (Supersedes the interim 1720px
   cap on the Executive section — to be removed in migration.)
2. **Space reveals intelligence, not larger rectangles.** A wider display
   shows *more zones* (more analysis, more comparison, more evidence), not
   stretched cards.
3. **Whitespace lives BETWEEN information zones**, produced by the zone-gap
   scale — never by narrowing the workspace.
4. **Density is tiered, not fluid.** The workspace snaps between five named
   density tiers. Inside a tier, charts absorb elasticity; text and cards
   stay at readable widths.
5. **One workspace, every page.** Executive, role-based, live/SCADA, and
   governance screens all compose the same shell, grid, and zone system.

---

## 2. Layout hierarchy (canonical)

```
Viewport
└── Application Shell            (full viewport, dark canvas, no max-width)
    ├── Header                   (full width, sticky)
    └── Shell Body               (flex row)
        ├── Sidebar              (navigation rail)
        └── Executive Workspace  (owns ~80–86% of horizontal space)
            └── Information Zones (Z1…Z10, tier-gated)
                └── Cards / Panels
                    └── Charts
                        └── Evidence (hashes, badges, manifests)
```

---

## 3. Application Shell

| Element   | Rule |
|-----------|------|
| Canvas    | `--pds-bg-0`, full-bleed; ambient radial accents (`.pds-root`) allowed |
| Header    | Height **64px** (T2+) / 56px (T1); sticky; full width; one accent primary action, all other actions quiet neutral |
| Shell body| `display:flex`; Sidebar + Workspace; **no outer margins** |

## 4. Sidebar

| Tier | Width | Share of 1440 / 1920 / 2560 / 3440 |
|------|-------|--------------------------------------|
| T1   | Overlay drawer 272px (existing) | — |
| T2–T5| `clamp(248px, 18vw, 400px)` | 18.0% / 18.0% / 15.6% / 11.6% |

- Meets the 18–20% target on 1440–2200px executive displays; **caps at 400px**
  beyond that so additional canvas feeds intelligence zones, not navigation.
- Collapsible to a **64px icon rail** at any tier (user toggle, persisted).
- Sticky, own scroll region, never scrolls with the workspace.

## 5. Executive Workspace

| Tier | Workspace padding | Zone gap (between zones) | Card gap (inside zones) |
|------|-------------------|--------------------------|--------------------------|
| T1   | 16px              | 24px                     | 12px |
| T2   | 32px              | 32px                     | 16px |
| T3   | 40px              | 40px                     | 20px |
| T4   | 48px              | 48px                     | 24px |
| T5   | 56px              | 56px                     | 24px |

The workspace is **never width-capped**. Whitespace grows with the tier —
between zones, not around the workspace.

---

## 6. Grid system

Three nested grids; no page invents its own.

1. **Macro-grid (regions)** — T4/T5 only. Splits the workspace into
   coexisting executive regions:
   - T4 `COMMAND`: `grid-template-columns: 65fr 35fr` → Main + Intelligence Rail
   - T5 `WALL`:    `grid-template-columns: 30fr 45fr 25fr` → Analysis | Command | Evidence/Live
2. **Zone-grid (rows)** — named row templates inside a region:
   - `row-full`    → `1fr`            (100%)
   - `row-split`   → `1fr 1fr`        (50 / 50)
   - `row-primary` → `65fr 35fr`      (65 / 35)
3. **Card-grid (within a zone)** —
   `repeat(auto-fit, minmax(280px, 1fr))`, with **card max-width 560px**;
   when cards hit max, surplus width goes to chart zones, never to card fat.

**Readable-width caps apply to content, not layout:** prose ≤ **72ch**;
KPI card 280–560px; charts and timelines are the elastic elements and may
grow without limit.

---

## 7. Density tiers (breakpoints)

| Tier | Name      | Viewport width | Typical displays |
|------|-----------|----------------|------------------|
| T1   | COMPACT   | < 1024px       | tablet, small laptop, phone (<720px → drawer) |
| T2   | STANDARD  | 1024–1679px    | 1280, **1440**, **1600** laptops/desktops |
| T3   | EXTENDED  | 1680–2239px    | **1920**, 2048 executive desktops |
| T4   | COMMAND   | 2240–3199px    | **2560** (QHD/4K scaled) |
| T5   | WALL      | ≥ 3200px       | **3440 ultrawide, 49-inch (5120), video walls** |

Tiers are detected once via `matchMedia` (`useWorkspaceTier()` hook) — the
same mechanism as the existing `useIsMobile`, generalized.

---

## 8. Information Zone catalog

Every zone binds to an **existing production API** (backend frozen).

| ID  | Zone                    | Answers                          | Data source (existing) |
|-----|-------------------------|----------------------------------|------------------------|
| Z1  | Command Header          | What asset, what period, how trusted | audit: `asset_name`, `risk_level`, `audit_manifest`, evidence badge |
| Z2  | Primary KPI Row         | Losing? Recoverable? Healthy?    | `total_gap_usd`, `recoverable_execution_gap`, `dq_score` (ECF) + `risk_level` |
| Z3a | Decision Intelligence   | How are decisions performing     | `decision_log`, decision stats |
| Z3b | Opportunity Panel       | What should we do next           | `opportunities[]`, `root_causes[]` |
| Z4  | Historical Chart        | Where did value leak over time   | audit time-series ledger (existing chart data) |
| Z5  | AI Reasoning            | Why — narrated causality         | Economic Intelligence Report (existing) |
| Z6  | Evidence Timeline       | Prove it                         | `audit_manifest`, certificate, governance records |
| Z7  | Decision Stream         | What is moving through lifecycle | EDA-DEC-LIFE events (existing endpoints) |
| Z8  | Live Telemetry          | What is happening right now      | `/ws/live`, live state (PROVISIONAL badge mandatory) |
| Z9  | Portfolio Comparison    | Which asset leaks most           | audit history (`/api/v1/audits`, authenticated) |
| Z10 | Opportunity Matrix      | Full recovery landscape          | `opportunities[]` (complete set) |

## 9. Zone visibility matrix — "space reveals intelligence"

| Zone | T1 | T2 | T3 | T4 | T5 |
|------|----|----|----|----|----|
| Z1 Command Header      | ● stack | ● 100% | ● 100% | ● 100% | ● 100% |
| Z2 Primary KPI Row     | ● stack | ● 100% (3–4 cards) | ● 100% | ● 100% | ● 100% |
| Z3 Decision + Opportunity | ● stack | ● 50/50 | ● 50/50 | ● 50/50 | ● 50/50 |
| Z4 Historical Chart    | ● h240 | ● h300 | ● h380 | ● h440 | ● h480 |
| Z5 AI Reasoning        | ○ via section | ○ via section | ● 65% | ● 65% | ● region |
| Z6 Evidence Timeline   | ○ via section | ○ via section | ● 35% | ● rail | ● region |
| Z7 Decision Stream     | ○ | ○ | ○ | ● rail | ● region |
| Z8 Live Telemetry      | ○ | ○ | ○ | ● rail | ● region |
| Z9 Portfolio Comparison| ○ | ○ | ○ | ● (if >1 audit) | ● |
| Z10 Opportunity Matrix | ○ | ○ | ○ | ○ | ● |

● = co-present on the workspace ○ = reachable through its sidebar section
(nothing is ever lost — lower tiers navigate; higher tiers co-locate).

This realizes the ladder: **1440** = KPIs + chart + recommendation;
**1920** = + AI reasoning + evidence; **2560** = + decision stream, live
telemetry, evidence chain, portfolio comparison; **3440/49-inch** = the full
command wall, glanceable without scroll.

---

## 10. Ultra-wide / 4K / video-wall behavior

- **T4 COMMAND:** dual-region. Main region keeps the canonical executive
  flow; the Intelligence Rail (35%) carries Z6/Z7/Z8 as a live evidence
  column. Scroll budget target ≤ 1.5 viewport heights.
- **T5 WALL:** tri-region; all zones coexist; target **zero scroll**
  (mission-control glanceability). Display numerals and section titles scale
  via `clamp()` (already the KPI pattern); body text stays fixed — legibility
  from distance comes from numerals, not paragraphs.
- 4K at 100% scaling behaves as its CSS-pixel tier (T4/T5). No DPI hacks.
- Motion budget unchanged across tiers (Motion System is Phase 6).

## 11. Scroll & interaction policy

- Horizontal scroll: **never**, at any tier.
- T1–T3: normal vertical scroll. T4: ≤1.5 viewports. T5: none (goal).
- Sidebar and Intelligence Rail scroll independently of the main region.
- `prefers-reduced-motion` honored everywhere (already in tokens.css).

---

## 12. Implementation primitives (built after ratification)

```
useWorkspaceTier(): 'T1'|'T2'|'T3'|'T4'|'T5'     // matchMedia, one source of truth
<Workspace>                                       // owns padding + zone-gap per tier
  <Region kind="main" | "rail" | "analysis" …>    // macro-grid (T4/T5)
    <Zone row="full" | "split" | "primary" min=…> // zone-grid rows
```
New tokens: `--ws-sidebar-w`, `--ws-pad`, `--ws-zone-gap`, `--ws-card-gap`
(values per §4–§5), added to design/tokens.css.

## 13. Migration order (after ratification — matches the governing phases)

1. Build primitives (`useWorkspaceTier`, `Workspace`, `Region`, `Zone`).
2. **Remove the interim 1720px cap** from the Executive section.
3. Refactor every existing dashboard/section onto the workspace (no visual
   redesign yet — pure layout adoption).
4. Then Phase 2 (Information Architecture) → Phase 3 (Executive Dashboard
   rebuild) → Phase 4 (role dashboards) → Phase 5 (chart language) →
   Phase 6 (motion) → Phase 7 (a11y/responsive) → Phase 8 (performance) →
   Phase 9 (design documentation).

## 14. Compliance checklist (every future page)

- [ ] Composes `<Workspace>` — no bespoke page grid
- [ ] No max-width container around the workspace; no centered column
- [ ] Zones from the catalog (§8) or a ratified addition to it
- [ ] Extra width adds zones/analysis (per §9), never stretched cards
- [ ] All data from existing production APIs; empty states honest
- [ ] Prose ≤72ch; cards ≤560px; charts elastic
- [ ] No horizontal scroll at any width
