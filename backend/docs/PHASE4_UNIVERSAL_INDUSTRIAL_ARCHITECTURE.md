# PREDAIOT Phase 4 — Universal Industrial Platform (Architecture RFC · rev 6)

**Status:** APPROVED. S1 + S1′ + S2 + S3 shipped (byte-identical, deployed). S4 in progress.
**Rev 6 (2026-07-21):** adds **Industrial Evidence Patterns** (§2B) — the layer between
Facts and Concepts. Industrial knowledge is not `Rule #27`; it is `Evidence A + B + C →
Pattern → Possible Equipment`. Three knowledge levels (Facts → Patterns → Concepts), and a
**Pattern Stability Test**: removing one piece of evidence must DOWNGRADE the conclusion to a
more general concept ("Possible High Power Furnace 0.54, need more evidence"), never keep
asserting the specific one (EAF). S4 is Industrial Knowledge Engineering, not YAML authoring.
**Rev 5 (2026-07-21):** the **Facility Understanding contract** (§2A) — S3 answers *"what is
in front of me?"*, not *"what is the plant's name?"*. Four rules: FacilityProfile is its
ONLY output · every inference is evidence-backed + confidence-scored (No Guess Without
Evidence) · the Knowledge Graph stores knowledge not conclusions · Explainability is a test.
**Rev 4 (2026-07-21):** adds the **Operational Intent** ontology tier — the objective a
facility is operated for (arbitrage, peak-shaving, reserve, CO₂ reduction, maintenance, …),
**independent of equipment**. Intent influences ONLY constraint generation + `CIM.to_wire()`;
the engine stays unaware of it (Law 1 preserved).
**Rev 3:** the **Industrial Ontology Layer** — abstraction ladder
*Signal → Equipment → Capability → Process → Intent → Facility*. Industries are **emergent
classifications**, never implementation units.
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

Six tiers. Each is a distinct level of abstraction; they must never be conflated.

```
  RAW SIGNALS      what the file literally contains (columns, sensors, tags, units)
       ▲ abstracts to
  EQUIPMENT        physical devices that emit those signals
       ▲ exhibits
  CAPABILITIES     what an equipment can do economically (a dispatch behavior or a modifier)
       ▲ enable
  PROCESSES        the industrial activity the equipment/capabilities serve
       ▲ serve
  OPERATIONAL      the objective the site is operated for — arbitrage · min-cost ·
  INTENT           max-throughput · peak-shaving · grid-support · reserve · CO₂-reduction ·
                   maintenance · demand-response. INDEPENDENT of equipment.
       ▲ frames
  FACILITY         the whole site
```

Concrete ladders (signal → equipment → capability → process → intent → facility):

```
 Power Meter → Electric Arc Furnace → Flexible Load  → Steel Melting     → Min Cost     → Steel Plant
 Battery PCS → Battery              → Energy Storage → Energy Time-Shift → Peak Shaving → Hybrid Solar Facility
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
  processes[], intent, signal→canonical map, confidence, unknowns[]}`.
- **IKG** is the knowledge substrate (assembled from packs) both the FUE and Composer read.
- **Composer** turns the profile into the graph CIM (Equipment → Capabilities → Processes
  → **Intent** → Facility), property-driven. Intent selects/parameterizes constraints and
  shapes `to_wire()`; it never reaches the engine.
- **CIM.to_wire()** flattens the graph to the frozen `AssetSpecs + time_series`. The engine
  never learns the graph — or the intent — exists.

### 2.3 Capabilities — behavioral vs descriptive

| Class | Meaning | Maps to | Examples |
|-------|---------|---------|----------|
| **Behavioral** | *how an asset decides* | one engine archetype | `energy_storage`→storage · `flexible_load`→load · `dispatchable_generation`→dispatchable · `intermittent_generation`→intermittent |
| **Descriptive** | *what kind of process* — adds constraints/KPIs/units/labels | archetype = null | `continuous_process` · `batch_process` · `thermal` · `electrochemical` · `cogeneration` |

Behavioral capabilities → CIM assets (multiple ⇒ F2). Descriptive capabilities colour them.

### 2.4 Knowledge Packs — eight single-tier kinds

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
| `intent` | Operational Intent | an operational objective; the constraints it generates + the `to_wire` params it shapes | constraint, units |
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
Intent → Facility**, keying only on declared *properties*:

1. Each recognized **equipment** → a CIM `Equipment` node; bind its signals to canonical fields.
2. Its **behavioral** capabilities → a priced `Asset` with that capability's `archetype`.
3. Its **descriptive** capabilities → merge `adds_constraints / adds_kpis / adds_units / labels`.
4. Group equipment into **processes** (from `process` packs); the facility is the process set.
5. Apply the facility **Intent**: merge its declared constraints + `to_wire` params onto the
   assets (property-driven — no `if intent ==`). Default intent per archetype reproduces
   today's behavior exactly (empty constraints, empty params).
6. ≥2 behavioral capabilities ⇒ ≥2 assets ⇒ **F2 multi-asset**, aggregated.

`Steel = Electric Arc Furnace + Rolling Mill + Flexible Load + Thermal` — assembled from
those packs, never from a `steel` unit.

### 2.7 Canonical Industrial Model — graph-based

The CIM is a **graph**, not a flat spec:

```
Facility  (intent: Intent)
 └── Process[]
      └── Equipment[]
           ├── signals:      { canonical_field → source column }
           ├── constraints:  [Constraint]     (from descriptive caps + intent)
           └── capabilities: [Capability]     # behavioral ⇒ a priced asset
```

`CIM.to_wire()` is the **sole** adapter to the frozen engine: it walks the graph, applies
the intent's constraints/params, and emits per priced asset the byte-identical
`AssetSpecs + time_series` the engine reads today. For BESS the graph is
Facility(intent: arbitrage)→(1 process)→(1 battery)→{energy_storage} → `to_wire()` = the
current single spec = **identity**. The engine is unaware the graph or the intent exists (Law 1).

**Intent expressiveness (honest scope).** Intent shapes the audit ONLY through constraints +
`to_wire` parameter reshaping — never the engine's objective function:
- **I1 (in scope):** intents expressible as bounds / availability caps / reserve margins /
  production targets / effective-price reshaping — e.g. CO₂ = carbon-adjusted price;
  Maintenance = capped `p_max`; Reserve = withheld capacity; Demand Response / Max Throughput
  = load-shift targets; Arbitrage / Min Cost = the archetype defaults. The engine solves its
  SAME objective on reshaped inputs.
- **I2 (out of scope — future engine RFC):** intents requiring a DIFFERENT objective function
  (e.g. true demand-charge co-optimization). The Composer *surfaces* them; it does not solve
  them — that would touch the engine and break Law 1.

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
    process/       steel_melting.yaml · energy_time_shift.yaml …
    intent/        arbitrage.yaml · peak_shaving.yaml · reserve.yaml · co2_reduction.yaml · maintenance.yaml …
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

## 2A. Facility Understanding — the S3 contract (four rules)

S3 (the **Facility Understanding Engine**) answers **"what is in front of me?"** Its job is
*understanding*, not analysis. Four inviolable rules:

**Rule 1 — FacilityProfile is S3's ONLY output.** Not an audit, recommendation, decision, or
optimization — those live downstream of `to_wire()`. S3 produces exactly one artifact: a
`FacilityProfile`.

**Rule 2 — Evidence-based + confidence-scored (No Guess Without Evidence).** Every element is
an `Inference {value, confidence, source, evidence[], rule?}` — never a bare value. When the
evidence is weak, S3 keeps the *distribution* and admits ignorance rather than guessing:

```yaml
facility_type:
  value: steel_melting        # or, when unproven:
  confidence: 0.97            #   candidates: [Battery Storage 0.63, Microgrid 0.29, Unknown 0.08]
  source: ontology
  evidence: [transformer_30MVA, electric_arc_furnace, CRT_tariff]
  rule: OR-27
```

`Unknown` is a first-class, legitimate outcome. A confident wrong answer is worse than an
honest low-confidence one in an industrial setting.

**Rule 3 — The Knowledge Graph stores knowledge, not conclusions.** It holds
`Electric Arc Furnace —requires→ High Current`, `—supports→ Steel Melting`. It NEVER holds
"best operating strategy" — that is an economic decision, and belongs to the frozen engine.

**Rule 4 — Explainability is a test, not a feature.** `FacilityProfile.explain()` must trace
every inference back to the evidence + ontology rules that produced it
(`Batch Melting ← Equipment ← Signals ← Rated Power ← Rule #27`). The **Explainability Test**
asserts every element in a produced profile is traceable; an inference that cannot explain
itself does not understand the facility and fails CI.

The Composer consumes `FacilityProfile.resolve()` (the highest-confidence interpretation),
carrying the confidence forward. S3 changes no engine, API, or wire contract.

## 2B. Industrial Evidence Patterns (S4) — the three knowledge levels

Understanding must not jump from raw facts straight to concepts. Between them sits the way
industrial experts actually reason: **a bundle of evidence forms a pattern**. A 30 MVA
transformer alone proves nothing; a 30 MVA transformer **+** 33 kV primary **+** >20 MW
rated power **together** form the pattern that suggests an Electric Arc Furnace.

**Three levels of knowledge (the S4 knowledge base):**

```
  Level 1  FACTS      transformer_mva=30 · voltage_primary=33000 · rated_power_mw=27 · signal:soc
  Level 2  PATTERNS   EAF_HIGH_POWER · UTILITY_BATTERY · PV_INVERTER_CLUSTER
  Level 3  CONCEPTS   Electric Arc Furnace · Steel Melting · Peak Shaving · Cement Grinding
```

The understanding path becomes **Facts → Patterns → Concepts → FacilityProfile** — never
Facts → Concepts directly.

**The Knowledge Graph gains a first-class Evidence-Patterns layer:**

```
Industrial Knowledge Graph
├── Ontology          (Signal/Equipment/Capability/Process/Intent/Facility, from packs)
├── Evidence Patterns (weighted predicates over Facts → implied concepts)   ← NEW
├── Recognition Rules (signal→canonical aliases; facility-signature labels)
└── Capability Map    (equipment —exhibits→ capability —archetype→ engine)
```

An Evidence Pattern (`kind: pattern`, data only) declares predicates over Facts and, by how
completely they match, implies a **specific** or a **more general** concept:

```yaml
kind: pattern
id: eaf_high_power
predicates:
  - { fact: transformer_mva,  op: gt, value: 25 }
  - { fact: voltage_primary,  op: eq, value: 33000 }
  - { fact: rated_power_mw,   op: gt, value: 20 }
implies:                                   # most-specific first
  - { concept: electric_arc_furnace, concept_kind: equipment, min_match: 1.0, confidence: 0.82 }
  - { concept: high_power_furnace,   concept_kind: equipment, min_match: 0.6, confidence: 0.54,
      needs_more_evidence: true }
```

The matcher computes `match_ratio = matched / total`, then asserts the most-specific
`implies` whose `min_match ≤ match_ratio` (confidence scaled by the ratio); below every
threshold it asserts nothing (No-Guess). Full evidence ⇒ *Electric Arc Furnace 0.82*;
transformer + voltage but **no rated power** ⇒ *High Power Furnace 0.54, need more evidence*
— never EAF. Every assertion is an `Inference` carrying the matched facts as evidence.

**Pattern Stability Test (new gate):** for a pattern with a specific + a general implication,
removing one required fact must move the conclusion from the specific concept to the general
one (with lower confidence + `needs_more_evidence`), and must NOT keep asserting the specific
concept. This is the No-Guess rule made testable at the pattern level.

## 3. Migration roadmap

| Stage | Deliverable | Engine? | Golden | Status |
|-------|-------------|---------|--------|--------|
| **S1** | `app/knowledge/` + registry + byte-identical alias extraction | no | identical | ✅ deployed (3801073) |
| **S1′** | **Ontology reconciliation:** per-kind `PackSchema` (7 kinds); recast the shipped pack into a `capability: energy_storage` pack + a `recognition: legacy_signal_aliases` (tier signal) carrying the alias bundle verbatim; registry merges signal aliases. **Byte-identical** — identity SHAs unchanged | no | **identical** | **THIS TURN** |
| **S2** | `domain/canonical/` graph CIM (Facility⊃Process⊃Equipment, +Intent) + Composer + `to_wire()`; `intent` pack kind + default `arbitrage`; BESS graph (intent: arbitrage) → `to_wire()` identity on a golden fixture | no | identical | **THIS TURN** |
| **S3** | evidence-based `FacilityProfile` (Inference{value,confidence,source,evidence,rule}) + `.explain()`/`.resolve()`; `knowledge/graph.py` IKG (knowledge, not conclusions); `services/facility/` FUE (No-Guess). Explainability + No-Guess tests. `/audit/inspect` FacilityProfile is a later increment | no | unchanged | **THIS TURN (core)** |
| **S4** | **Industrial Knowledge Engineering:** the Evidence-Patterns layer (`kind: pattern` + Facts extractor + matcher; Facts→Patterns→Concepts) + Pattern Stability Test; then author equipment/capability/process/pattern/facility-recognition packs per industry (steel, cement, …) + baselines | no | S3 recognition evolves (pattern-based) | **THIS TURN (pattern engine + EAF/BESS demo)** |
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
