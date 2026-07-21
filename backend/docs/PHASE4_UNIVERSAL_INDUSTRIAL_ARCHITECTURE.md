# PREDAIOT Phase 4 — Universal Industrial Platform (Architecture RFC)

**Status:** PROPOSED — no code. Approval gate before implementation.
**Author:** Lead Architect pass, 2026-07-21.
**Rule of law:** the economic engine is FROZEN. No `if industry ==`. Golden tests byte-identical.

---

## 0. Executive finding — the engine is *already* universal

The single most important result of the backend inspection: **PREDAIOT does not
assume BESS at the mathematical level.** It assumes BESS at the *vocabulary* and
*packaging* level. Evidence:

- `optimization_service.py` routes on **physics archetype**, not industry:
  `_dispatch_mode(asset_type) → {storage | intermittent | dispatchable | load}`
  (`optimization_service.py:22-38`). There is **no** industry branch anywhere.
- The economic-findings domain is **already asset-agnostic and mode-aware**:
  root-cause partition, opportunities, heat-map, EDA metrics and risk band all
  derive from `gap_step` ledger rows; `_BUCKET_ACTIONS`/`_ADVISORY_IDEAS` already
  carry a full **`load`** vocabulary — "Shift consumption into cheapest windows"
  (`economics.py:142-151`) — which is exactly the steel/cement/aluminium case.
- The engine consumes a **canonical model already**: `AssetSpecs` + a
  `time_series` of `{price, observed action}` → `AuditResponse` (`schemas/__init__.py`).
  The docstring even says *"Universal fields — works for all energy assets."*
- Ingestion already maps solar/wind/hydro/gas/nuclear/electrolyzer/desal/H₂/water
  headers (and Arabic) onto those canonical fields (`ingestion/columns.py:29-174`).

**Conclusion:** steel, cement, aluminium, chemical, food, water treatment are all
the **LOAD archetype** — "a facility that consumes energy to meet a production
target; the decision is *when* to consume." `_run_optimizer_load` already solves
this (`optimization_service.py:138-169`). Making PREDAIOT universal is therefore a
**mapping, recognition, and packaging** problem — **not** an engine problem. This
is why the "don't touch the engine" rule is not just possible; it is the natural
shape of the system.

---

## 1. Phase 1 — BESS-Assumption Inventory (evidence-based)

Every residual assumption, classified. Severity = migration effort / blast radius.

| # | Location | Assumption | Class | Severity |
|---|----------|-----------|-------|----------|
| A1 | `schemas` `TimeStepData` / `DecisionRecord` fields `actual_discharge`, `actual_charge`, `soc`, `curtailment_mw` | Canonical wire vocabulary is storage-flavored | **Vocabulary** | Low — keep as canonical names; map industry terms *onto* them |
| A2 | `schemas` `AssetSpecs` `p_max/e_max/soc_init/eta_ch/eta_dis/deg_cost` | Params named for storage; `e_max/soc/eta` meaningless for load/gen | **Vocabulary** | Low — engine already ignores them off-storage |
| A3 | `AssetSpecs` defaults: `asset_type="Generic"→storage`, `p_max=50,e_max=100,deg_cost=5` | BESS-sized defaults + storage fallback | **Default** | Low — pack supplies defaults; keep storage as BESS pack default |
| A4 | `EDAMetrics.curtailed_energy_mwh`, `battery_opportunity_capture` | Unit/asset baked into field name | **Vocabulary** | Low — rename via pack label layer; keep key for API compat |
| A5 | `economics.py:273` + `_build_heat_map` label `f"{h//12:02d}:{(h%12)*5:02d}"` | Hour label hard-assumes 5-min steps (12/hour) | **Structural (minor)** | Low — derive label from real timestamp/resolution |
| A6 | `ingestion/columns.py` `COLUMN_ALIASES` (one 145-line dict) | All industry aliases hardcoded in one monolith; no per-industry plug-in; no true process signals (tap-to-tap, clinker, pot-line) | **Structural** | **Medium** — refactor into packs + extend |
| A7 | *absent* — no industry/equipment recognition anywhere | Cannot say "this is a steel plant / EAF" | **Missing capability** | **Medium** — new Layer 2 |
| A8 | Data model = **one asset, one action series, one optimizer run** | A multi-process facility (EAF + rolling mill + compressors) is not represented as a process hierarchy | **Structural (the hard one)** | **High** — see §2.7; solved by composition, NOT engine change |
| A9 | Mission Control labels ("SOLVER", "DISPATCH", "SOC") | Presentation is energy-centric | **Presentation** | Low — pack-driven label map |

**Reading of the table:** 6 of 9 items are Vocabulary/Default/Presentation —
cosmetic, additive, zero-risk. Only A6/A7 are net-new modules, and A8 is the one
genuine architectural question (answered by composition, §2.7). **Nothing here
requires editing the engine or breaking the wire contract.**

---

## 2. Phase 2 — Universal Industrial Architecture

### 2.1 The organizing principle

> Industries are **descriptions**. Physics archetypes are **behavior**.
> The engine only ever sees archetypes. Knowledge Packs translate an industry's
> world into the canonical model; they contain **zero business logic**.

### 2.2 The five layers, mapped to real modules

```
                         ┌──────────────────────────────────────────────┐
  raw file  ──►  L1 ──►  L2 ──►  build L3  ──►  [FROZEN ENGINE]  ──►  AuditResponse ──► L5
 (csv/xlsx/                                                                    (+ pack labels)
  scada/erp)
```

| Layer | Responsibility | Where it lives | Status |
|-------|----------------|----------------|--------|
| **L1 Universal Interpreter** | Parse any file; detect timestamps, units, sensors, production vars; emit confidence + unknown columns + candidate mappings | `app/services/ingestion/*` (extend) | ~70% exists |
| **L2 Industry Recognition** | From interpreted signals → {industry, asset family, process, equipment, confidence} using the Knowledge Graph | `app/services/recognition/` (**new**) | new |
| **L3 Canonical Industrial Model (CIM)** | The ONE contract the engine consumes. Formalize the existing `AssetSpecs + time_series + AuditResponse` as generic `Asset/Process/Energy/Production/Constraint/Economics/Decision`, **compiling down to the frozen wire schema** | `app/domain/canonical/` (**new, adapter-only**) + existing `schemas` | seed exists (`canonical_event.py`, EDA-ES-1.0) |
| **L4 Knowledge Packs** | Per-industry declarative data: terminology, aliases, KPIs, units, asset hierarchy, constraints, recognition fingerprints, **archetype**, default specs. No logic. | `app/knowledge/packs/<industry>/` (**new**) | new (BESS pack = extract of A6) |
| **L5 Mission Control** | Already built. Bind to CIM + pack label map. Do not rewrite. | `frontend/` | exists |

### 2.3 Data-flow diagram (the critical seam)

```
 upload ──► L1 Interpreter ──────────────► InterpretedTable
                                             { columns[], units[], signals[],
                                               timestamps, confidence, unknowns[] }
                                                     │
                                                     ▼
                          L2 Recognition ◄──── Knowledge Graph (built from L4 packs)
                                             { industry, confidence, equipment[],
                                               suggested_pack, candidate_mappings }
                                                     │
                     ┌──── user confirms / overrides mapping (Auto-Mapping UI)
                     ▼
        L4 Pack.map(InterpretedTable) ──► CIM instance
                                             { Asset(archetype), Process[],
                                               EnergySeries, ProductionSeries,
                                               Constraints, Economics }
                                                     │
                             CIM.to_wire()  ◄── ADAPTER (the only new code the
                                     │            engine "sees"; emits the
                                     ▼            byte-identical AssetSpecs+time_series)
                        ╔════════════════════════╗
                        ║  FROZEN ECONOMIC ENGINE ║  run_optimizer + economics.*
                        ╚════════════════════════╝
                                     │  AuditResponse (unchanged schema)
                                     ▼
                     L4 Pack.labels() decorates response for L5
                                     ▼
                              Mission Control
```

**The whole design rests on one invariant:** `CIM.to_wire()` produces the *exact*
`AssetSpecs`/`time_series` the engine reads today. For the BESS pack this is the
identity function → golden fingerprint (188.62 / 3848.68) stays byte-identical.

### 2.4 Module boundaries (dependency direction — extends the existing arch_graph law)

```
api  ─►  services ─►  { recognition, ingestion }  ─►  knowledge (packs, graph)
                              │                              │
                              ▼                              ▼
                         domain/canonical  ────────────►  schemas (frozen wire)
                              │
                              ▼
                     FROZEN ENGINE (optimization_service, economics)
```

Rules (CI-enforced via the existing `arch_graph.py` fitness function):
- `knowledge/` may depend on **nothing** but plain data types. **No imports of
  engine, services, or domain.** (Enforces "packs contain no business logic.")
- The engine imports **nothing** from `knowledge/`, `recognition/`, or `canonical/`.
  (Enforces "the engine never knows the industry.")
- `canonical/` depends only on `schemas`. It is a pure translator.

### 2.5 Directory layout

```
backend/app/
  knowledge/
    __init__.py
    graph.py                 # Industrial Knowledge Graph (built by loading packs)
    registry.py              # pack discovery + load + validate (schema-checked)
    schema.py                # PackSchema (pydantic) — what a pack MUST declare
    packs/
      bess/pack.yaml         # BESS = the reference pack (extracted from A6 aliases)
      solar/pack.yaml
      wind/pack.yaml
      steel/pack.yaml        # NEW industry = ONLY a new pack.yaml (+ fixtures)
      cement/pack.yaml
      aluminium/pack.yaml
      chemical/pack.yaml
      water/pack.yaml
      food/pack.yaml
      _template/pack.yaml    # the contract for authoring future industries
  services/
    recognition/
      __init__.py
      engine.py              # InterpretedTable → RecognitionResult (uses graph.py)
      fingerprints.py        # signal-signature matching
  domain/
    canonical/
      __init__.py
      model.py               # CIM dataclasses (Asset, Process, Energy, ...)
      to_wire.py             # CIM → frozen AssetSpecs/time_series (the adapter)
```

**A `pack.yaml` (declarative only — no code):**
```yaml
industry: steel
display_name: Steel Manufacturing
archetype: load                      # ← reuses the engine's existing routing
asset_family: [electric_arc_furnace, ladle_furnace, rolling_mill]
recognition:                         # ← feeds the Knowledge Graph / L2
  strong_signals: [tap_to_tap_time, kwh_per_ton, eaf_power, tons_produced]
  units_seen: [tonne, kWh/t, MW]
  keywords: [eaf, arc furnace, casting, rolling mill, ladle]
column_aliases:                      # ← replaces the monolith slice for steel
  actual_charge: [eaf_power, arc_furnace_kw, melt_power, furnace_load]
  price: [energy_price, tariff]
  production: [tons_produced, heat_weight, tapped_tons]
kpis: [kwh_per_ton, tap_to_tap_time, yield_pct, specific_energy]
constraints: [demand_charge, production_target, thermal_ramp]
defaults: { p_max: 120.0, deg_cost: 0.0 }
labels:                              # ← L5 presentation, per industry
  actual_charge: "Furnace Power"
  soc: null                          # hide storage-only instruments
```

### 2.6 The Industrial Knowledge Graph

Not a database — an **in-memory graph built at startup by loading all packs**
(`graph.py`). Nodes: Industry → AssetFamily → Equipment → {KPIs, Constraints,
Signals, Units}. Used by L2 to score `P(industry | observed signals)`. Because it
is *generated from the packs*, adding a pack extends the graph automatically —
recognition of a new industry requires no recognition-engine change.

### 2.7 The one hard question — single asset vs. process network (item A8, answered honestly)

A real steel plant is not one dispatch decision; it is many processes (EAF,
rolling mill, compressors, cooling). The current model is **one asset → one action
series → one optimizer run.** Three faithfulness levels:

| Level | What it audits | Engine change? | This phase |
|-------|----------------|----------------|------------|
| **F1 Facility-as-load** | Whole-site power vs. price: "could the same production have been met cheaper by shifting *when*?" | **None** | ✅ ship now |
| **F2 Multi-asset composition** | Each process audited as its own asset; results aggregated | **None** (loop the frozen engine; a multi-asset router already exists) | ✅ ship as follow-up |
| **F3 Process-network co-optimization** | Cross-process coupling (buffer/inventory constraints between stages) | **YES — new engine capability** | ❌ **out of scope** — would violate the freeze; a future engine RFC |

**Recommendation & honest caveat:** Phase 4 delivers **F1 + F2**. That is a *real,
defensible* economic audit for every industry listed, with zero engine risk. F3
is genuinely valuable but is a *different program* (it changes the optimization
problem itself). I will not smuggle it in under "don't touch the engine." Selling
F1/F2 as F3 would fail a Siemens/AVEVA technical review — so we scope it explicitly.

### 2.8 Future-proof requirement (per your addition)

The design satisfies "an industry that does not exist in 2035 needs only a new
Knowledge Pack" **by construction**, because:
- Packs are **data**, discovered at runtime by `registry.py` (drop-in `pack.yaml`).
- The Knowledge Graph is **generated** from packs — new pack ⇒ new recognition.
- Every industry resolves to one of the **four physics archetypes**; a 2035
  industry that is fundamentally new physics would need a 5th archetype in the
  engine — the *only* scenario that touches the engine, and a deliberate,
  rare, RFC-gated event. Adding `pack.yaml` changes **nothing** in Engine / CIM /
  Mission Control. This is the enforced contract, checked by `arch_graph.py`.

---

## 3. Phase 3 — Migration Roadmap (incremental, production-safe)

Every stage ships independently and keeps prod + golden tests green.

| Stage | Deliverable | Engine? | Golden tests | Risk |
|-------|-------------|---------|--------------|------|
| **S0** | This RFC + approval | — | — | none |
| **S1** | `knowledge/` scaffold + `PackSchema` + **BESS pack extracted from the A6 monolith** (behavior-preserving); `registry` loads it; ingestion reads aliases *from* the pack instead of the inline dict | no | **byte-identical** (BESS pack == current aliases) | low |
| **S2** | `domain/canonical/` CIM + `to_wire()` adapter; BESS path routed CIM→wire; prove identity on the golden fixture | no | byte-identical | low |
| **S3** | L2 `recognition/` + Knowledge Graph from packs; `/audit/inspect` returns `{industry, confidence, equipment, candidate_mappings, unknowns}` | no | unchanged (new fields, additive) | low |
| **S4** | Add packs: steel, cement, aluminium, chemical, water, food (+ fixtures). Each is data-only. F1 facility-as-load audits live | no | new per-industry regression baselines | med (data quality) |
| **S5** | Auto-Mapping UX in Mission Control (Detected: Steel 95% · review mapping) + pack label map | no | frontend snapshot | low |
| **S6** | F2 multi-asset composition for multi-process facilities | no | new | med |

Each stage is a PR behind the `arch_graph` fitness function; a stage that makes
`knowledge/` import the engine, or the engine import a pack, **fails CI**.

---

## 4. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Golden fingerprint drift during S1/S2 | Med | **Critical** | BESS pack + `to_wire()` are provably identity on the golden fixture; `smoke_golden.py` gates every commit |
| A pack sneaks in logic (the forbidden thing) | Med | High | `PackSchema` is pure data; `arch_graph` forbids `knowledge/`→engine imports; packs are YAML (can't import) |
| Mis-recognition (steel data called cement) | Med | Med | Recognition is *advisory* — surfaced with confidence + user confirm; never auto-runs a wrong mapping silently |
| Facility-as-load oversimplifies (F1 vs F3 gap) | High | Med | Scoped explicitly (§2.7); reports state the model level; F2 offered for granularity |
| Unit/production-signal errors for exotic industries | Med | Med | L1 confidence + `unknown columns` + human-in-the-loop mapping review |
| Scope creep into engine (F3 temptation) | Med | High | RFC freezes engine; F3 is a separate future RFC |

## 5. Backward-Compatibility Analysis

- **Wire contract frozen:** `AssetSpecs`/`TimeStepData`/`AuditResponse` field names
  unchanged; all additions are new optional fields (recognition, pack labels).
- **BESS path:** BESS becomes the default pack; `to_wire()` is identity ⇒ existing
  `/api/v1/audit*` responses are byte-identical. `smoke_golden.py`,
  `report_baseline.json`, `crypto_baseline.json` remain the gate.
- **APIs:** no endpoint removed/renamed; `/audit/inspect` gains fields only.
- **Mission Control:** reads the same response; pack labels default to today's
  strings when a pack omits them.
- **Certificates:** input hash + Ed25519 unaffected (same canonical bytes for BESS).

## 6. Performance Considerations

- Packs load **once at startup** into the graph (O(#packs), tiny). No per-request I/O.
- Recognition is O(#signals × #packs) vector scoring — microseconds; runs once per
  upload, not per step.
- `to_wire()` is a field rename/copy — negligible vs. the MILP solve (the cost center).
- The engine's 45s CBC wall-clock cap and step counts are untouched.
- No new hot-path allocations; CIM is built once per audit, not per interval.

## 7. Testing Strategy

- **Invariant (highest bar):** `smoke_golden.py` byte-identical through S1–S3.
  A dedicated `test_bess_pack_identity` asserts BESS-pack `to_wire()` == legacy
  path on the golden fixture.
- **Per-pack regression:** each industry pack ships a fixture + frozen baseline
  (like `twin.py` does for BESS) → a per-industry golden report.
- **Recognition tests:** labelled fixtures per industry; assert top-1 industry +
  confidence band; adversarial/hybrid files (Solar+BESS) assert graceful ambiguity.
- **Architecture tests:** extend `arch_graph.py` — assert `knowledge/` has no
  forbidden edges; assert engine imports nothing industry-aware.
- **Property test:** for any pack, `to_wire(CIM).time_series` conforms to
  `TimeStepData` and the engine runs without a pack-specific branch.
- **Contract test:** `AuditResponse` schema hash unchanged (no accidental field
  break).

---

## 8. Architect's recommendation (what to do, what I'd push back on)

**Do:** approve S0→S3 (scaffold + BESS-pack extraction + CIM adapter + recognition)
as the foundation. It is almost pure de-risking: it externalizes the alias
monolith, formalizes the canonical model, and adds recognition — all with a
byte-identical BESS path. This is the work that makes every future industry a
data-only drop-in.

**Push back on:** treating Phase 4 as "PREDAIOT now optimizes steel plants." It
will *audit* them (F1/F2) truthfully and look native in Mission Control — but
full cross-process co-optimization (F3) is a future engine program. Naming that
boundary now is what separates a platform from a demo.

**One decision I need from you** before S1 (it sets the pack format for a decade):
packs as **YAML data files** (recommended — non-engineers can author, obviously
logic-free) vs. **Python dataclasses** (typed, but tempts logic in). I recommend
YAML + a strict `PackSchema` validator.
