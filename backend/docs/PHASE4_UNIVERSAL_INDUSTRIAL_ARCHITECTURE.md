# PREDAIOT Phase 4 — Universal Industrial Platform (Architecture RFC · rev 3)

**Status:** APPROVED direction. S1 shipped. S1′ authorized (byte-identical). Gate before S2.
**Rev 3 (2026-07-21):** adds the **Industrial Ontology Layer** — the platform models a
strict abstraction ladder *Signal → Equipment → Capability → Process → Facility*.
Industries are **emergent classifications**, never implementation units.
**Rev 2:** facility-first capability composition (packs are knowledge sources, not industries).

### The Laws (inviolable, CI-enforced)
1. **Immutable Engine.** The Economic Engine is frozen infrastructure. **Nothing outside
   `CIM.to_wire()` may ever require a change inside the optimization engine.** If a future
   industry needs engine code changed, *the architecture has failed*.
2. **No name branching.** No `if industry ==`. No `if capability ==`. Control flow keys on
   physics archetypes (engine) and declared properties (composer) — never on names.
3. **One tier per pack.** Every Knowledge Pack describes exactly one ontology tier. Packs
   are DATA (YAML, no logic).
4. **Byte-identical.** The golden fingerprint and the `test_knowledge_pack_identity` SHAs
   never move without an explicit, reviewed baseline change.

---

## 0. Executive finding + governing principle

The engine already routes on **physics archetype** (`_dispatch_mode →
{storage|intermittent|dispatchable|load}`), never industry — universalization is a
recognition + composition problem, not an engine problem. Rev 2 made it *facility-first*;
rev 3 makes the facility a **composition over a formal ontology**:

> PREDAIOT is not a steel/cement analyzer. It is an **economic operating system for
> industrial facilities**: discover a facility's equipment, capabilities, processes and
> constraints from its data, then automatically compose a canonical economic model the
> frozen engine can price. "Steel", "Cement" are labels for recurring compositions.

---

## 1. BESS-assumption inventory (rev 1, still valid — condensed)

Engine + economic domain already universal. Residual BESS-ness = canonical field
*vocabulary*, BESS-sized *defaults*, the *alias monolith* (extracted, S1), a 5-min
heat-map label, *no facility recognition*, and a *single-asset data model* (resolved by
the graph CIM + composition → F2). None touches the engine or wire schema. (Full table in
git history rev 1.)

---

## 2. Architecture

### 2.1 The Industrial Ontology (the new spine)

Five tiers. Each is a distinct level of abstraction; they must never be conflated.

```
  RAW SIGNALS      what the file literally contains (columns, sensors, tags, units)
       ▲ abstracts to
  EQUIPMENT        physical devices that emit those signals
       ▲ exhibits
  CAPABILITIES     what an equipment can do economically (a dispatch behavior or a modifier)
       ▲ enable
  PROCESSES        the industrial activity the equipment/capabilities serve
       ▲ compose
  FACILITY         the whole site
```

Concrete ladders:

```
 Power Meter  →  Electric Arc Furnace  →  Flexible Load  →  Steel Melting  →  Steel Plant
 Battery PCS  →  Battery               →  Energy Storage →  Peak Shaving   →  Hybrid Solar Facility
```

The **Facility Understanding Engine** climbs this ladder bottom-up (signals → … →
facility). The **Capability Composer** builds the model top-down (facility ⊃ processes ⊃
equipment ⊃ {signals, constraints, capabilities}). "Steel Plant" and "Hybrid Solar
Facility" are the *emergent* top of each ladder — recognized, never hardcoded.

### 2.2 The pipeline

```
Upload → Facility Understanding Engine → Industrial Knowledge Graph
       → Capability Composer → Canonical Industrial Model → (FROZEN) Economic Engine
```

- **FUE** parses any file, then grounds raw signals against the IKG to detect
  **equipment** and **capabilities** → `FacilityProfile {equipment[], capabilities[],
  processes[], signal→canonical map, confidence, unknowns[]}`.
- **IKG** is the knowledge substrate (assembled from packs) both the FUE and Composer read.
- **Composer** turns the profile into the graph CIM (Equipment → Capabilities → Processes
  → Facility), property-driven.
- **CIM.to_wire()** flattens the graph to the frozen `AssetSpecs + time_series`. The engine
  never learns the graph exists.

### 2.3 Capabilities — behavioral vs descriptive

| Class | Meaning | Maps to | Examples |
|-------|---------|---------|----------|
| **Behavioral** | *how an asset decides* | one engine archetype | `energy_storage`→storage · `flexible_load`→load · `dispatchable_generation`→dispatchable · `intermittent_generation`→intermittent |
| **Descriptive** | *what kind of process* — adds constraints/KPIs/units/labels | archetype = null | `continuous_process` · `batch_process` · `thermal` · `electrochemical` · `cogeneration` |

Behavioral capabilities → CIM assets (multiple ⇒ F2). Descriptive capabilities colour them.

### 2.4 Knowledge Packs — seven single-tier kinds

Every pack has a `kind` and describes exactly one ontology concern. Packs **reference**
other concepts by id; they never inline another tier (no mixing).

| `kind` | Tier | Describes | References |
|--------|------|-----------|-----------|
| `units` | — | engineering units + conversions | — |
| `kpi` | — | one KPI (name, formula, unit) | units |
| `constraint` | — | one constraint family (params) | units |
| `capability` | Capability | behavioral/descriptive; `class`, `archetype`, contributions | kpi, constraint, units |
| `equipment` | Equipment | an equipment class; terminology, the signal headers it is known by (`column_aliases`), `exhibits` | capability, kpi, constraint |
| `process` | Process | a process template; stages + `couplings` | capability, equipment, kpi, constraint |
| `recognition` | Signal / Facility | how to recognize a concept from raw data — `tier: signal` (header→canonical aliases) or `tier: facility` (signature → label, e.g. "Steel Plant") | — |

> **No `industry` kind exists.** Industry recognition lives in `recognition` packs
> (`tier: facility`) as *labels + confidence*, carrying zero behavior.

### 2.5 The Industrial Knowledge Graph

Assembled at startup from packs (`knowledge/graph.py`). Nodes: Signal · Equipment ·
Capability · Process · Facility-pattern · KPI · Unit · Constraint. Edges: *emits*,
*exhibits*, *enables*, *composes*, *constrains*, *measured-by*. The FUE walks it upward to
understand; the Composer walks it downward to compose. New packs extend the graph — and
therefore recognition and composition — automatically.

### 2.6 The Capability Composer

Generic platform logic (not a pack). Composes **Equipment → Capabilities → Processes →
Facility**, keying only on declared *properties*:

1. Each recognized **equipment** → a CIM `Equipment` node; bind its signals to canonical fields.
2. Its **behavioral** capabilities → a priced `Asset` with that capability's `archetype`.
3. Its **descriptive** capabilities → merge `adds_constraints / adds_kpis / adds_units / labels`.
4. Group equipment into **processes** (from `process` packs); the facility is the process set.
5. ≥2 behavioral capabilities ⇒ ≥2 assets ⇒ **F2 multi-asset**, aggregated.

`Steel = Electric Arc Furnace + Rolling Mill + Flexible Load + Thermal` — assembled from
those packs, never from a `steel` unit.

### 2.7 Canonical Industrial Model — graph-based

The CIM is a **graph**, not a flat spec:

```
Facility
 └── Process[]
      └── Equipment[]
           ├── signals:      { canonical_field → source column }
           ├── constraints:  [Constraint]
           └── capabilities: [Capability]   # behavioral ⇒ a priced asset
```

`CIM.to_wire()` is the **sole** adapter to the frozen engine: it walks the graph and emits,
per priced asset, the byte-identical `AssetSpecs + time_series` the engine reads today. For
BESS the graph is Facility→(1 process)→(1 battery)→{energy_storage} → `to_wire()` = the
current single spec = **identity**. The engine is unaware the graph exists (Law 1).

### 2.8 Directory layout

```
app/knowledge/                    # foundation leaf (rank 1) — imports nothing app-side
  schema.py                       # per-kind pydantic pack schemas (discriminated on `kind`)
  registry.py                     # discover + validate packs; merge signal aliases
  graph.py                        # build the Industrial Knowledge Graph (S2/S3)
  packs/
    units/         energy.yaml · mass.yaml
    kpi/           kwh_per_ton.yaml · round_trip_efficiency.yaml
    constraint/    demand_charge.yaml · thermal_ramp.yaml · soc_limits.yaml
    capability/    energy_storage.yaml · flexible_load.yaml · dispatchable_generation.yaml
                   intermittent_generation.yaml · thermal.yaml · continuous_process.yaml …
    equipment/     battery.yaml · electric_arc_furnace.yaml · rolling_mill.yaml · kiln.yaml …
    process/       steel_melting.yaml · peak_shaving.yaml …
    recognition/   legacy_signal_aliases.yaml (tier: signal) ; steel.yaml (tier: facility, S4)
services/facility/                # Facility Understanding Engine (S3)
  understanding.py · fingerprints.py
domain/canonical/                 # graph CIM + composer + adapter (S2)
  model.py · composer.py · to_wire.py
```

### 2.9 Faithfulness scope (unchanged)

F1 single-asset · **F2 multi-asset = the native Composer output** · **F3** cross-process
co-optimization (`process.couplings`) is **out of scope** — it changes the optimization
problem and would touch the engine (Law 1). The Composer *surfaces* couplings; it does not
co-optimize across them in Phase 4.

### 2.10 Future-proof / long-term vision

A 2035 facility needs **no new pack** if its equipment/capabilities exist — it is a new
composition the FUE recognizes. Genuinely new behavior = a new **capability** pack (data).
Only new *physics* (a 5th archetype) touches the engine — the rare, RFC-gated event.
Engine / CIM contract / Mission Control change in none of these cases.

---

## 3. Migration roadmap

| Stage | Deliverable | Engine? | Golden | Status |
|-------|-------------|---------|--------|--------|
| **S1** | `app/knowledge/` + registry + byte-identical alias extraction | no | identical | ✅ deployed (3801073) |
| **S1′** | **Ontology reconciliation:** per-kind `PackSchema` (7 kinds); recast the shipped pack into a `capability: energy_storage` pack + a `recognition: legacy_signal_aliases` (tier signal) carrying the alias bundle verbatim; registry merges signal aliases. **Byte-identical** — identity SHAs unchanged | no | **identical** | **THIS TURN** |
| **S2** | `domain/canonical/` graph CIM + Composer + `to_wire()`; BESS graph → identity on the golden fixture | no | identical | next |
| **S3** | `services/facility/` FUE + `graph.py` IKG; `/audit/inspect` returns FacilityProfile (additive) | no | unchanged | |
| **S4** | Author equipment/capability/process/kpi/constraint/units packs + `recognition tier:facility` labels (steel, cement, …) + per-industry baselines | no | new baselines | |
| **S5** | Auto-Mapping UX ("Detected: Steel Plant 94% · review") + profile labels | no | FE snapshot | |
| **S6** | F2 multi-asset composition end-to-end | no | new | |

Composition/facility-recognition packs remain **deferred to S4**.

---

## 4. Risk · 5. Back-compat · 6. Performance · 7. Testing (deltas from rev 2)

- **Risk:** ontology mis-tiering (a KPI inlined into equipment) → the per-kind schema
  (`extra=forbid`) rejects it; reference-by-id is validated by the graph builder.
  Recognition ambiguity stays advisory + confidence + human-confirm.
- **Back-compat:** wire frozen; `energy_storage`+`legacy_signal_aliases` reproduce the S1
  merged tables exactly → BESS byte-identical through S1′/S2.
- **Performance:** packs + graph built once at startup; unchanged hot path.
- **Testing:** `test_knowledge_pack_identity` SHAs unchanged (the S1′ gate); + a schema test
  that every pack validates against exactly one kind; + (S2) `to_wire(compose(BESS))` ==
  legacy wire on the golden fixture; + an arch test that engine/composer contain no
  industry/capability *name* literals in control flow (Law 2).

## 8. Assessment

The ontology is the right final abstraction: it turns PREDAIOT into an economic OS for
facilities, makes hybrids (steel + battery + PV + desal) first-class without industry
logic, and makes Law 1 (immutable engine) structurally enforceable — every future industry
is absorbed at `CIM.to_wire()` or not at all. Cost to reconcile the shipped S1 is small and
byte-identical (S1′). Proceeding with S1′ now.
