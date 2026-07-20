# PREDAIOT Motion Identity — SPEC-MI (Status: PROPOSED)

> **Thesis (ratified direction, 2026-07-20):** PREDAIOT does not imitate Siemens/
> Honeywell dashboards — it owns a visual language where **the mathematics itself
> moves**. Someone seeing the screen from across a room says "هذه PREDAIOT"، لا
> "هذه Dashboard أخرى". Mission Control, not chart gallery.

## The governing rule that makes it inimitable

**MI-0 · No-Fabrication Motion.** Every animation is DRIVEN by real audit data —
positions, counts, magnitudes, colors and timing derive from ledger rows, solver
telemetry, or cryptographic events. Decorative motion that encodes nothing is
forbidden. This is why competitors can't copy it: the motion IS the analysis.

## Signature set (each with its honest data anchor)

| # | Concept | What the viewer sees | Real data it binds to (already in the API) |
|---|---|---|---|
| MI-1 | **Digital Twin Pulse** | Energy flowing grid↔asset↔load; leaks bleed RED at the intervals where value was lost; PREDAIOT's counterfactual turns the flow GREEN | `decision_log[]` per-step: `gap_step`, `optimal_action` vs `actual_action` |
| MI-2 | **Decision Engine** | 288 decision-points streaming; alternatives visibly rejected until one remains → "Optimal Decision Found" | 288 ledger rows; MILP branch-and-bound genuinely rejects thousands of nodes (CBC) — phrase from solver reality, never invented counts |
| MI-3 | **Economic Recovery Counter** | The money figure counts up from 0 — each increment ANNOTATED with its cause | `opportunities[].period_gain` + bucket names (exact ledger partition — the counter's segments must sum to the real total) |
| MI-4 | **Digital Fingerprint** | The Ed25519 seal laser-etches onto the report → "Verified · Tamper-Proof" | real `certificate_id`, `signature_ed25519`, `payload_sha256` — animation completes only when the real payload exists |
| MI-5 | **Energy Flow Network** | Continuously moving light-lines between equipment; congestion/loss slows + recolors flow | live window `LiveEvent` stream / `heat_map[]` statuses |
| MI-6 | **Predictive Timeline** | Time flows past→future: the without-PREDAIOT path vs the with-decisions path | `edv_actual_step` vs `edv_optimal_step` cumulative curves (both already computed; no forward projection beyond the audited span — recorded-period rule holds) |

## Binding order (the user's condition — normative)

1. **Core UX complete first** (current items: density, Live/RT merge, share UI).
2. **All functions stabilized.**
3. **Motion Design System before any animation:** palette (extends
   `src/design/tokens.css`), Motion Language (how energy moves, how numbers
   reveal, how loss "bleeds"), transition speeds (one tempo scale, not per-widget
   whims), easing signatures.
4. **Then** signature animations land gradually, each serving the six-act story —
   never distracting from it. One at a time, preview-verified, behind the same
   commit discipline.

## Non-goals

- No random/decorative animations; no motion on data we don't have.
- No animation that delays comprehension (motion must reduce time-to-insight).
- `prefers-reduced-motion` honored everywhere (SPEC-AX stays sovereign).

_Ratification: this spec is PROPOSED until the user ratifies scope + order.
Implementation begins only after step 1–2 above are done._
