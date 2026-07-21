# PHASE 3.1 — Visual DNA Audit (no code)

Goal: map where visual values live **before** removing duplication. Evidence-based;
every claim cites a file. This is the reference the 3.2 token work builds on.

## System map (as-is)

```
src/
├── design/
│   ├── tokens.css      ← --pds-* (≈40 semantic vars) + --pdm-* (7 motion vars)  [CANONICAL]
│   ├── ds.js           ← PDS{} + MC{} : JS mirrors that READ the CSS vars (var())  [GOOD: no values]
│   ├── components.jsx  ← Panel, KpiCard, AnimatedNumber, GradeBadge, EvidenceBadge,
│   │                     StatusDot, SectionShell, SectionTitle, Sparkline, Divider
│   └── mission.js      ← Mission* facade (re-exports; no values)                  [GOOD]
├── instruments/theme.jsx ← chart theme (reads tokens)
├── workspace/Workspace.jsx ← Workspace, Zone (layout)
├── motion/*            ← MI instruments (inline var(--x,#fallback) styles)
└── App.jsx             ← DS{} legacy palette + Card{} legacy primitive + heavy inline styles
```

## The 7 questions, answered

| Question | Answer | Evidence |
|---|---|---|
| Where are **colors** defined? | **3 places.** `tokens.css` `--pds-*`/`--pdm-*` (canonical) · `App.jsx` `DS{}` hardcoded hexes (stale mirror) · inline `var(--x,#hex)` fallbacks in `motion/*` | `tokens.css:9-203`, `App.jsx:118-142`, 60+ hex literals in motion/* |
| Where are **spacings** defined? | `--pds-s1..s9` (4/8/12/16/24/32/48/64/96) canonical + `PDS.s*` mirror — but **not enforced**; many raw px in inline styles | `tokens.css:92-93`; raw `gap:16`, `padding:'20px 24px'` throughout |
| Is there **one scale**? | Spacing: one concept (8-pt), unenforced. Radius: **two** parallel scales with identical values, different names | see radius row |
| Is there **one radius**? | **No.** `--pds-r-sm/r/r-lg/r-xl` = 10/14/18/24 **and** `DS.r8/r12/r16/r20` = 10/14/18/24 (dupe) **and** hardcoded `borderRadius:12/14/8` in motion/* | `tokens.css:96`, `App.jsx:141`, motion/* |
| Is there **one typography**? | Values yes (Inter + JetBrains Mono), **defined twice**: `--pds-font-sans/mono` and `DS.mono/DS.sans` (DS stack is thinner — missing `ui-monospace`/`SF Mono`). `tnum` only where `.pds-num`/`.pdm-mono` classes are applied | `tokens.css:88-89`, `App.jsx:139-140` |
| **Multiple shadows**? | `--pds-shadow-1/-2`, `--pds-glow-accent/-loss` canonical + inline `boxShadow` literals + `DS` glow pattern `0 0 28px ${glow}12` | `tokens.css:99-102`, `App.jsx:160` |
| **Multiple Card versions**? | **Yes, ≥4:** `Panel` + `KpiCard` (design/components) · `Card` (App.jsx:156, legacy, uses DS) · `RatingCard` (components/) | those files |

## Core finding

A single source of truth **exists** (`tokens.css` → `PDS`/`MC`), but it is **shadowed by a
legacy parallel layer** that has already begun to drift:

- 🔴 **`DS{}` (App.jsx:118-142)** — a full parallel palette + radius + type source. Already
  diverged: `DS.border = rgba(255,255,255,0.07)` ≠ `--pds-border = #1B2536`. **#1 duplication.**
- 🟡 **`Card` (App.jsx:156)** — a second card primitive competing with `Panel`.
- 🟢 **inline `var(--x,#hex)` fallbacks** in motion/* — cosmetic; the token still wins. Low risk.

## Consolidation targets (ranked, for 3.2+)

1. 🔴 Convert `DS{}` from hardcoded hexes → `var(--pds-*)` reads, so it can never drift again.
   (Keeps every `DS.x` call site working — no component rewrite.)
2. 🟡 Route the legacy `Card` through `MissionPanel`/`Panel` (one primitive).
3. 🟢 Opportunistically replace raw px radii/spacing with tokens when a file is already being touched.

## The `--mission-*` decision (reconciling the constraint)

The proposed `--mission-bg / --mission-panel / --mission-loss / --mission-grid / …` names are
right — but if they hold **new hex values**, they become a **third** value-set (more duplication),
and renaming every `--pds-*` → `--mission-*` would be a mass rewrite (violates "don't rewrite").

**Recommendation — Mission = a semantic ALIAS layer, not new values:**

```css
:root {
  /* Mission vocabulary → points at the ONE value source (--pds-*/--pdm-*) */
  --mission-bg:        var(--pds-bg-1);
  --mission-panel:     var(--pds-panel);
  --mission-border:    var(--pds-border);
  --mission-success:   var(--pdm-optimal);   /* live-motion layer */
  --mission-warning:   var(--pdm-warning);
  --mission-loss:      var(--pdm-leak);
  --mission-glow-green: var(--pdm-optimal-glow);
  --mission-glow-red:   var(--pdm-leak-glow);
  --mission-radius:    var(--pds-r-lg);
  --mission-grid:      8px;                   /* only genuinely-new token */
}
```

Result: new Mission components speak the clean `--mission-*` language; values still live in
exactly one place; nothing existing is rewritten. This satisfies all three goals at once —
single source of truth · Mission\* as a layer · no rewrites.
