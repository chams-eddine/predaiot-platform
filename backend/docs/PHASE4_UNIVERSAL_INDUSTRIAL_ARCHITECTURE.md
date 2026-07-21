# PREDAIOT Phase 4 — Universal Industrial Platform (Architecture RFC · rev 2)

**Status:** PROPOSED — no code beyond S1 (already shipped). Approval gate before S2.
**Rev 2 (2026-07-21):** refined from *industry packs* to **facility-first capability
composition** — the platform understands **facilities, not industries**. Industries
become compositions of reusable capabilities, never `steel.yaml`.
**Rule of law:** engine FROZEN · no `if industry ==` · **no `if capability ==`** ·
packs are DATA (no logic) · golden tests byte-identical.

---

## 0. Executive finding + the rev-2 principle

The backend inspection proved the engine does **not** assume BESS mathematically —
it routes on **physics archetype** (`_dispatch_mode → {storage | intermittent |
dispatchable | load}`, `optimization_service.py:22-38`), with no industry branch,
and the economic-findings domain is already asset-agnostic. Universalization is a
**recognition + composition + mapping** problem, never an engine problem.

**Rev-2 principle — understand facilities, not industries.** A real facility is not
a member of a taxonomy; it is a *bundle of what it does*. A steel plant that also
runs on-site solar and a battery is not "steel" — it is:

```
Steel Plant  =  Continuous Process  +  Thermal  +  Flexible Load  +  Dispatchable  (+ on-site PV + Storage)
```

So the platform recognizes **capabilities** and **equipment** from the data, and a
facility *emerges* as their composition. "Industry" is only a **name we recognize
for a common composition** — a label, never a behavior. This is strictly more
powerful than per-industry packs: it handles hybrids, multi-process sites, and
industries that do not exist yet, with the same primitives.

---

## 1. BESS-assumption inventory (from rev 1 — still valid, condensed)

The engine + economic domain are already universal; residual BESS-ness is:
**vocabulary** (canonical field names `discharge/charge/soc/curtailment_mw`),
**defaults** (`asset_type→storage`, BESS-sized numerics), **a monolithic alias
table** (now extracted — §3 S1), **a 5-min heat-map label**, **no facility
recognition**, and **a single-asset data model** (the one structural item, resolved
by composition → F2). None requires editing the engine or the wire schema. Full
table in git history of this file (rev 1).

---

## 2. Architecture — Facility-First, Capability-Composed

### 2.1 The pipeline (your six stages, made precise)

```
   Upload
     │        any file (csv/xlsx/scada/historian/erp/mes)
     ▼
 ┌─────────────────────────────┐
 │ 1. Facility Understanding   │  parse + interpret signals; ground them against
 │    Engine (FUE)             │  the graph → detect EQUIPMENT + CAPABILITIES
 └─────────────┬───────────────┘  → FacilityProfile {equipment[], capabilities[],
     │  queries │                     signal→canonical map, confidence, unknowns[]}
     ▼          ▼
 ┌─────────────────────────────┐
 │ 2. Industrial Knowledge     │  the shared substrate, ASSEMBLED FROM PACKS:
 │    Graph (IKG)              │  Capability ↔ Equipment ↔ KPI ↔ Unit ↔ Signal ↔
 └─────────────┬───────────────┘  Constraint ↔ ProcessTemplate. Read by FUE + Composer.
     │
     ▼
 ┌─────────────────────────────┐
 │ 3. Capability Composer      │  GENERIC, property-driven: turns the detected
 │                             │  capabilities into a coherent facility model.
 └─────────────┬───────────────┘  Behavioral caps → assets (with archetypes);
     │                              descriptive caps → constraints/KPIs/units/labels.
     ▼
 ┌─────────────────────────────┐
 │ 4. Canonical Industrial     │  Asset[] · Process[] · Energy · Production ·
 │    Model (CIM)             │  Constraints · Economics · Decisions.
 └─────────────┬───────────────┘  CIM.to_wire() → the FROZEN AssetSpecs+time_series.
     ▼
 ┌─────────────────────────────┐
 │ 5. Economic Engine (FROZEN) │  run_optimizer + economics.*  (never sees a
 └─────────────┬───────────────┘   facility, capability, or industry)
     ▼
        AuditResponse ──► Mission Control (labels resolved from the profile)
```

The IKG is not a sequential transform so much as the **knowledge substrate** the
FUE consults to *understand* and the Composer consults to *compose*. Both are
generated from Knowledge Packs, so extending knowledge extends both at once.

### 2.2 Capabilities — the reusable unit of industrial behavior

A **Capability** is a reusable, industry-independent unit of what a facility does.
Two classes — the distinction is load-bearing:

| Class | Meaning | Maps to | Examples |
|-------|---------|---------|----------|
| **Behavioral** | *how an asset decides* — implies a dispatch archetype | one engine archetype | `energy_storage`→storage · `flexible_load`→load · `dispatchable_generation`→dispatchable · `intermittent_generation`→intermittent |
| **Descriptive** | *what kind of process* — adds constraints / KPIs / units / labels, **no dispatch behavior** | archetype = null | `continuous_process` · `batch_process` · `thermal` · `electrochemical` · `cogeneration` |

A facility's **behavioral** capabilities determine its asset decomposition and
archetypes (→ possibly multi-asset, F2). Its **descriptive** capabilities enrich
the CIM (thermal ramp constraints, kWh/ton KPIs, °C units, UI labels). This is why
`Steel = Continuous + Thermal + Flexible Load (+ Dispatchable)` works: two
descriptive modifiers colour a `load`-archetype asset (plus a `dispatchable` asset
if on-site generation is present).

### 2.3 Knowledge Packs, redefined — knowledge SOURCES, never industries

A pack describes **one reusable thing**. It has a `kind`; it is pure YAML data,
validated by a per-kind schema; it contains no logic and no industry.

| Pack `kind` | Describes | Key fields |
|-------------|-----------|-----------|
| `capability` | a behavioral or descriptive capability | `class`, `archetype` (or null), `signals`, `column_aliases`, `kpis`, `constraints`, `adds_units` |
| `equipment` | an equipment class | `exhibits: [capability…]`, `terminology`, `column_aliases`, `kpis`, `recognition` |
| `units` | an engineering unit system + conversions | `units`, `conversions` |
| `process_template` | a reusable process pattern | `stages`, `couplings` |
| `constraint` | a constraint family | `parameters`, `applies_to` |
| `composition` | **a named, recognizable bundle** ("Steel Plant") — **label + recognition only, ZERO behavior** | `display_name`, `typical_capabilities`, `typical_equipment` |

> **There is no `industry` pack kind.** "Steel" exists only as an optional
> `composition` used to *label* and *boost recognition confidence* — the platform
> audits the facility correctly even if no such composition exists.

### 2.4 The Capability Composer — the second law of non-coupling

The Composer is **generic platform logic** (allowed to have logic; it is not a
pack). Its inviolable rule mirrors "no `if industry ==`":

> **The Composer branches on capability PROPERTIES declared in pack data, never on
> capability or industry NAMES.** No `if capability.id == "thermal"`. It reads
> `capability.class`, `capability.archetype`, `capability.adds_constraints`, etc.

Algorithm (uniform for every facility, present and future):
1. For each **behavioral** capability in the profile → instantiate a CIM `Asset`
   with `capability.archetype`; bind its signals to the canonical action series.
2. For each **descriptive** capability → merge its `adds_constraints / adds_kpis /
   adds_units / labels` into the asset(s) it applies to.
3. ≥2 behavioral capabilities → ≥2 CIM assets → **F2 multi-asset** audit, aggregated.
4. `CIM.to_wire()` emits the byte-identical `AssetSpecs + time_series` per asset.

**Three Laws of Non-Coupling** (all CI-enforced by `arch_graph` + schema):
- **Engine** sees only archetypes.
- **Composer** sees only capability *properties*.
- **Packs** are data — no logic at all.
Nobody, at any layer, branches on an industry or capability *name*.

### 2.5 Worked example — Steel Plant, bottom-up

```
upload (EAF_Power_kW, Tons_Produced, Energy_Price, PV_Output_MW, BESS_SOC…)
  FUE grounds signals via IKG →
    equipment:    electric_arc_furnace, rolling_mill, solar_array, battery
    capabilities: {flexible_load(behavioral,load), thermal(desc),
                   continuous_process(desc), intermittent_generation(behavioral,
                   intermittent), energy_storage(behavioral,storage)}
    → recognized composition "Steel Plant" @ 0.94 (label only)
  Composer →
    Asset A (load)         ← EAF+mill flexible load, +thermal/continuous constraints+KPIs
    Asset B (intermittent) ← PV
    Asset C (storage)      ← battery
  to_wire → 3 frozen audits → aggregated (F2)
  Mission Control → labels "Furnace Power", "kWh/ton", hides SoC on A, shows it on C
```

No `steel.yaml` decides any of this. Change the facility (drop the PV) and the
model changes automatically — because it was never "steel," it was a composition.

### 2.6 Module boundaries + directory layout (revised)

```
app/knowledge/                 # foundation leaf (rank 1) — imports nothing app-side
  schema.py                    # per-KIND pack schemas (capability/equipment/units/…)
  registry.py                  # discover + validate packs
  graph.py                     # build the Industrial Knowledge Graph from packs (NEW)
  packs/
    capabilities/  energy_storage.yaml · flexible_load.yaml · dispatchable_generation.yaml
                   intermittent_generation.yaml · continuous_process.yaml · thermal.yaml · …
    equipment/     battery.yaml · electric_arc_furnace.yaml · rolling_mill.yaml · kiln.yaml · …
    units/         energy.yaml · mass.yaml
    process_templates/  melt_cast_roll.yaml
    compositions/  steel.yaml · cement.yaml   # recognition labels only (no behavior)
services/facility/             # Facility Understanding Engine (NEW)
  understanding.py             # parse (via ingestion) + recognize (via graph) → FacilityProfile
  fingerprints.py
domain/canonical/              # (NEW) — depends only on schemas + knowledge
  model.py                     # CIM dataclasses
  composer.py                  # Capability Composer (generic, property-driven)
  to_wire.py                   # CIM → frozen AssetSpecs/time_series
```

Dependency law (extends `arch_graph`): `knowledge` imports nothing but stdlib +
yaml + itself. Engine imports nothing from `knowledge / facility / canonical`.
`domain/canonical` may read capability *properties* from `knowledge` (data), never
the engine. CI fails on any violation.

### 2.7 Faithfulness scope (unchanged, re-expressed through composition)

- **F1** — a facility with one behavioral capability (or aggregated whole-site
  load) → single-asset audit. **No engine change. Ship.**
- **F2** — multiple behavioral capabilities → multiple assets, aggregated. This is
  now the *native* output of the Composer. **No engine change.**
- **F3** — cross-process co-optimization (inventory/buffer coupling *between*
  stages, e.g. `process_template.couplings`). **Requires new engine capability →
  out of scope**, a future engine RFC. The Composer will detect and *surface*
  couplings but will not co-optimize across them in Phase 4.

### 2.8 Future-proof (stronger under composition)

A 2035 industry needs **no new pack at all** if its capabilities already exist —
it is simply a new composition the FUE recognizes. If it introduces genuinely new
industrial *behavior*, that is a new **capability pack** (still pure data). Only a
fundamentally new *physics* (a 5th archetype) touches the engine — the rare,
RFC-gated event. Engine / CIM / Mission Control change in none of these cases.

---

## 3. Migration roadmap (revised — incl. reconciling the shipped S1)

| Stage | Deliverable | Engine? | Golden | Status |
|-------|-------------|---------|--------|--------|
| **S1** | `app/knowledge/` + registry + byte-identical alias extraction | no | byte-identical | ✅ done + deployed (3801073) |
| **S1′** | **Reconcile to facility-first:** per-`kind` PackSchema; recast the shipped `bess` pack as a **`capability: energy_storage`** pack still carrying the legacy alias bundle verbatim (rename, not re-order → byte-identical); `graph.py` assembles the IKG | no | **byte-identical** (same merged aliases; identity test still passes) | **next** |
| **S2** | `domain/canonical/` CIM + Composer + `to_wire()`. BESS = one `energy_storage` behavioral cap → one storage asset → `to_wire()` identity on the golden fixture | no | byte-identical | after S1′ |
| **S3** | `services/facility/` FUE + IKG recognition; `/audit/inspect` returns FacilityProfile {equipment, capabilities, composition-label, confidence, candidate_mappings, unknowns} (additive) | no | unchanged | |
| **S4** | Author capability + equipment packs (thermal, flexible_load, continuous_process, EAF, kiln, electrolyzer, …) + composition labels (steel, cement, aluminium, chemical, water, food) + per-industry fixtures/baselines | no | new baselines | |
| **S5** | Auto-Mapping UX in Mission Control ("Detected: Steel Plant 94% · review mapping") + profile-driven labels | no | FE snapshot | |
| **S6** | F2 multi-asset composition wired end-to-end | no | new | |

**S1′ is the immediate next step** (it reflects this refinement in code) and is
byte-identical — the `test_knowledge_pack_identity` SHAs must not move.

---

## 4. Risk analysis (updated)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Golden drift in S1′/S2 | Med | **Critical** | Same SHAs frozen; `to_wire()` identity on the golden fixture; `smoke_golden` + identity test gate |
| **Recognition ambiguity** (compositional recognition is harder than a flat industry lookup) | **High** | Med | Recognition is advisory + confidence-scored + human-confirmed; the audit runs on detected *capabilities* even if the composition label is wrong/absent |
| Composer grows industry-specific branches (the new forbidden thing) | Med | High | "No `if capability ==`" law; Composer reads only declared properties; code review + a lint/arch test |
| A pack carries logic | Med | High | per-kind pydantic schemas (`extra=forbid`); YAML can't import |
| Over-decomposition (too many tiny assets) | Med | Med | Composer aggregates by default; multi-asset only when behavioral caps genuinely differ |
| F1/F2 mistaken for F3 | High | Med | Scoped in §2.7; couplings surfaced, not co-optimized |

## 5. Backward-compatibility

Wire contract frozen; all additions optional. BESS path stays byte-identical
through S1′/S2 (`energy_storage` cap → storage asset → identity `to_wire()`).
`/audit/inspect` gains fields only. Mission Control labels default to today's
strings when a profile omits them. Certificates unaffected (same canonical bytes).

## 6. Performance

Packs + IKG built once at startup (O(#packs)). Recognition is O(#signals ×
#graph-nodes) once per upload. Composer builds the CIM once per audit. `to_wire()`
is a copy. The MILP solve remains the only cost center; its 45 s cap is untouched.
Multi-asset (F2) is N independent solves — parallelizable, bounded by N.

## 7. Testing strategy (updated)

- **Invariant:** `test_knowledge_pack_identity` SHAs unchanged through S1′/S2; a
  `test_bess_composition_identity` asserts `to_wire(compose(BESS profile))` == the
  legacy wire input on the golden fixture.
- **Capability tests:** each capability pack ⇒ a fixture asserting the Composer
  produces the expected asset archetype + merged constraints/KPIs.
- **Composition tests:** labelled facility fixtures (steel, hybrid steel+PV+BESS)
  assert detected capabilities + composition label + confidence; adversarial hybrids
  assert graceful multi-asset decomposition.
- **Non-coupling tests (architecture):** `arch_graph` — no forbidden edges; a
  source scan asserts the engine and Composer contain no industry/capability *name*
  literals in control flow.
- **Property test:** for any capability set, `to_wire(compose(...))` conforms to
  `TimeStepData` and runs without a name branch.

## 8. Architect's assessment of the refinement

**This is the right call and it is strictly better.** Per-industry packs are a
taxonomy that breaks on the first hybrid facility; capability composition models
what facilities actually *are*, maps 1:1 onto the engine's archetypes, makes F2 the
natural output, and future-proofs by recombination rather than enumeration.

**The one honest trade-off:** compositional recognition is *harder* than a flat
"steel.yaml" lookup — the FUE must infer capabilities from signals and may be
ambiguous on messy real-world exports. Mitigated by: recognition is advisory +
confidence-scored + human-confirmed, and the audit depends on **capabilities**
(which are more robustly detectable from signals) rather than the industry label.

**Cost to reconcile the shipped S1:** small and byte-identical — S1′ is a schema
`kind` model + re-filing the `bess` pack as an `energy_storage` capability pack
with the same alias bytes. The frozen SHAs do not move.

**Decision needed before S1′:** whether `composition` label packs (steel, cement)
ship in S1′ scaffolding (empty, for the recognition UX) or are deferred to S4 with
the real per-industry work. I recommend deferring them to S4 — S1′ stays a pure,
byte-identical reconciliation.
