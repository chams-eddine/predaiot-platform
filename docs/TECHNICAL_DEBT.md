# PREDAIOT — Technical Debt Register

Tracked, accepted debt — deliberate trade-offs deferred to a later version. An item
here is NOT a bug: current behaviour is intentional and stable. Do not "fix" an item
without an explicit decision to schedule it.

---

## TD-001 — Live decision core is storage-oriented (single core for all asset classes)

- **Type:** Architecture Debt (NOT a bug).
- **Status:** ACCEPTED — do not change in the current version.
- **Logged:** 2026-07-23 (owner-ratified).

### Current behaviour (intentional; must NOT change now)

The Live / Real-Time path evaluates **every** stream — BESS, Solar, Wind, Hydrogen —
with a **single storage-oriented decision core**:

- Batch: `app/api/live.py::_recompute_live_state` calls the frozen
  `process_calculation` but **hardcodes `asset_type="storage"`**.
- Real-time: `app/services/telemetry_service.py::_live_decision_core` is a
  self-contained **storage-arbitrage + curtailment-recovery** evaluator, applied to
  all streams regardless of asset type.

This is stable, errors for no asset class, and ships correctly as an advisory
**Observer (Integration Level 1–2)**. It is **NOT** archetype-differentiated the way
the FROZEN Offline engine is (which routes `storage / intermittent / dispatchable /
load` via `_dispatch_mode`).

### Consequence

Live recommendations are directionally reasonable but not archetype-optimal:
Solar/Wind receive storage-style arbitrage/curtailment advice rather than
generation-specific economics; Hydrogen (a load) receives storage advice rather than
load-shifting logic. Acceptable for the advisory Observer role and the Paid Pilot.

### Why it is acceptable now

- **Zero regression:** none of the Offline-audit work (Facility, Flexibility Factor,
  Load Routing, load DQ = cost-ratio, Validation gates, TOU bands) reaches Live — all
  are gated on load-mode or the `/audit/file` endpoint, neither of which Live uses.
  Verified: 21 Live tests green; `_dispatch_mode` invariant for every Live label;
  BESS/ingest→state/step smokes pass.
- The storage-arbitrage + curtailment core covers the common real-time advisory need.
- Priority now is **Zero Regression · Stable Production · Deployable SaaS**, then the
  first Paid Pilot — not new real-time capability.

### Resolution (next version — AFTER the Paid Pilot)

Build a separate, standalone **Industrial Live Decision Engine**, fully decoupled from
the Offline Audit, providing archetype-aware real-time decisioning (mirroring the
offline archetype routing) for Live. It must be built on **real client operational
data** collected during the pilot — not on engineering assumptions.

### Explicit non-goals for the CURRENT version

- Do **not** unify the Live and Offline paths.
- Do **not** change any Live behaviour (BESS / Solar / Wind / Hydrogen stay as-is).
- Do **not** route Live through the archetype-differentiated Offline engine.

### Ratified roadmap (risk-minimising sequence)

1. Stabilise the Offline Audit. ✅
2. Stabilise Live. ✅
3. Stabilise Real-Time. ✅
4. Sign the first Paid Pilot.
5. Collect real operational data from the client.
6. Build the Industrial Live Decision Engine on that real data (not assumptions).

Boundary until then: **Live = BESS + Solar + Wind + Hydrogen only**; **Industrial Load
= Offline Audit only**. The two paths are not mixed or unified.
