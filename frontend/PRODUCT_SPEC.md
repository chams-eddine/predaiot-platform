# PREDAIOT Frontend Product Specification — PREDAIOT-FE-2.0

**Status:** **RATIFIED — 2026-07-14** (execution authorization issued by the
platform architect). The governing contract in force; single source of
truth. Supersedes the FE-1.0 proposal. Changes only via GOV-AL amendments.
**Class:** Governing architectural contract for the entire PREDAIOT user
experience. The frontend equivalent of the certified EDA architecture. Every
screen, component, dashboard, animation, instrument, interaction, and pixel
must trace to this document. Deviations require a ratified amendment first.
**Authority chain:** PLATFORM_BLUEPRINT.md → **PART 0 (Product
Philosophy)** → Parts I–V of this document → `WORKSPACE_SPEC.md` (normative
annex of SPEC-WS) → implementation. Part 0 is the highest authority in the
frontend architecture; every other specification inherits from it, as
proven by the Traceability Matrix (end of document).
**Backend:** FROZEN. Every specification consumes existing production APIs
only. No spec may invent endpoints or alter contracts.
**Identity Law:** Constitutionalized in **SPEC-CA (Part 0)** and immutable:
PREDAIOT is an **Economic Decision Intelligence Platform** — it is NOT
SCADA, NOT EMS, NOT BI, NOT an IoT dashboard, NOT analytics, NOT
monitoring, NOT predictive maintenance, NOT optimization software, NOT a
digital twin. Every screen must reinforce this identity.

## Specification index

| Part | ID | Specification | Status |
|------|----|---------------|--------|
| 0 — Product Philosophy | SPEC-MS | Mission | RATIFIED |
| 0 | SPEC-VS | Vision | RATIFIED |
| 0 | SPEC-CA | Category | RATIFIED (immutable core) |
| 0 | SPEC-TR | Truth Model | RATIFIED |
| 0 | SPEC-QA | Executive Questions | RATIFIED |
| 0 | SPEC-DM | Decision Model | RATIFIED |
| 0 | SPEC-HM | Human Model | RATIFIED |
| 0 | SPEC-EV | Economic Value Model | RATIFIED |
| 0 | SPEC-TM | Trust Model | RATIFIED |
| 0 | SPEC-FM | Frontend Manifesto | RATIFIED |
| 0 | — | The PREDAIOT Experience | RATIFIED |
| I — Foundation | SPEC-PR | Product Principles | RATIFIED |
| I | SPEC-ID | PREDAIOT Visual Identity | RATIFIED |
| I | SPEC-DL | Executive Design Language | RATIFIED |
| I | SPEC-DS | Design System | RATIFIED |
| I | SPEC-WS | Workspace System (annex: WORKSPACE_SPEC.md) | RATIFIED |
| I | SPEC-IA | Information Architecture | RATIFIED |
| II — Executive Experience | SPEC-EX | Executive Experience | RATIFIED |
| II | SPEC-RB | Role-Based Experience | RATIFIED |
| II | SPEC-ST | Narrative Experience | RATIFIED |
| II | SPEC-AI | AI Interaction Language | RATIFIED |
| III — Visualization | SPEC-DV | Data Visualization | RATIFIED |
| III | SPEC-CH | Decision Instrument Library | RATIFIED |
| III | SPEC-MO | Motion Language | RATIFIED |
| III | SPEC-LX | Industrial Luxury Language | RATIFIED |
| IV — Product | SPEC-CO | Component Registry | RATIFIED |
| IV | SPEC-NV | Navigation | RATIFIED |
| IV | SPEC-DB | Dashboard Manifest | RATIFIED |
| IV | SPEC-IX | Interaction Language | RATIFIED |
| IV | SPEC-SX | Security UX | RATIFIED |
| IV | SPEC-AX | Accessibility | RATIFIED |
| IV | SPEC-RS | Responsive System | RATIFIED |
| IV | SPEC-PF | Performance | RATIFIED |
| V — Governance | GOV-CM | Compliance Matrix | RATIFIED |
| V | GOV-DR | Design Registry | RATIFIED |
| V | GOV-AL | Amendment Log | RATIFIED |
| V | GOV-AC | Acceptance Process | RATIFIED |
| V | GOV-RP | Ratification Procedure | RATIFIED |

Every operational specification (Parts I–IV) defines: **Purpose · Vision ·
Responsibilities · Boundaries · Inputs · Outputs · Rules · Acceptance
Criteria · Non-Goals · Future Extensions · Dependencies · Examples ·
Failure Cases · Governance Rules.**
Part 0 specifications are constitutional, not operational; they use the
constitutional contract form: **Purpose · Declaration · Rules ·
Inheritance · Acceptance Criteria · Governance Rules.** They define *why*;
Parts I–V define *what and how* under their authority.

---
---

# PART 0 — PRODUCT PHILOSOPHY

This part is the highest authority in the frontend architecture. It is not
a design document, not a UX document, not a marketing document. It defines
the philosophy of the entire product — why the interface exists. Every
specification in Parts I–V inherits from Part 0; the Traceability Matrix
at the end of this document proves the inheritance.

---

# SPEC-MS — Mission 1.0

**Purpose.** Fix, permanently, why PREDAIOT exists — not what it does, not
how it works.

**Declaration.**
Industrial infrastructure loses money invisibly. Every asset — a battery,
a plant, a grid — executes thousands of operational decisions, and the
industrial world measures those decisions in operational terms:
availability, output, uptime, alarms. Nobody measures whether the
decisions captured the value that was achievable. The gap between what an
asset earned and what it could have earned is real money — and today it is
unmeasured, unowned, and ungoverned. It appears in no report, no meeting,
no accountability chain.

**PREDAIOT exists to end invisible economic loss** — by making the
economic quality of operational decisions measurable, provable, and
governable. It exists because economic accountability is missing between
operations and finance: operations optimizes machines, finance audits
books, and no one audits decisions. PREDAIOT is that missing auditor,
running continuously, with evidence.

**Rules.**
1. Every surface must serve the mission: making economic leakage visible,
   recoverable, and provable. A feature serving any other mission —
   monitoring comfort, data exploration for its own sake, engagement — is
   rejected regardless of quality.
2. The mission is stated in money, and so is the product: money is the
   product's native language (inherited by SPEC-EV, SPEC-DL).

**Inheritance.** SPEC-PR's Existence Test derives from this mission; every
Part I–V spec must be justifiable as an instrument of it.

**Acceptance Criteria.** Any shipped screen can state, in one sentence, how
it advances the mission; screens that cannot are removed.

**Governance Rules.** The mission is immutable upon ratification. Rewording
requires a constitutional amendment with full cascade review — expected
never.

---

# SPEC-VS — Vision 1.0

**Purpose.** Describe the long-term future the architecture must be built
to reach.

**Declaration.**
**PREDAIOT becomes the operating system for economic decisions across
industrial infrastructure.** Every dispatch decision, on any asset, in any
market, is proposed, tracked, measured, and verified through governed
economic evidence — the way financial statements move through audit
opinions.

The horizons:
- **H1 — Certified economic audit** of a single asset (delivered: the EDA
  audit engine, certificates, evidence chain).
- **H2 — Live economic runtime**: continuous provisional economic state,
  reconciled into certified truth (delivered: RT pipeline + EDA-RECON;
  hardening).
- **H3 — Portfolio economic command**: fleets governed as one economic
  surface (Q8 surfaces, T4/T5 workspace zones).
- **H4 — The EDA Standard as industry norm**: PREDAIOT's methodology as the
  reference discipline for economic decision governance (EDA Standard v1.0
  in preparation).

**Rules.**
1. Architectural decisions must move toward the operating-system role:
   canonical objects, governed registries, versioned contracts,
   asset-agnostic generalization. One-off features that cannot generalize
   across assets and markets are rejected.
2. The frontend must scale along the horizons without re-architecture —
   this is why the Workspace System (SPEC-WS) tiers toward portfolio and
   wall scale.

**Inheritance.** SPEC-WS tier ladder (T4/T5 = H3 surfaces); SPEC-IA/QA
future questions (Q8, reserved Q10); registry-based governance throughout
Part V.

**Acceptance Criteria.** Every new architectural proposal states which
horizon it serves; none regresses an earlier horizon's guarantees.

**Governance Rules.** The vision statement is amendable only by
ratification; horizons may be appended, never deleted.

---

# SPEC-CA — Category 1.0

**Purpose.** Define PREDAIOT's category — immutably.

**Declaration.**
PREDAIOT's category is **Economic Decision Intelligence**.

PREDAIOT is **NOT**, and must never present as:

| NOT | Why PREDAIOT is not it |
|-----|------------------------|
| SCADA | SCADA controls equipment; PREDAIOT governs the economics of decisions |
| EMS | EMS optimizes setpoints; PREDAIOT audits and certifies economic outcomes |
| BI | BI aggregates data for exploration; PREDAIOT produces certified economic evidence for registered questions |
| IoT Dashboard | IoT renders telemetry; PREDAIOT renders money, decisions, and proof |
| Analytics Platform | Analytics explores; PREDAIOT answers a closed charter of executive questions |
| Monitoring Software | Monitoring watches state; PREDAIOT judges economic value |
| Predictive Maintenance | PdM predicts failure; PREDAIOT measures decision economics |
| Optimization Software | Optimizers prescribe control; PREDAIOT's MILP is a hindsight benchmark for attribution — never a controller |
| Digital Twin | Twins simulate physics; PREDAIOT certifies economics |

**Category drift tests** (any one failing = non-compliance):
- The primary object of every screen is money, a decision, or evidence —
  never a sensor value, a device, or a data table for its own sake.
- No surface invites open-ended data exploration as its purpose.
- No surface implies control authority over equipment.

**Rules.**
1. The category definition and the NOT-list are **immutable upon
   ratification** — they may be extended (new NOT entries appended), never
   weakened or removed.
2. Copy, navigation, and marketing surfaces inside the product use the
   category name and never a NOT-category's vocabulary as self-description.

**Inheritance.** SPEC-PR Identity Law (operationalization); SPEC-LX
anti-list (aesthetic enforcement); SPEC-IA taxonomy (question-driven, not
data-driven); SPEC-CH (instruments answer questions, they do not "chart
data").

**Acceptance Criteria.** Category drift tests pass on every screen at every
release; the blind-screenshot test (SPEC-ID) never reads as a NOT-category.

**Governance Rules.** This specification is the only one in the document
declared immutable-on-ratification in its core: no amendment may remove or
weaken the category definition or NOT-list; append-only extension permitted.

---

# SPEC-TR — Truth Model 1.0

**Purpose.** Define the five truths of PREDAIOT, their differences, and how
truth propagates from the EDA backend into the frontend.

**Declaration.**

| Truth | What it is | Where it lives (existing) |
|-------|-----------|----------------------------|
| **Operational truth** | What physically happened — recorded dispatch, prices, SOC, curtailment; raw and unjudged | Ingested data; canonical events (EDA-EVENT-1.0) |
| **Economic truth** | What that behavior was worth — gaps, EDV, attribution, judged by versioned methodology | The certified engine (EDA-AUDIT, EDA-ES-1.0); provisional live states |
| **Decision truth** | What was proposed, accepted, executed, deferred — intent and its lifecycle | EDA-DEC-1.0, EDA-DEC-LIFE-1.0 records |
| **Evidence truth** | Why any of the above can be believed — hashes, manifests, certificates, verdicts, reconciliations | audit_manifest, certificates, EDA-OUT/GOV/RECON chains |
| **Visual truth** | What the user sees — a faithful rendering of the four truths above, with provenance and uncertainty visible | The frontend (this document's subject) |

The differences: operational truth tells *what happened*; economic truth
*what it was worth*; decision truth *what was chosen*; evidence truth *why
to believe it*; visual truth *what you see* — and visual truth must equal
the sum of the other four, exactly.

**Propagation (the truth pipeline):**
Operational → (canonical events + data-quality gate) → Economic (one
engine; provisional when live, certified when audited) → Decision
(proposals and lifecycle) → Evidence (append-only chains, certification,
reconciliation) → **Visual** (the frontend renders; it never manufactures).

**Rules.**
1. The frontend consumes truth; it never creates, adjusts, extrapolates,
   or smooths it.
2. The provisional/certified distinction propagates unbroken from EDA-RECON
   semantics to every pixel that shows a live-derived figure.
3. A truth state absent upstream cannot appear downstream: no invented
   confidence, no fabricated trends, no synthesized comparisons.
4. INDETERMINATE and PROVISIONAL are truths, not gaps to be papered over.
5. Where truths conflict in presentation space, evidence truth wins
   placement (P7) and economic truth wins emphasis (P2).

**Inheritance.** SPEC-PR P2/P3/P7; SPEC-DV axis truth; SPEC-AI confidence
honesty; SPEC-SX provenance surfaces; SPEC-IX no-optimistic-economics.

**Acceptance Criteria.** Every rendered figure traces to its upstream truth
layer and state; provenance E2E checks pass; no downstream-only "truths"
exist in any release.

**Governance Rules.** The five-truth model and pipeline are amendable only
by ratification with full cascade review; new truth layers append.

---

# SPEC-QA — Executive Questions 1.0

**Purpose.** Define every executive question PREDAIOT is allowed to answer.
**If a question is not registered here, the UI cannot answer it.** This
registry is the exclusive charter; SPEC-IA (Part I) inherits it and owns
the mapping of questions to sections and zones.

**Declaration — the registered questions.**

**Q1 — How much are we losing?**
- Purpose: quantify the period's economic leakage so it becomes ownable.
- Required evidence: certified audit + manifest hash; provenance badge.
- Required APIs: `POST /api/v1/audit` (JSON), the file-upload audit
  endpoint; certified-state endpoints when reconciled from live.
- Required metrics: EDA-AUDIT (`total_gap_usd`), EDA-ES-1.0.
- Decision owner: CFO / asset owner.
- Output: leakage figure + period + currency + provenance state.
- Acceptance: figure equals the API field; basis and badge verified in E2E.

**Q2 — How much can we recover?**
- Purpose: separate winnable value from unreachable benchmark.
- Required evidence: gap attribution (Ch 8.2), audit manifest.
- Required APIs: audit response (`recoverable_execution_gap`,
  `gap_attribution`).
- Required metrics: EDA-AUDIT attribution; EDA-ES-1.0.
- Decision owner: CFO / Operations Manager.
- Output: recoverable figure + share of leakage + basis line.
- Acceptance: recoverable ≤ leakage; ceiling labeled non-achievable.

**Q3 — How healthy are our decisions?**
- Purpose: judge decision quality as a governed verdict, not a vibe.
- Required evidence: ECF capture fraction; risk band; DQI/AC when computed.
- Required APIs: audit response (`dq_score`, `risk_level`,
  `data_quality_index`, `audit_confidence`).
- Required metrics: EDA-DQI-1.0, EDA-AC-1.0 (INDETERMINATE honest).
- Decision owner: CEO / asset manager.
- Output: capture %, risk verdict, confidence grade where present.
- Acceptance: no fabricated confidence; ECF fallback lawful and labeled.

**Q4 — What should we do next?**
- Purpose: convert leakage into one governed, evidence-bearing action.
- Required evidence: full SPEC-AI Recommendation Block anatomy.
- Required APIs: audit response (`opportunities[]`, `root_causes[]`);
  decision endpoints (EDA-DEC) when decisions are issued.
- Required metrics: EDA-DEC-1.0; ACTION_LIBRARY versioning.
- Decision owner: Operations (governance_owner default: asset_manager).
- Output: primary recommendation + alternatives + value at stake +
  recorded-basis disclaimer.
- Acceptance: never a bare recommendation; experimental gated.

**Q5 — Why is value leaking?**
- Purpose: attribute leakage to recorded causes so action targets truth.
- Required evidence: root-cause decomposition; step ledger.
- Required APIs: audit response (`root_causes[]`, `gap_attribution`,
  decision ledger series).
- Required metrics: EDA-AUDIT decomposition.
- Decision owner: Engineer / Operations.
- Output: causes ranked by recorded loss with derivations.
- Acceptance: causes sum within the audited gap; no invented causes.

**Q6 — Can we prove it?**
- Purpose: make every figure auditable to evidence.
- Required evidence: manifest hash, certificate, governance verdicts,
  lifecycle records, outcomes, reconciliations.
- Required APIs: `GET /api/v1/certificate`; governance / lifecycle /
  outcome / reconciliation record endpoints.
- Required metrics: EDA-GOV-1.0, EDA-OUT-1.0, EDA-DEC-LIFE-1.0,
  EDA-RECON-1.0.
- Decision owner: Auditor / Administrator.
- Output: verifiable chain: input hash → audit → decision → outcome →
  verdict.
- Acceptance: every chain link renders a real, verifiable artifact.

**Q7 — What is happening right now?**
- Purpose: continuous provisional economic awareness.
- Required evidence: live provisional state, PROVISIONAL badge, event
  window manifest.
- Required APIs: `/ws/live`; live-state endpoints.
- Required metrics: EDA-EVENT-1.0; live DQ gate; EDA-RECON-1.0 for later
  certification.
- Decision owner: Operations.
- Output: live leakage/health, always marked provisional until reconciled.
- Acceptance: no live figure ever renders as certified.

**Q8 — How do assets compare?**
- Purpose: portfolio allocation of attention and capital.
- Required evidence: certified audit history per asset.
- Required APIs: `GET /api/v1/audits` (authenticated history).
- Required metrics: EDA-ES-1.0 across audits.
- Decision owner: CEO / portfolio owner.
- Output: comparative capture/risk/leakage across assets (T4+ surfaces).
- Acceptance: only assets with real audits appear; no synthetic peers.

**Q9 — What happens if we wait?**
- Purpose: give inaction a recorded price — honestly.
- Required evidence: the audited period's recorded figures, re-expressed
  as a period rate; mandatory basis disclosure.
- Required APIs: audit response (recorded values only).
- Required metrics: EDA-AUDIT recorded figures; no forecasting metric
  exists and none may be implied.
- Decision owner: CFO / Operations.
- Output: recorded rate framing ("recorded at X per 24h this period.
  Basis: recorded period only — no forward projection.").
- Acceptance: the word "forecast" and forward-looking verbs absent; basis
  line present verbatim-class.

**Q10 — (RESERVED) What did our decisions earn us?** Realized-value
aggregate from Outcome/Governance history. Activates by amendment when
certified outcome history accumulates.

**Rules.**
1. The UI may not answer unregistered questions — any surface answering an
   unregistered question is removed regardless of quality.
2. Registration requires all seven fields, with APIs and metrics that
   exist in the frozen backend.
3. One question may have many surfaces; every surface has exactly one
   primary question.

**Inheritance.** SPEC-IA (mapping to sections/zones); SPEC-DB manifests
(primary-question field); SPEC-CH (instruments bind to questions);
SPEC-EX (Q1–Q4 supremacy).

**Acceptance Criteria.** Registry ↔ surface audit at every release: no
orphan questions (registered but unanswerable), no rogue surfaces
(answering unregistered questions).

**Governance Rules.** Append-only; activation of reserved questions and
any new registration require ratified amendment with the seven fields
complete.

---

# SPEC-DM — Decision Model 1.0

**Purpose.** Define the lifecycle of a decision from the user's
perspective; every dashboard must serve one or more stages.

**Declaration — the seven stages.**

| Stage | The user… | The platform provides (existing) |
|-------|-----------|-----------------------------------|
| **Observe** | sees the current economic state | S01 command center; live telemetry (Q1, Q7) |
| **Understand** | learns why value moved | root causes, attribution, counterfactual (Q5) |
| **Trust** | inspects the proof | DQI/AC grades, hashes, certificates (Q3, Q6) |
| **Decide** | accepts a governed recommendation | SPEC-AI block; EDA-DEC issuance (Q4) |
| **Execute** | tracks the action | EDA-DEC-LIFE states: PROPOSED → ACCEPTED → IN_EXECUTION → EXECUTED (or DEFERRED / REJECTED) |
| **Verify** | measures what it earned | EDA-OUT outcomes; EDA-GOV verdicts; EDA-RECON certification |
| **Learn** | accumulates institutional memory | audit history; governance records (the future Knowledge Layer's diet) |

**Rules.**
1. Every dashboard declares in its manifest (SPEC-DB) which stages it
   serves; a dashboard serving zero stages cannot exist.
2. The full loop must remain reachable in the product at all times — no
   stage may become orphaned by a redesign.
3. Stage transitions render as evidence (chips, records), never as mere
   UI state.

**Inheritance.** SPEC-ST beats (beats 1–3 ≈ Observe/Understand + money;
beat 4 ≈ Decide; beat 5 ≈ Trust; beat 6 ≈ the cost of not moving to
Execute); SPEC-DB manifest schema; SPEC-NV (loop reachability).

**Acceptance Criteria.** Manifest stage declarations complete; loop
walkthrough (Observe → Learn) passes on production data at every release.

**Governance Rules.** The seven stages are amendable only by ratification;
stage semantics align with the frozen EDA lifecycle vocabulary.

---

# SPEC-HM — Human Model 1.0

**Purpose.** Define how executives think, so the interface optimizes
cognitive load — not information density.

**Declaration.**
Executives do not consume dashboards. **Executives consume answers.** They
arrive mid-thought, under time pressure, carrying accountability. The
interface's job is to complete their thought, not to furnish them with
data. Therefore:

- **Answer-first cognition:** conclusion before support, always (the
  pyramid principle, rendered).
- **Recognition over recall:** one constant grammar — a user who learned
  one instrument, badge, or block has learned them all; nothing requires
  remembering a previous screen (the Economic Context Strip carries state).
- **Pre-interpreted numbers:** every figure arrives with its verdict
  (grade, risk band, class) — the user never computes judgment.
- **Attention as scarce capital:** one primary emphasis per screen;
  everything else waits its turn.
- **Progressive disclosure:** detail exists on demand, never by default.
- **Density is a tool, not a virtue:** dense evidence tables are lawful
  when density *reduces* total effort; dense answers never are.

**Rules.**
1. The five-second answer law governs every question-bearing screen.
2. No screen requires cross-screen memory to be understood.
3. Jargon budget: EDA terms always accompany a plain-language answer.
4. Cognitive load reviews are part of acceptance (GOV-AC) — measured as
   time-to-answer, not opinions.

**Inheritance.** SPEC-DL hierarchies; SPEC-EX five-second criterion;
SPEC-MO restraint; SPEC-AX (access as cognitive equity); SPEC-RS reading
order.

**Acceptance Criteria.** Five-second tests pass; zero cross-screen memory
dependencies found in review; verdict-adjacency audit passes (no naked
numbers).

**Governance Rules.** Amendable only by ratification; the answer-first law
is manifesto-protected (FM-8, FM-10).

---

# SPEC-EV — Economic Value Model 1.0

**Purpose.** Define how value is represented. Every displayed value must
belong to exactly one class. **Nothing else may be presented as money.**

**Declaration — the six value classes.**

| Class | Meaning | Existing source |
|-------|---------|-----------------|
| **Money lost** | recorded leakage of the period | `total_gap_usd`, root-cause losses |
| **Money recoverable** | winnable with information available at decision time | `recoverable_execution_gap`, opportunity `period_gain` |
| **Money saved** | recorded improvement realized by an executed decision | EDA-OUT realized value vs baseline |
| **Money protected** | value actually captured by sound decisions | `edv_actual_total` (captured value) |
| **Money at risk** | provisional live exposure not yet reconciled | live economic state leakage (PROVISIONAL) |
| **Money verified** | realized value confirmed by governance verdict | EDA-GOV verified outcomes |

**Rules.**
1. Every money figure on every surface declares exactly one class —
   visually (semantic color + label) and in its manifest.
2. Benchmark values (theoretical ceiling, `edv_optimal_total`) are **not a
   value class**: they are context, always labeled as non-achievable
   benchmarks, always visually subordinate (SPEC-DL economic hierarchy).
3. A money display that fits no class is removed — the class system is the
   Existence Test for numbers.
4. Class semantics bind to color semantics (SPEC-DS): lost=loss,
   recoverable/saved/verified=recover family, at-risk=provisional amber
   context, protected=captured presentation.

**Inheritance.** SPEC-DL economic hierarchy; SPEC-DS semantic palette;
SPEC-CH instrument meanings; SPEC-DB manifest value-class declarations;
SPEC-AI economic-impact element.

**Acceptance Criteria.** Value-class audit per release: every money figure
classified, benchmark labeling verified, zero unclassifiable money.

**Governance Rules.** The six classes are amendable only by ratification;
class additions require an existing API source — classes without recorded
data cannot exist (P2).

---

# SPEC-TM — Trust Model 1.0

**Purpose.** Define how trust is built. **Every screen must increase
trust.**

**Declaration — the seven trust mechanisms (the trust ladder).**

| Mechanism | What it gives the user | Existing artifacts |
|-----------|------------------------|--------------------|
| **Transparency** | nothing is hidden: methodology, versions, basis | metric versions, Math Appendix, basis disclaimers |
| **Evidence** | claims bind to artifacts | `input_sha256`, manifests, canonical events |
| **Confidence** | uncertainty is quantified, honestly | EDA-DQI-1.0, EDA-AC-1.0, INDETERMINATE |
| **Certification** | an authority signed it | EDPC certificate, signing key status, registry number |
| **Governance** | verdicts exist above the engine | EDA-GOV records, hash-chained |
| **Verification** | reality was re-measured | EDA-OUT outcomes; EDA-RECON reconciliation |
| **Auditability** | anyone can re-derive it | append-only chains, ledger CSV export, re-derivable from input hash |

**Rules.**
1. Every screen carries at least one trust artifact appropriate to its
   question — trust is shown, never asserted.
2. Trust may never be spent: no dark patterns, no hidden states, no
   euphemism for failure; a trust-reducing pattern is a release blocker.
3. The ladder is cumulative: higher mechanisms never replace lower ones
   (a certificate does not excuse a missing hash).
4. Broken trust artifacts (failed verification, missing chain link) render
   as explicit warnings — never silently omitted.

**Inheritance.** SPEC-SX (rendering the artifacts); SPEC-ID evidence
styling; SPEC-AI governance status; SPEC-IX honest states; P3/P4/P7.

**Acceptance Criteria.** Trust-artifact inventory per screen complete;
trust-reduction review clean; broken-artifact rendering verified in E2E.

**Governance Rules.** The seven mechanisms are amendable only by
ratification; every new surface registers its trust artifacts in GOV-DR.

---

# SPEC-FM — Frontend Manifesto 1.0

**Purpose.** Ten immutable laws every implementation obeys.

**Declaration.**

1. **The interface never guesses.** No optimistic economics, no
   extrapolation, no synthesized data. *(SPEC-TR, SPEC-IX; P2)*
2. **The interface never exaggerates.** Axis truth, no annualization, no
   alarm aesthetics. *(SPEC-DV, SPEC-LX; P2)*
3. **The interface never hides uncertainty.** PROVISIONAL and
   INDETERMINATE are first-class states, styled and named. *(SPEC-TR,
   SPEC-ID; P3)*
4. **The interface never decorates information.** Every element passes the
   Existence Test; no cosmetic charts, widgets, or ornament. *(SPEC-PR,
   SPEC-LX; P10)*
5. **The interface always explains its recommendations.** The full
   Recommendation Block anatomy — reasoning, evidence, confidence,
   alternatives, assumptions, governance. *(SPEC-AI; P9)*
6. **The interface always shows evidence.** Every economic figure within
   reach of its proof. *(SPEC-SX, SPEC-TM; P7)*
7. **The interface always prioritizes money.** Money first on every
   screen; the canonical hierarchy never inverts. *(SPEC-DL; P1)*
8. **The interface always protects executive attention.** One primary
   emphasis; motion and color only as meaning; five-second answers.
   *(SPEC-HM, SPEC-MO; P10)*
9. **The interface always reflects certified economic truth — and says so
   when truth is still provisional.** The truth pipeline renders unbroken.
   *(SPEC-TR; P2)*
10. **The interface exists to improve decisions.** The final test of every
    feature: does it move a user through Observe → Learn better than
    before? *(SPEC-DM, SPEC-MS)*

**Rules.**
1. The laws bind every implementation, review, and amendment in Parts I–V.
2. Conflicts between a law and any downstream rule resolve in the law's
   favor; the conflict itself is logged in GOV-AL for reconciliation.

**Inheritance.** All of Parts I–V; each law names its enforcing specs
above; P1–P10 operationalize the laws (mapping in the Traceability
Matrix).

**Acceptance Criteria.** Every acceptance pack (GOV-AC) attests all ten
laws; a violated law is a release blocker with no severity negotiation.

**Governance Rules.** The ten laws are immutable upon ratification: none
may be removed or weakened; new laws may be appended by ratification.

---

# THE PREDAIOT EXPERIENCE

The emotional contract. When someone opens PREDAIOT, they should feel —
and the architecture that produces each feeling:

| The user feels | Produced by |
|----------------|-------------|
| *"I understand my business."* | Answer-first briefings (SPEC-HM, SPEC-ST); money-first hierarchy (SPEC-DL) |
| *"I trust these numbers."* | The truth pipeline (SPEC-TR); trust artifacts on every screen (SPEC-TM) |
| *"I know what to do."* | The governed Recommendation Block (SPEC-AI); one primary action (SPEC-IX) |
| *"I know why."* | Reasoning + recorded attribution (SPEC-ST beat 2, Q5) |
| *"I know how much it is worth."* | Value classes on every figure (SPEC-EV) |
| *"I know what happens if I wait."* | Q9's honest recorded-rate framing (SPEC-QA) |
| *"I know the recommendation is governed."* | Lifecycle and governance chips; the evidence chain (SPEC-TM, Q6) |
| *"I know this platform thinks economically — not technically."* | The Category Law (SPEC-CA); money as the primary object everywhere |

The composite feeling is **institutional custody**: the calm of a private
bank, the rigor of an audit firm, the immediacy of a trading floor —
applied to the user's own infrastructure. The user leaves every session
knowing more, trusting more, and owing fewer unanswered questions than
when they arrived. That — not engagement, not delight, not time-on-screen
— is the product's emotional KPI.

---
---

# PART I — FOUNDATION

---

# SPEC-PR — Product Principles 1.0

**Purpose.** Establish the ten governing principles, the Identity Law, and
the existence tests from which every Part I–V specification and every UI
decision derives. This is the operational constitution — it inherits its
authority from Part 0 (Product Philosophy) and translates the philosophy
into citable, reviewable principles.

**Vision.** A product where nothing is arbitrary: any pixel, at any time,
can state why it exists, which executive question it serves, and which
principle authorizes it.

**Responsibilities.**
- Define and number the principles (P1–P10) cited by all specs and reviews:

| ID | Principle | Meaning | Test |
|----|-----------|---------|------|
| **P1** | Executive Clarity | The screen answers an executive question before anything else | The question is answered in < 5 seconds |
| **P2** | Economic Truth | Every figure originates in the frozen audit engine; nothing fabricated, projected, or smoothed | Each figure traces to a named API field; basis always disclosed |
| **P3** | Decision Confidence | Uncertainty, grades, and evidence are visible and honest | Absent data renders as absent; INDETERMINATE is a legitimate state |
| **P4** | Institutional Trust | Quiet, consistent, premium — the interface behaves like a financial institution | No noise, no rainbow, no template look |
| **P5** | Operational Efficiency | Fast to load, fast to read, fast to act | SPEC-PF budgets met; primary action ≤ 2 interactions away |
| **P6** | Narrative Intelligence | Screens tell the economic story in briefing order, never as widget collections | The six narrative beats (SPEC-ST) are present and ordered |
| **P7** | Evidence First | Every claim sits within reach of its proof | Hash, badge, grade, or chain link adjacent to every economic figure |
| **P8** | Industrial Luxury | Expensive, calm, timeless — never flashy, gaming, cyberpunk, or consumer SaaS | SPEC-LX material rules hold |
| **P9** | AI Transparency | Machine recommendations expose reasoning, confidence, assumptions, and alternatives | No bare recommendation ever renders (SPEC-AI anatomy) |
| **P10** | Visual Calm | Stillness is the default; motion and color are meaningful events | Nothing moves or saturates without an economic reason |

- Enforce the **Existence Test**: every UI element must answer an executive
  question. If it does not answer a question, it must not exist.
- Enforce the **Five Purposes Test**: every visual element must declare at
  least one of — economic purpose, narrative purpose, decision purpose,
  evidence purpose, executive purpose. Reviews record which.
- Hold the **Identity Law** (header of this document) over all design work.

**Boundaries.** Defines *why*; never *how* (identity → SPEC-ID, hierarchy →
SPEC-DL, mechanics → Parts III–IV). Principles do not override the frozen
backend or PLATFORM_BLUEPRINT.md.

**Inputs.** The ratified mission; the EDA governance philosophy; the design
references below (philosophy only — never copied): Bloomberg Terminal
(density with authority), Palantir Foundry (evidence-linked analysis),
Stripe Dashboard (typographic restraint), Apple Vision Pro (material calm),
Tesla Energy (quiet telemetry), Formula 1 telemetry (glanceable precision),
TradingView (financial time literacy), Linear (disciplined minimalism),
Bridgewater reporting (narrative machine-briefings), McKinsey executive
reports (pyramid answers first), BlackRock Aladdin (portfolio risk gravity).
The result must be uniquely PREDAIOT.

**Outputs.** The principle registry (P1–P10); the two existence tests; the
citation vocabulary used in manifests, reviews, and the Compliance Matrix.

**Rules.**
1. Every spec section, dashboard manifest, and component registration cites
   ≥ 1 principle by ID.
2. Conflicts resolve by precedence: P2 Economic Truth > P7 Evidence First >
   P1 Executive Clarity > P3 Decision Confidence > all others. Truth is
   never sacrificed for clarity or beauty.
3. No decorative widgets. No meaningless KPIs. No cosmetic charts. An
   element failing the Existence Test is removed regardless of effort spent.
4. Reference products are studied for philosophy; visual copying of any
   reference is a compliance failure.

**Acceptance criteria.** The Compliance Matrix (GOV-CM) shows a principle
citation for every registered artifact; review minutes record Existence
Test outcomes; zero uncited elements in shipped screens.

**Non-Goals.** Marketing brand strategy; naming; pricing surfaces.

**Future Extensions.** Principle P11 candidate — "Portfolio Gravity" — when
multi-asset portfolios become the primary object.

**Dependencies.** PART 0 (Product Philosophy) — the principles
operationalize SPEC-MS/CA/TR/HM/TM/FM; the P1–P10 → Part 0 mapping is
fixed in the Traceability Matrix. All Part I–V specs depend on SPEC-PR.

**Examples.**
- A pulsing dot on a LIVE badge: passes (P10 — motion signals a real live
  stream; evidence purpose).
- A decorative gradient orb in a corner: fails the Existence Test — removed.
- A KPI card showing "uptime %": fails — answers no executive question in
  the registry; monitoring identity violation.

**Failure Cases.**
- An element justified only by "it looks premium" (P8 without a question) —
  rejected: luxury is a *manner*, not a *purpose*.
- A screen that answers its question but fabricates a trend to do so —
  P2 violation; worst-class failure, blocks release.
- Copying Bloomberg's amber-on-black terminal look — identity failure.

**Governance Rules.** Amendments to principles require explicit ratification
and cascade review of all dependent specs. The principle registry is
append-only; principles are never silently reworded.

---

# SPEC-ID — PREDAIOT Visual Identity 1.0

**Purpose.** Make PREDAIOT instantly recognizable: a person seeing any
screenshot — without the logo — knows it is PREDAIOT.

**Vision.** An identity so consistent it functions as a certificate: the
look itself signals "governed economic evidence", the way a banknote's
engraving signals authenticity.

**Responsibilities.** Define the identity dimensions:

- **Typography.** Two faces only. Inter — headings, UI, narrative. JetBrains
  Mono — every numeral that carries money, evidence, or identity (amounts,
  percentages, hashes, IDs, timestamps, grades). Weights: 400/500/600 for
  prose, 700/800 reserved for answers (the money, the verdict). No third
  typeface may ever enter the product.
- **Financial Typography.** Money is the largest text on any screen it
  appears on. en-US digit grouping; compact institutional notation
  (7.04K / 2.31M / 1.20B) for secondary mentions, full precision at the
  primary mention; currency codes (USD, OMR) in small caps beside the
  numeral, never symbols alone for non-USD; negative values carry the loss
  color, never parentheses.
- **Spacing DNA.** The 8pt scale is the product's meter. Generosity grows
  with importance: the more consequential the figure, the more silence
  around it. Density is allowed only inside evidence tables.
- **Visual Rhythm.** Zones alternate weight — a heavy answer zone is
  followed by a lighter context zone. Repeating card rows of equal visual
  weight (the "widget grid" look) are an identity violation.
- **Geometry.** Soft-rectangular: radii 10/14/18/24. No sharp corners, no
  full circles except gauges and status dots. Hairlines at 1px; the
  signature top-accent rule on panels is 2px.
- **Card Language.** A card states one fact: kicker (microcaps label) →
  answer (mono numeral) → basis (one quiet line). Never more than one
  primary fact per card.
- **Panel Language.** Panels are instruments, not boxes: layered surface
  (panel → panel-2 gradient), hairline border, 2px accent top-rule,
  soft inset light. Panels never nest more than two levels.
- **Executive Grid.** Asymmetric by intent (65/35, 50/50 rows per SPEC-WS)
  — the grid of a briefing document, not a widget dashboard.
- **Evidence Language.** Evidence is jewelry: small, precise, mono —
  truncated SHA-256 chips, grade letters, CERTIFIED/PROVISIONAL badges,
  chain links. Always adjacent to the figure it certifies (P7).
- **Iconography.** Minimal geometric line icons, 1.5px stroke, no filled
  emoji glyphs in product surfaces (⚡/🏆 style tags are retired). Icons
  never appear without a text label at first use.
- **Economic Color Philosophy.** Color is a semantic system, not a palette:
  ink canvas (#06090F family) = the institution; teal `accent` (#34E0C8) =
  PREDAIOT intelligence speaking; rose `loss` = money leaking; green
  `recover` = money recoverable/verified; amber `warn` = caution &
  provisional states; gold `seal` = certification. Saturated color occupies
  < 10% of any screen; the canvas does the talking.
- **Brand Signature.** The five marks that make a screenshot unmistakably
  PREDAIOT: (1) deep-ink canvas with faint teal ambient radial; (2) panels
  with the 2px teal top-rule; (3) glowing mono financial numerals;
  (4) microcaps kicker labels with wide tracking; (5) evidence chips with
  truncated hashes beside every major figure.
- **Dashboard Personality.** A senior risk officer: calm, precise, direct,
  slightly austere, never excited. Copy is declarative ("Execution gap:
  6,710.39 USD"), never exclamatory, never gamified.
- **Premium Materials.** Layered ink surfaces with subtle luminance steps;
  restrained glass (blur only on sticky chrome); light always falls from
  above (inset top highlight, soft below-shadow).
- **Shadow Language.** Two elevations only: resting (soft 30px ambient) and
  raised (60px ambient for overlays). Glow is reserved for money numerals
  and live signals — glow is meaning, not decoration.
- **Surface Language.** bg-0 canvas < panel < panel-2 < panel-3; each step
  a small luminance increment. No pure black, no pure white anywhere.
- **Empty States.** Honest and directive: what is absent, why, and the one
  action that fills it ("No audit loaded. Run a demo or upload dispatch
  data."). Never sample data, never illustration mascots.
- **Loading States.** Skeleton panels shaped like the incoming answer; a
  quiet progress phrase for engine work ("Optimizing against hindsight
  benchmark…"). Never full-screen spinners after first paint.
- **Success States.** Understated confirmation — the artifact itself
  (certificate, badge) is the celebration. No confetti, ever.
- **Failure States.** Institutional candor: what failed, its impact, the
  recovery path — in warn/loss semantics, without stack traces or blame.
- **Evidence Styling.** Hash chips mono at 10–11px, truncated to 10 chars +
  ellipsis, copy-full affordance; chain relations rendered as linked chips.
- **Confidence Styling.** Grades A–E always as letter + color + numeric
  percentage when available; INDETERMINATE renders as neutral slate, never
  as a fake grade (P3).

**Boundaries.** Identity defines the *look and voice*; token values live in
SPEC-DS; layout in SPEC-WS; hierarchy in SPEC-DL; material physics detail in
SPEC-LX.

**Inputs.** SPEC-PR principles (P4, P7, P8, P10); the existing token
foundation.

**Outputs.** The identity dimensions above; the Brand Signature checklist
used in the screenshot recognition test.

**Rules.**
1. The five Brand Signature marks appear on every data-bearing screen.
2. Two typefaces, the semantic palette, and the 8pt meter are inviolable.
3. Emoji, mascots, stock illustrations, and decorative imagery are banned
   from product surfaces.
4. Money never shares its visual weight class with non-money content on the
   same screen.

**Acceptance criteria.** Blind screenshot test: reviewers identify PREDAIOT
without the logo from any section at any tier. Signature checklist passes on
every shipped screen.

**Non-Goals.** Marketing website identity; print/PDF identity (exists
separately); logo design.

**Future Extensions.** Light-theme identity (same signature in daylight);
customer co-branding rules that preserve the signature.

**Dependencies.** SPEC-PR; consumed by SPEC-DS, SPEC-DL, SPEC-LX, SPEC-CH.

**Examples.**
- The Executive Command Center hero: ink canvas, teal kicker
  "ECONOMIC DECISION AUDIT", glowing rose 7,070.54 USD, CERTIFIED chip with
  hash — all five signature marks present.
- A governance record row: mono verdict + hash chip + gold seal accent —
  evidence-as-jewelry.

**Failure Cases.**
- A section that renders blue default-styled charts on white tooltips —
  identity break (and SPEC-DV violation).
- A "🎉 Audit complete!" toast — personality violation (risk officers do
  not celebrate).
- Third typeface introduced by a library default — identity regression;
  blocked at review.

**Governance Rules.** Identity dimensions change only by amendment; the
Brand Signature list is append-only; any new visual pattern must be
registered in the Design Registry (GOV-DR) before use.

---

# SPEC-DL — Executive Design Language 1.0

**Purpose.** Define HOW executives consume information: the interface is
built around executive questions, never around widgets.

**Vision.** Every screen reads like the first page of a McKinsey answer —
conclusion first, support beneath — rendered as living software.

**Responsibilities.** Define the five hierarchies and the Money-First Law.

- **The Canonical Hierarchy (inviolable):**

  **Money → Risk → Opportunity → Decision → Evidence → Details.**

  Never reversed, never reordered, on any screen, at any tier.

- **Executive hierarchy** — what order questions are answered: the screen's
  primary question (per SPEC-IA registry) first, then its supporting
  questions in canonical order.
- **Visual hierarchy** — what the eye meets: largest/brightest element =
  the money answer; second = risk state; chrome is near-invisible. Squint
  test: only money and risk survive.
- **Attention hierarchy** — what may interrupt: live economic change >
  provisional→certified transitions > user-requested results > everything
  else. Nothing below the fold may animate for attention (P10).
- **Decision hierarchy** — what is actionable: exactly one recommended
  action holds primary emphasis per screen (from `opportunities[]` ranked
  by recorded `period_gain`); alternatives are visible but subordinate
  (SPEC-AI).
- **Economic hierarchy** — what money matters most: leakage (what is lost)
  > recoverable (what is winnable) > captured (what is safe) > ceiling
  (theoretical bound, always labeled as unreachable benchmark).

**Boundaries.** Order and emphasis only; identity (SPEC-ID), zones
(SPEC-WS), narrative voice (SPEC-ST), instruments (SPEC-CH) are elsewhere.

**Inputs.** SPEC-IA question registry; audit-response money fields.

**Outputs.** The hierarchy laws; per-screen hierarchy declarations inside
Dashboard Manifests (SPEC-DB).

**Rules.**
1. **Money-First Law:** every screen begins with money. Always. Sections
   whose primary question is non-monetary (Math Appendix, Audit History,
   administrative surfaces) open with the persistent Economic Context Strip
   — a condensed Z1/Z2 (asset, leakage, recoverable, health) — so money
   still leads.
2. Details (tables, ledgers, formulas) may never render above the money
   answer they support.
3. Evidence sits between Decision and Details: proof before mechanics.
4. At most one element per screen may claim primary attention; ties are
   resolved by the economic hierarchy.
5. Ceiling/benchmark values are always visually subordinate to actionable
   values and always labeled non-achievable (P2).

**Acceptance criteria.** For every shipped screen, a reviewer can draw the
six hierarchy bands top-to-bottom and finds no inversion; the Economic
Context Strip is present on all non-monetary sections; squint test passes.

**Non-Goals.** Copywriting style (SPEC-ST); component internals.

**Future Extensions.** Attention budgets per tier (T5 walls may host two
primary attention elements across regions — requires amendment).

**Dependencies.** SPEC-PR (P1, P4 P6-analog: P1/P2/P6); SPEC-IA; consumed by
SPEC-EX, SPEC-DB, SPEC-ST.

**Examples.**
- S01: Leakage (money) → Severe risk chip (risk) → Recoverable + top action
  (opportunity/decision) → CERTIFIED hash chip (evidence) → ledger below
  (details). Compliant.
- Math Appendix: Economic Context Strip on top, formulas beneath. Compliant.

**Failure Cases.**
- A screen opening with a data-quality donut above the money row —
  hierarchy inversion; rejected.
- A "Steps audited: 288" stat rendered at money weight — economic
  hierarchy violation (a detail dressed as an answer).

**Governance Rules.** The Canonical Hierarchy is amendable only by
ratification with cascade review of every Dashboard Manifest.

---

# SPEC-DS — Design System 1.0

**Purpose.** One token system carrying the identity: color, type, spacing,
radii, elevation, and motion tokens with economic semantics baked in.

**Vision.** The single material source from which every surface is built —
change a token, and the whole institution changes suit.

**Responsibilities.**
- Own the token families: surfaces (bg-0…panel-3, borders, hairlines), text
  (3 levels + inverse), accent family, economic semantics (loss/recover/
  warn/info + soft variants), grade scale A–E, decision types, trust
  (verified/provisional/seal), typography (two faces), 8pt spacing scale,
  radii, two elevations + meaning-glows, motion durations/easings.
- Own the semantic resolvers (grade, decision, severity, risk → color) and
  institutional formatters (money, percent) as the only formatting path.
- Maintain the dark theme as primary and the light scaffold with identical
  semantic names.
- Govern the legacy bridge (the App-level `DS` object mirroring token
  values) until Component Registry migration retires it.

**Boundaries.** Values and semantics only — identity rationale is SPEC-ID;
usage hierarchy is SPEC-DL; layout tokens belong to SPEC-WS (`ws-*`).

**Inputs.** SPEC-ID identity dimensions; SPEC-AX contrast floors.

**Outputs.** The token registry (registered in GOV-DR); resolvers;
formatters; theme scaffolds.

**Rules.**
1. No hardcoded color, font, spacing, radius, duration, or shadow outside
   token definitions. The documented bridge is the sole sanctioned
   exception until retirement.
2. Semantic-first: tokens are named for meaning (loss, recover, seal),
   never for hue (red, green, gold).
3. Money and evidence formatting flows only through the registered
   formatters — no ad-hoc `toLocaleString`/`toFixed` in screens.
4. New tokens enter by Design Registry registration citing an identity
   dimension.
5. Alpha-composited emphasis uses the defined soft variants, not arbitrary
   opacities.

**Acceptance criteria.** Static audit: zero unregistered literals outside
token files and the documented bridge; all colors pass SPEC-AX contrast in
their sanctioned contexts; the resolver/formatter functions are the only
call sites for semantic color/money text.

**Non-Goals.** Page layout; component behavior; chart internals;
white-label theming (future).

**Future Extensions.** Light theme completion; density variants; per-tenant
accent within identity constraints.

**Dependencies.** SPEC-ID, SPEC-AX; consumed by every implementing spec.

**Examples.**
- A new "DEFERRED lifecycle" chip needs a color → registered as semantic
  token `lifecycle-deferred` citing Evidence Language — not a hex in a
  component.
- Risk banding on the Decision Health instrument resolves via the risk
  resolver; the instrument never picks colors.

**Failure Cases.**
- A quick-fix `#FF0000` in a section file — blocked by the static audit.
- A formatter bypass producing "7 038,75" locale bleed — the historical
  defect class this spec exists to prevent.

**Governance Rules.** Token registry is append-only; value changes are
amendments with a visual-regression evidence pack; token deletion requires
proof of zero references.

---

# SPEC-WS — Workspace System 1.0

**Purpose.** One workspace architecture for every screen: shell, sidebar,
header, executive workspace, information zones, density tiers, and
ultra-wide/4K/video-wall behavior.

**Vision.** The workspace behaves like trading-floor real estate: more
canvas means more coexisting intelligence, never inflated rectangles.

**Responsibilities.** The full normative contract lives in
**`WORKSPACE_SPEC.md` (WS-1.0)** — density tiers T1–T5, sidebar geometry
(clamp 248px–400px), zone catalog Z1–Z10 with data bindings, the zone
visibility matrix ("space reveals intelligence"), the macro/zone/card grid
system, whitespace scale, and scroll policy. This chapter binds the annex
into FE-2.0 governance.

**Boundaries.** Allocates space; never chooses content (SPEC-IA/DL), visual
identity (SPEC-ID), or instrument design (SPEC-CH).

**Inputs.** Viewport tier signal; ratified zone catalog; `ws-*` layout
tokens.

**Outputs.** Workspace primitives contract (Workspace / Region / Zone and
the tier hook); the tier signal every other spec consumes.

**Rules.** (Annex is authoritative; the laws restated:)
1. No artificial max-width container; no centered content column. The
   interim 1720px executive cap is formally superseded and must be removed
   in Phase 1 migration.
2. Readable-width caps bind content (prose ≤ 72ch, cards ≤ 560px), never
   the workspace.
3. Wider tiers add zones per the visibility matrix; horizontal scroll never
   exists; T5 targets zero vertical scroll.
4. Whitespace grows between zones by tier — silence is structural
   (SPEC-LX), not residual.

**Acceptance criteria.** Workspace share ≥ 80% of viewport at 1440–3440
(sidebar expanded); zone matrix renders per tier; measured symmetric zone
gaps match the tier scale; no horizontal scroll 390→5120px.

**Non-Goals.** Mobile-first patterns; zone content; navigation taxonomy.

**Future Extensions.** User-arranged zone layouts with persistence;
multi-monitor workspace splitting.

**Dependencies.** SPEC-PR (P1, P5, P10); SPEC-IA zone-questions; consumed by
SPEC-EX, SPEC-DB, SPEC-RS, SPEC-CH.

**Examples.**
- 1920px (T3): AI Reasoning (65%) and Evidence Timeline (35%) join the
  canonical flow — more intelligence, same rectangles.
- 2560px (T4): Intelligence Rail carries decision stream + live telemetry +
  evidence chain beside the main briefing.

**Failure Cases.**
- A future screen shipping its own `max-width: 1200px` wrapper — instant
  non-compliance (the FE-1.0 lesson codified).
- KPI cards stretching to 748px at 2560 — the "larger rectangles" failure
  the tier matrix exists to prevent.

**Governance Rules.** Zone catalog and tier boundaries change only by
amendment to the annex, ratified with this document's procedure; every new
zone must name its question (SPEC-IA) and data binding (frozen API).

---

# SPEC-IA — Information Architecture 1.0

**Purpose.** Define the sequence of executive questions the product answers
and map every screen, section, and zone to exactly one primary question.

**Vision.** The product is a question-answering hierarchy so strict that
navigation is merely choosing which question to ask next.

**Responsibilities.**
- Map the **Question Registry** to surfaces. (Registry *authority* resides
  in SPEC-QA, Part 0 — the exclusive charter with the full seven-field
  entries. SPEC-IA inherits the registered questions and owns their mapping
  to sections and zones. The summary below restates the registry for
  mapping purposes; SPEC-QA is authoritative on any divergence):

| # | Question | Primary surface | Data (existing API) |
|---|----------|-----------------|----------------------|
| Q1 | How much are we losing? | Z2 Financial Leakage | `total_gap_usd` |
| Q2 | How much can we recover? | Z2 Recoverable Value | `recoverable_execution_gap` / `gap_attribution.execution_gap` |
| Q3 | How healthy are our decisions? | Z2 Decision Health | `dq_score` (ECF) + `risk_level` (+ `audit_confidence` when present) |
| Q4 | What should we do next? | Z3b Recommendation (SPEC-AI block) | `opportunities[]`, `root_causes[]` |
| Q5 | Why is value leaking? | Root Cause / analytical instruments | `root_causes[]`, ledger series, `gap_attribution` |
| Q6 | Can we prove it? | Evidence & Governance surfaces | `audit_manifest`, certificate, governance/lifecycle/outcome records |
| Q7 | What is happening right now? | Live telemetry (PROVISIONAL) | `/ws/live`, live state |
| Q8 | How do assets compare? | Portfolio surfaces (T4+) | `/api/v1/audits` history |
| Q9 | What happens if we wait? | Narrative inaction framing (SPEC-ST) | recorded per-period figures re-expressed as period rate — basis always disclosed, never a forecast |

- Own the **Section Taxonomy** (groups render via SPEC-NV): **COMMAND**
  (Executive Summary) · **ANALYSIS** (Value Flow, Audit Trail, Root Cause,
  Counterfactual, EDA Metrics, Leakage, Heat Map) · **ACTION** (Economic
  Action Plan, Intelligence Report) · **EVIDENCE & GOVERNANCE** (Governance,
  Certificate, Audit History) · **OPERATIONS** (Live Monitor, Real-Time) ·
  **REFERENCE** (Math Appendix).
- Bind every zone (Z1–Z10) and every section to one primary question.

**Boundaries.** Decides *which questions where*; rendering order is
SPEC-DL; navigation chrome is SPEC-NV; narrative voice is SPEC-ST.

**Inputs.** The frozen API surface; the executive brief; SPEC-PR Existence
Test.

**Outputs.** Question Registry; Section Taxonomy; the question declarations
required in every Dashboard Manifest.

**Rules.**
1. Every screen declares exactly one primary question; its answer renders
   first per SPEC-DL.
2. Q1–Q4 are never displaced from the first screen.
3. A screen or element answering no registered question may not exist
   without a ratified registry amendment (Existence Test, operationalized).
4. Q9 answers must be expressed strictly as recorded historical rates with
   the basis disclaimer — the word "forecast" is banned from Q9 surfaces
   (P2).

**Acceptance criteria.** Reviewer names each section's question unaided;
manifest question fields populated for all dashboards; Q1–Q4 answered on
S01 without scrolling at T2+.

**Non-Goals.** Copy tone (SPEC-ST); URL routing (SPEC-NV future).

**Future Extensions.** Q10 "What did our decisions earn us?" — realized
Outcome/Governance ROI aggregate as portfolio history accumulates.

**Dependencies.** SPEC-PR; consumed by SPEC-DL, SPEC-EX, SPEC-DB, SPEC-CH,
SPEC-NV.

**Examples.**
- Decision Heat Map → Q5 (why/when decisions degrade) — ANALYSIS group.
- EDPC Certificate → Q6 — EVIDENCE & GOVERNANCE group.

**Failure Cases.**
- A proposed "system resources" panel — no registered question; identity
  violation (monitoring); rejected twice over.
- Two sections claiming the same primary question with identical surfaces —
  consolidation required before ship.

**Governance Rules.** Question registration is governed by SPEC-QA
(Part 0); the section taxonomy and question-to-surface mappings here amend
only by ratification; data bindings must cite frozen API fields verifiable
at review.

---
---

# PART II — EXECUTIVE EXPERIENCE

---

# SPEC-EX — Executive Experience 1.0

**Purpose.** Contract for the first screen: an Executive Command Center that
answers Q1–Q4 in under five seconds and makes "this software manages
millions" felt without a word.

**Vision.** The chairman's opening page of a board briefing, alive: money,
risk, the one action that matters, and the proof — before a single scroll.

**Responsibilities.**
- Compose zones per the WS matrix: Z1 Command Header (identity, period,
  risk, evidence badge), Z2 Primary KPI row (Q1/Q2/Q3), Z3 Decision +
  Recommendation (Q4, rendered as the SPEC-AI block), Z4 Financial Timeline
  instrument; Z5/Z6 join at T3+, the Intelligence Rail at T4+.
- Enforce SPEC-DL hierarchy and SPEC-ST narrative beats on this screen
  before any other.
- Carry the dataSource truth: demo / upload / live provenance visible; live
  states PROVISIONAL until reconciled (EDA-RECON semantics).

**Boundaries.** Consumes zones and instruments; defines none. Role emphasis
variants belong to SPEC-RB; block anatomy to SPEC-AI.

**Inputs.** One audit response object (historical or live-provisional);
dataSource signal; tier signal.

**Outputs.** The reference Dashboard Manifest (first entry in GOV-DR's
manifest registry) against which all other dashboards are measured.

**Rules.**
1. Q1–Q4 visible without scroll at T2 (1440×900 reference).
2. Money numerals are the largest elements on the screen (SPEC-DL / P4).
3. Confidence renders only from API-provided values; the ECF-based Decision
   Health presentation is the permanent no-fabrication fallback (P2/P3).
4. Every value-at-stake statement carries its recorded-basis disclaimer.
5. The evidence badge state must provably match data provenance.

**Acceptance criteria.** Five-second test with an uninitiated executive
passes; no-scroll at 1440×900; every figure traces to a named field; badge
state verified against source in E2E; manifest evidence pack archived.

**Non-Goals.** Onboarding, configuration, marketing surfaces.

**Future Extensions.** Portfolio-mode command center when Q8 surfaces
mature; multi-period certified comparisons.

**Dependencies.** SPEC-DL, SPEC-IA, SPEC-WS, SPEC-AI, SPEC-ST, SPEC-CH;
principles P1, P2, P3, P7.

**Examples.**
- Compliant: leakage 7,070.54 USD (largest), Severe risk chip beside
  identity, recommendation block with reasoning + 7.8K USD at stake +
  basis line, CERTIFIED chip with hash.
- Compliant T3 addition: AI Reasoning (65%) narrating the execution gap,
  Evidence Timeline (35%) listing manifest → certificate → governance.

**Failure Cases.**
- A DQ donut promoted above money — SPEC-DL inversion; blocked.
- "Recommended Action" as bare text — SPEC-AI violation; blocked.
- Demo data rendering a CERTIFIED badge while live streaming shows the same
  — provenance conflation; worst-class P2 failure.

**Governance Rules.** Changes to S01 composition require manifest amendment
review before implementation; the five-second test is re-run and archived
at every S01 change.

---

# SPEC-RB — Role-Based Experience 1.0

**Purpose.** Adapt emphasis — never truth — to executive archetypes: CFO,
CEO, Operations Manager, Engineer, Administrator.

**Vision.** One instrument, five grips: each leader picks it up and finds
their question already on top.

**Responsibilities.**
- Own the archetype → emphasis matrix:

| Archetype | Leads with | Elevated surfaces | De-emphasized |
|-----------|-----------|-------------------|----------------|
| CFO | Q1/Q2 money | Z2, Value Flow, Leakage, Certificate | Live telemetry |
| CEO | Q3/Q8 health & portfolio | Z2, Portfolio, Governance verdicts | Engineering depth |
| Operations | Q4/Q7 act now | Recommendation block, Live Monitor, Decision Stream | Math Appendix |
| Engineer | Q5/Q6 why & proof | Root Cause, Counterfactual, EDA Metrics, Appendix | — |
| Administrator | System stewardship | Audit History, sessions, access surfaces | — |

- Bind archetype defaults to the existing authenticated role (owner/admin/
  asset_manager) as a hint only; explicit selection persists client-side.

**Boundaries.** Presentation lens only. RBAC enforcement remains entirely
backend (frozen). Archetypes never gate data the role could otherwise see,
and never grant access.

**Inputs.** Account role (existing API); user archetype selection; SPEC-IA
question weights.

**Outputs.** The `archetype` signal consumed by SPEC-DB compositions and
SPEC-NV ordering.

**Rules.**
1. No archetype hides evidence, alters figures, or reorders the Canonical
   Hierarchy — emphasis and section ordering only (P2, SPEC-DL).
2. Switching archetypes is one reversible interaction; the active lens is
   always visible.
3. Default without selection: CFO lens — the platform's moat is economic
   truth, so money-first is the native grip.
4. Q1–Q4 remain on the first screen for every archetype.

**Acceptance criteria.** Same audit under two archetypes shows identical
figures and evidence with different emphasis; lens persists across reload;
zero API divergence between archetypes.

**Non-Goals.** New permission models; per-role feature gating; per-user
custom layouts (future).

**Future Extensions.** Org-default archetypes; saved custom lenses;
briefing export per archetype.

**Dependencies.** SPEC-IA, SPEC-DL, SPEC-DB, SPEC-NV; principles P1, P5.

**Examples.**
- Engineer lens: ANALYSIS group promoted in navigation; S01 unchanged in
  truth, Counterfactual elevated to second position.
- CFO lens: Certificate surfaced in the Evidence Timeline by default.

**Failure Cases.**
- An archetype hiding the PROVISIONAL badge to "reduce noise" — P2/P7
  violation; rejected.
- Archetype selection persisting into another organization's session —
  scoping defect; blocked at review.

**Governance Rules.** The emphasis matrix is amendable; adding an archetype
requires question-weight justification from the SPEC-IA registry.

---

# SPEC-ST — Narrative Experience 1.0

**Purpose.** Dashboards tell the economic story in briefing order — never a
collection of widgets.

**Vision.** Reading a PREDAIOT screen feels like reading a one-page
executive briefing written by a careful analyst who respects your time.

**Responsibilities.**
- Own the **Six Narrative Beats** every dashboard answers, in order:
  1. **What happened?** — the period's economic outcome, stated plainly.
  2. **Why?** — the attributed causes (recorded attribution only).
  3. **How much money?** — quantified in the period's own figures.
  4. **What should I do?** — the SPEC-AI recommendation block.
  5. **What evidence supports this?** — manifest, certificate, chain.
  6. **What happens if I wait?** — Q9: the recorded loss re-expressed as a
     period rate with mandatory basis disclosure ("This period recorded
     6,710.39 USD recoverable execution gap over 24h. Basis: recorded
     period only — no forward projection.").
- Own the briefing voice: declarative sentences, active verbs, figures
  in-line, one thought per line; headline-grade statements above, mechanics
  below.
- Own narrative structure inside zones: each zone opens with its beat's
  conclusion, then its support (mini pyramid principle).

**Boundaries.** Voice and story order; visual hierarchy is SPEC-DL; the
recommendation anatomy is SPEC-AI; instruments visualize beats (SPEC-CH).

**Inputs.** Audit narrative fields (`root_causes[].description`,
opportunity derivations, Intelligence Report text); SPEC-IA questions.

**Outputs.** The beat structure required in every Dashboard Manifest; copy
rules for all product text.

**Rules.**
1. Every dashboard maps its zones to the six beats in its manifest; beats
   never render out of order.
2. Copy is institution-grade: no exclamation marks, no hype adjectives
   ("massive", "huge"), no anthropomorphic chat ("I found…" — the platform
   states, it does not chat).
3. Beat 6 is always historically-based rate framing; forward-looking verbs
   ("will lose", "is projected") are banned (P2).
4. Numbers inside narrative use the registered formatters and carry units
   and period labels.
5. A dashboard that cannot fill a beat states so honestly ("No governance
   verdict recorded for this audit yet") — beats are never faked.

**Acceptance criteria.** Manifest beat-mapping present for every dashboard;
copy review passes the voice rules; beat-order walkthrough finds no
inversion; Q9 surfaces carry the basis disclaimer verbatim-class wording.

**Non-Goals.** Localization (future); marketing tone; chatbot UX.

**Future Extensions.** Auto-generated period-over-period narrative when
certified history accumulates; Arabic/RTL briefing variant.

**Dependencies.** SPEC-IA (Q9), SPEC-DL, SPEC-AI; principles P2, P6.

**Examples.**
- S01 mapping: Beat1→Z1/Z2, Beat2→root-cause strip, Beat3→Z2 figures,
  Beat4→Z3 recommendation block, Beat5→Evidence Timeline, Beat6→inaction
  rate line under the recommendation.
- Compliant Beat 1 line: "Ibri 2 leaked 7,070.54 USD of achievable value in
  24 hours — 3.1% of the optimum was captured."

**Failure Cases.**
- A dashboard of eight equal tiles with no story spine — the "monitoring
  grid" anti-pattern this spec exists to kill.
- "You're losing money fast! ⚠️" — voice violation on three counts.
- Beat 6 phrased as "You will lose 200 USD/day" — P2 violation; must be
  "The recorded rate this period was 200 USD/day. Basis: recorded period
  only."

**Governance Rules.** The six beats are amendable only by ratification;
voice rules are enforced in copy review; beat mappings live in manifests
and are audited in GOV-AC.

---

# SPEC-AI — AI Interaction Language 1.0

**Purpose.** Give PREDAIOT's intelligence its own governed language:
recommendations are never bare text — they are evidence-bearing decision
artifacts.

**Vision.** Executives trust the machine because the machine shows its
work: reasoning, confidence, alternatives, and audit trail — every time,
in the same anatomy.

**Responsibilities.**
- Own the **PREDAIOT Recommendation Block** — the only sanctioned way any
  machine recommendation renders. Required anatomy, all fields from
  existing API data:

| Element | Content | Source (existing) |
|---------|---------|--------------------|
| Designation | "PREDAIOT Recommendation" + decision type chip | `opportunities[]` / decision `decision_type` (CORRECTIVE / OPTIMIZATION / RECOVERY / MONITORING) |
| Reasoning | Why this action, from recorded attribution | opportunity `description` / `derivation`, `root_causes[]` |
| Evidence | The audit basis | `audit_id`, `audit_manifest.input_sha256`, EDA-ES version |
| Confidence | Grade + % where provided; INDETERMINATE honestly | `audit_confidence`, `data_quality_index` |
| Economic Impact | Recorded-period value at stake + basis disclaimer | `period_gain` / `expected_value_impact` (recorded-period semantics) |
| Alternative Decisions | Next-ranked actions, subordinate emphasis | remaining `opportunities[]` ranked by recorded gain |
| Assumptions | Method + flags | `derivation`, `experimental` flag, methodology version |
| Governance Status | Where this stands in the loop | Decision → DEC-LIFE state → Outcome → Governance verdict (existing endpoints) |
| Evidence Chain | Linked chips | decision id → audit id → hashes → governance record |

- Own the AI voice: declarative, sourced, unhurried; the platform states
  findings — it never chats, never emotes, never markets itself.
- Own uncertainty language: INDETERMINATE, PROVISIONAL, and absent data are
  first-class honest states with defined styling (SPEC-ID Confidence
  Styling).

**Boundaries.** Presentation of machine output only; the intelligence
itself is the frozen engine. No new inference, no client-side "AI" logic,
no re-ranking beyond recorded figures.

**Inputs.** `opportunities[]`, `root_causes[]`, decisions + lifecycle +
outcomes + governance records, confidence objects, Intelligence Report
text.

**Outputs.** The Recommendation Block contract; the experimental-content
rule; the AI copy rules used across ACTION surfaces.

**Rules.**
1. **A bare "Recommended Action" may never render.** Minimum lawful render:
   Designation + Reasoning + Evidence + Confidence + Economic Impact;
   Alternatives/Assumptions/Governance/Chain follow at T3+ per zone space.
2. Experimental opportunities always carry their EXPERIMENTAL flag and are
   never the primary recommendation (existing product rule, now law).
3. Alternatives are visible wherever a primary recommendation renders —
   a lone option is presented as a ranked choice of one, stated as such.
4. Confidence is never invented: absent → the block renders its honest
   fallback (ECF-based health context) and says why.
5. Economic impact always carries the recorded-basis disclaimer; annualized
   or projected framings are banned (P2).
6. Governance status reflects the actual EDA loop state; "not yet governed"
   is a legitimate display state.

**Acceptance criteria.** Anatomy audit: every recommendation surface carries
the minimum lawful elements traceable to fields; no bare-text
recommendations grep-detectable in copy; experimental gating verified in
E2E; alternatives present wherever primaries render.

**Non-Goals.** Chat interfaces; generative free-text on-screen; client-side
model calls; prompt UIs.

**Future Extensions.** Recommendation diffing across certified periods;
governance-verdict-aware ranking (still recorded-data-only).

**Dependencies.** SPEC-ST (beat 4), SPEC-ID (confidence styling), SPEC-IA
(Q4); principles P2, P3, P7, P9.

**Examples.**
- Compliant block: "PREDAIOT Recommendation · OPTIMIZATION — Dynamic
  dispatch trigger. Reasoning: static thresholds held charge through the
  19:40 price window (root cause: market-response gap). Evidence: audit
  EDA-…5c1f · sha256 9f4be6f6a1…. Confidence: INDETERMINATE (JSON audit —
  DQI not computed). Economic impact: 7,842.11 USD recorded this period —
  recorded basis only. Alternatives: SOC floor retune (+1,204.55 USD
  recorded). Status: Decision not yet issued."
- Governance chip sequence: `EDDEC-…` → `EDLIFE: EXECUTED` → `EDOUT-…` →
  `EDGOV: VERIFIED` — the loop as jewelry.

**Failure Cases.**
- "We recommend enabling dynamic dispatch." with nothing else — unlawful
  render; blocked.
- Confidence shown as "B (estimated)" when the API returned null —
  fabrication; worst-class failure.
- An experimental optimizer surfaced as the primary action — gating
  violation.

**Governance Rules.** The block anatomy is amendable only by ratification;
any new machine-output surface must register its anatomy mapping in GOV-DR
before implementation.

---
---

# PART III — VISUALIZATION

---

# SPEC-DV — Data Visualization 1.0

**Purpose.** The rendering discipline for all visual data: truth, restraint,
and identity in every axis, area, and tooltip — regardless of which
instrument (SPEC-CH) is being drawn.

**Vision.** Every visualization reads as economic evidence prepared for a
board, not as library output.

**Responsibilities.**
- Own the render rules any instrument must obey: quiet hairline grids,
  tertiary-text axes, panel-styled tooltips, gradient-to-transparent area
  fills, semantic series colors, mono numerals on axes and tooltips.
- Own **axis truth**: baselines and breaks explicit; no truncated axis may
  exaggerate movement without a visible break marker (P2).
- Own series honesty: real API series only; gaps render as gaps; empty and
  insufficient states are honest and directive; downsampling must be
  visually declared when applied.
- Own labeling: every visualization carries unit, currency, and period;
  money axes use the registered formatters.

**Boundaries.** How things render — *which* instruments exist and what
questions they answer is SPEC-CH; colors are SPEC-DS tokens; entrance
motion is SPEC-MO.

**Inputs.** Audit ledger series, gap attribution, root causes, history,
live buffers — existing API only.

**Outputs.** The render-discipline ruleset; the shared visualization theme
contract every instrument implementation must consume.

**Rules.**
1. No default library styling may remain visible — fonts, colors, grids,
   tooltips all themed (identity signature applies inside plots).
2. One accent series per visualization; comparisons use semantic palette
   members, never arbitrary hues.
3. Loss shading below benchmark, recover shading above — the economic
   orientation is constant product-wide.
4. Maximum data-ink discipline: no 3D, no drop shadows on marks, no
   decorative gradients beyond the sanctioned area fill.
5. Tooltips state figure + unit + timestamp + basis; hover never reveals
   information unavailable to keyboard/touch users (SPEC-AX).

**Acceptance criteria.** Screenshot review finds zero default-library
styling; axis-truth audit passes on every instrument; every plot labeled
with unit/period; empty-state review passes.

**Non-Goals.** Instrument taxonomy (SPEC-CH); animation choreography
(SPEC-MO); exotic chart types.

**Future Extensions.** Canvas/WebGL render path for T5 walls; synchronized
brushing across instruments in a region.

**Dependencies.** SPEC-DS, SPEC-ID, SPEC-CH, SPEC-MO, SPEC-AX; principles
P2, P4, P10.

**Examples.**
- Financial Timeline: ink plot, hairline grid, teal actual vs slate
  benchmark, rose shading where actual underruns, mono axis money.
- Tooltip: "14:35 · Price 82.40 USD/MWh · Dispatch 38 MW · EDV gap 41.22
  USD (recorded)".

**Failure Cases.**
- Default blue/white tooltip — identity break inside evidence; blocked.
- A y-axis starting at 90% of range making a 2% dip look like a collapse —
  axis-truth violation; worst-class P2 defect.

**Governance Rules.** Render rules amendable by ratification; every
instrument implementation passes DV review before registry activation.

---

# SPEC-CH — Decision Instrument Library 1.0

**Purpose.** Replace generic charts with **Decision Instruments** — named,
governed visualizations that each answer one executive question with
economic meaning. *Charts are forbidden; instruments are required.*

**Vision.** A cockpit of financial instruments as recognizable as a
Bloomberg pane or an F1 pit wall — but answering PREDAIOT's questions.

**Responsibilities.**
- Own the **Instrument Registry**. Every visualization in the product is a
  registered instrument. The word "chart" is banned from product copy.
- Founding registry (all inputs are existing API data):

| Instrument | Question | Economic meaning | Inputs (existing) |
|------------|----------|------------------|--------------------|
| IN-01 Economic Dial | Q3 | Share of achievable value captured | `dq_score` (ECF), `risk_level` |
| IN-02 Opportunity Ladder | Q4 | Ranked recoverable actions by recorded gain | `opportunities[]` |
| IN-03 Decision Timeline | Q5/Q7 | When decisions were made and their quality | `decision_log`, DEC-LIFE events |
| IN-04 Economic Allocation | Q1/Q5 | Where the period's value went (captured / forecast-unreachable / execution gap) | `edv_actual_total`, `gap_attribution`, `edv_optimal_total` |
| IN-05 Risk Horizon | Q3/Q8 | Risk banding across audited periods | audit history risk levels |
| IN-06 Leakage Flow | Q5 | Leakage decomposed by root cause | `root_causes[]` |
| IN-07 Recoverable Value River | Q2 | Cumulative recoverable value across the period | ledger execution-gap series |
| IN-08 Confidence Spectrum | Q6 | Data-quality components → audit confidence | `data_quality_index.components`, `audit_confidence` |
| IN-09 Governance Chain | Q6 | Hash-linked verification lineage | governance / lifecycle / outcome records |
| IN-10 Decision Sankey | Q5/Q6 | Decisions flowing through lifecycle to outcomes | DEC → DEC-LIFE → OUT records |
| IN-11 Asset Health Matrix | Q8 | Portfolio grid: asset × capture/risk | `/api/v1/audits` history |
| IN-12 Executive Heatmap | Q5 | Decision quality by time-of-day/step | heat map data (existing S08) |
| IN-13 Financial Timeline | Q1 | Money over time: actual vs benchmark, loss shaded | ledger series |
| IN-14 Action Priority Matrix | Q4 | Recorded impact × evidence confidence quadrant | `opportunities[]` (`period_gain` × confidence/experimental flags) |

- Each registered instrument defines, in its registry entry:
  **Purpose · Question Answered · Economic Meaning · Inputs · Outputs ·
  Interaction Rules · Acceptance Criteria.** The founding entries above fix
  the first five; interaction and acceptance follow the global rules below
  until per-instrument sheets are ratified in Phase 5.

**Boundaries.** Instrument taxonomy and meaning; rendering discipline is
SPEC-DV; placement is SPEC-WS/DB; motion is SPEC-MO.

**Inputs.** Question Registry (SPEC-IA); frozen API series and records.

**Outputs.** The Instrument Registry (mirrored in GOV-DR); per-instrument
contract sheets (Phase 5 deliverable).

**Rules.**
1. No unregistered visualization may ship. Generic "add a chart" requests
   resolve to an existing instrument or a registry proposal.
2. Every instrument names exactly one primary question; instruments that
   answer nothing are removed (Existence Test).
3. Axes of judgment must be recorded data: e.g., IN-14 uses recorded gain ×
   evidence confidence — never invented "effort" scores (P2).
4. Instruments carry their economic orientation constantly (loss below/
   rose; recover above/green) — a reader who learns one instrument has
   learned them all.
5. Interaction: hover inspects, click pins evidence, nothing navigates
   without explicit affordance; every interaction has keyboard parity.
6. IN-09 Governance Chain must render real hash linkage — visual chains
   without verifiable hashes are forbidden.

**Acceptance criteria.** Registry complete and mirrored in GOV-DR; each
shipped instrument passes its contract sheet + DV render audit; zero
unregistered visualizations in the tree; copy audit finds no "chart" in
product surfaces.

**Non-Goals.** Decorative infographics; 3D; instruments for questions
outside the registry.

**Future Extensions.** IN-15 Outcome Realization instrument (recorded
realized vs recorded expected) as Outcome history accumulates; T5
wall-scale composite instruments.

**Dependencies.** SPEC-IA, SPEC-DV, SPEC-DS, SPEC-MO, SPEC-AX; principles
P1, P2, P6, P7.

**Examples.**
- IN-04 Economic Allocation replaces the "value flow" stacked view: one
  horizontal allocation bar — captured (green), execution gap (rose),
  forecast-unreachable (slate) — with the ceiling explicitly labeled
  "benchmark, not a target".
- IN-02 Opportunity Ladder: rungs sorted by recorded gain, EXPERIMENTAL
  rungs visually quarantined below the line.

**Failure Cases.**
- A pie chart of asset types — unregistered, answers no question; removed.
- IN-14 with a made-up "implementation effort" axis — P2 violation.
- A sparkline added "for texture" — decorative; Existence Test failure.

**Governance Rules.** The registry is append-only; new instruments enter by
ratified proposal (question + meaning + inputs verified against frozen
API); instrument retirement requires proof no manifest references it.

---

# SPEC-MO — Motion Language 1.0

**Purpose.** Motion as meaning: animation communicates state change —
money moved, evidence arrived, a system is live. Nothing else moves.

**Vision.** The stillness of a private bank lobby, broken only when
something true happens.

**Responsibilities.**
- Own the motion vocabulary: durations 140ms (state), 260ms (entrance),
  520ms (money count-up); one easing family (the product's signature
  deceleration curve); the sanctioned patterns — rise-in for arriving
  content, count-up for money, pulse for live signals, sweep for gauges.
- Own the meaning map: each pattern is bound to a semantic event; using a
  pattern for a different meaning is a violation.
- Own restraint: motion frequency budgets per screen; loops reserved for
  genuinely live data.

**Boundaries.** Token values live in SPEC-DS; instrument-entrance specifics
in SPEC-DV/CH; loading skeletons in SPEC-IX.

**Inputs.** State-change events (data arrival, provenance transitions,
user actions); reduced-motion preference.

**Outputs.** The motion vocabulary and meaning map; the animation review
checklist.

**Rules.**
1. Compositor-only: animate transform and opacity exclusively; 60fps is a
   law, not a target (P5-perf via SPEC-PF).
2. Every animation names its meaning at review ("money changed", "evidence
   arrived", "stream is live"). Unnamed motion is removed (P10).
3. No bounce, spin, parallax, shimmer-theatrics, or scroll-jacking. Ever.
4. Looping motion only for live provisional streams; certified/static data
   never loops.
5. Reduced-motion disables all non-essential animation; money renders at
   final value instantly.
6. Provenance transitions (PROVISIONAL → CERTIFIED) receive the most
   deliberate animation in the product — trust arriving is the one moment
   worth ceremony (still ≤ 520ms).

**Acceptance criteria.** Performance trace shows zero layout/paint work
from animation; motion inventory per screen ≤ budget; reduced-motion audit
passes; every registered animation carries its meaning in GOV-DR.

**Non-Goals.** Page-transition cinematics; Lottie/video; easter eggs.

**Future Extensions.** T5 wall zone-stagger choreography (ratified
amendment); haptic-paired motion on touch hardware.

**Dependencies.** SPEC-DS, SPEC-LX, SPEC-PF, SPEC-AX; principles P8, P10.

**Examples.**
- Audit completes: zones rise-in staggered 60ms; leakage counts up 520ms;
  evidence chip fades in last — the story lands in hierarchy order.
- Live tick: the LIVE dot breathes; the leakage numeral steps without
  easing theatrics.

**Failure Cases.**
- A hover bounce on KPI cards — banned pattern; removed.
- Count-up applied to a hash — motion without meaning (hashes don't
  accumulate); violation.
- A perpetual sheen sweep across certified panels — loop on non-live data.

**Governance Rules.** The vocabulary is closed; new patterns enter only by
ratified amendment with a named meaning and performance evidence.

---

# SPEC-LX — Industrial Luxury Language 1.0

**Purpose.** Define how PREDAIOT feels expensive: institutional, executive,
financial, confident, calm, scientific, trustworthy, premium, timeless.
Never flashy, gaming, cyberpunk, consumer-SaaS, or futuristic for its own
sake.

**Vision.** The product feels like a precision instrument delivered in a
machined case: weight you sense, restraint you trust.

**Responsibilities.**
- **Materials.** Layered ink surfaces (the luminance staircase bg-0 →
  panel-3); matte, never glossy; metalized accents only in the certificate
  seal context.
- **Depth.** Two elevations (resting, raised) plus the canvas — depth
  states hierarchy, never spectacle.
- **Glass.** Blur reserved for sticky chrome (header, drawers) — content
  never sits on glass; evidence is always on solid ground.
- **Contrast.** High contrast is spent on money and verdicts; everything
  else lives in the mid-range. Contrast is the loudest voice in the room
  and is rationed accordingly.
- **Lighting.** One implied light source from above: inset top highlights,
  soft under-shadows; glow only as meaning (money, live, seal).
- **Animation.** Defers to SPEC-MO — luxury moves rarely and lands softly.
- **Spacing.** Generosity correlates with consequence: the leakage figure
  gets the widest margins in the product.
- **Silence.** The default state of every screen is still and quiet; sound
  is never used.
- **Negative Space.** Emptiness is structural — zones breathe between, not
  inside; a crowded panel is a defect, not density.
- **Professional Confidence.** The interface never begs (no "Upgrade
  now!"), never apologizes decoratively, never over-explains. It states,
  it proves, it waits.

**Boundaries.** Feel and material physics; exact tokens in SPEC-DS;
identity marks in SPEC-ID; motion mechanics in SPEC-MO.

**Inputs.** SPEC-ID identity; the anti-reference list (what PREDAIOT must
never feel like).

**Outputs.** The material ruleset; the luxury review rubric used in GOV-AC.

**Rules.**
1. The anti-list is absolute: no neon-on-black gaming palettes, no
   cyberpunk glitch, no consumer-SaaS friendliness (rounded mascots,
   confetti, marketing gradients), no sci-fi HUD cosplay.
2. Saturated area ≤ 10% of any screen; glow only on money, live, seal.
3. Nothing blinks for attention; urgency is expressed by hierarchy and
   semantics, not by alarm aesthetics.
4. Every surface passes the "timeless test": would this look dated in five
   years? Trend-driven treatments are rejected.
5. Density is earned: evidence tables may be dense; answers may not.

**Acceptance criteria.** Luxury rubric passes per screen (materials, depth,
contrast rationing, negative space); anti-list audit clean; a printed
grayscale screenshot still reads hierarchy correctly (luxury survives
without color).

**Non-Goals.** Skeuomorphism; darkening for its own sake; brand marketing
surfaces.

**Future Extensions.** Light-theme luxury (daylight institutional); physical
control-room profiles (matte wall displays).

**Dependencies.** SPEC-ID, SPEC-DS, SPEC-MO; principles P4, P8, P10.

**Examples.**
- The certificate surface: gold seal accent on matte ink, wide margins,
  mono registry number — a document, not a modal.
- Severe risk state: rose semantics and hierarchy weight — no siren
  banners, no flashing.

**Failure Cases.**
- A glowing grid-line background "for tech feel" — cyberpunk drift;
  removed.
- An upgrade banner with a gradient CTA inside the workspace — consumer
  SaaS drift; removed.
- Ten saturated series colors in one instrument — contrast inflation.

**Governance Rules.** The anti-list is append-only; material rules amend
only by ratification; the luxury rubric is part of every acceptance pack.

---
---

# PART IV — PRODUCT

---

# SPEC-CO — Component Registry 1.0

**Purpose.** A governed component catalog — the UI equivalent of
METRIC_REGISTRY. Components enter by registration, never by improvisation.

**Vision.** Any engineer, in any future year, opens the registry and knows
exactly what exists, why, and what each piece may and may not do.

**Responsibilities.**
- Own the registry. Founding entries:

| Component | Status | Owner spec |
|-----------|--------|------------|
| Panel, KpiCard, AnimatedNumber, GradeBadge, EvidenceBadge, StatusDot, SectionTitle, Sparkline*, Trend, Divider | EXISTS (design system home) | SPEC-DS/CO |
| SectionHeader, Pill, BtnOutline, ProgressBar, Card (legacy bridge) | EXISTS — migrate & retire | SPEC-CO |
| Workspace, Region, Zone, tier hook | PLANNED | SPEC-WS |
| Economic Context Strip | PLANNED | SPEC-DL |
| Recommendation Block | PLANNED | SPEC-AI |
| Decision Instruments IN-01…IN-14 | PLANNED | SPEC-CH |
| Button family, Skeleton, Toast, EmptyState | PLANNED | SPEC-IX |
| Archetype Switcher | PLANNED | SPEC-RB |

  *Sparkline is re-registered as an instrument primitive under SPEC-CH
  during Phase 5.
- Enforce: components consume tokens only; components never fetch data
  (data arrives as props from zones/screens); one component, one
  responsibility; props are semantic (`grade`, `provisional`, `live`),
  never raw colors.

**Boundaries.** Inventory and entry rules; visual identity is SPEC-ID;
behavior states are SPEC-IX.

**Inputs.** Token registry; interaction grammar; accessibility rules.

**Outputs.** The registry (mirrored in GOV-DR); migration list retiring the
legacy bridge.

**Rules.**
1. A new component requires: registry entry, principle citation, question
   or purpose declaration (Five Purposes Test), state matrix (SPEC-IX),
   token-only styling, accessibility notes.
2. Legacy bridge components are frozen — no new features; feature work
   happens in the design-system home.
3. Composition over configuration: variants multiply only with registered
   justification.
4. No component may embed copy that violates SPEC-ST voice.

**Acceptance criteria.** Zero unregistered reusable components in the tree;
zero data-fetching imports in registered components; bridge retirement
tracked to completion during migration phases.

**Non-Goals.** External publication; visual regression tooling choice
(Phase 9 decides documentation/tooling).

**Future Extensions.** Extraction as a versioned internal package;
manifest-driven component provenance stamps.

**Dependencies.** SPEC-DS, SPEC-IX, SPEC-AX; principles P4, P5.

**Examples.**
- Registering the Recommendation Block cites P9 + Q4 and ships with its
  full state matrix before first render.

**Failure Cases.**
- A one-off styled div copy-pasted across three sections — unregistered
  de-facto component; consolidation required.
- A component accepting `color="#FF5C7A"` — semantic-prop violation.

**Governance Rules.** Registry is append-only with retirement protocol
(proof of zero references); entries carry their owning spec and principle
citations.

---

# SPEC-NV — Navigation 1.0

**Purpose.** Navigation as an instrument rail: grouped by the Section
Taxonomy, quiet, instant — choosing the next executive question.

**Vision.** Wayfinding so calm it disappears; the questions are the map.

**Responsibilities.**
- Render the SPEC-IA taxonomy groups (COMMAND / ANALYSIS / ACTION /
  EVIDENCE & GOVERNANCE / OPERATIONS / REFERENCE) with microcaps group
  kickers; items keep number + name in mono tags; glyph tags (⚡/🏆) are
  retired per SPEC-ID iconography.
- Own the header action bar: one accent primary, quiet neutral utilities,
  identity, session badge — nothing more; overflow moves to menus.
- Own the sidebar geometry contract with SPEC-WS (expanded/rail/drawer).

**Boundaries.** Chrome only; taxonomy is SPEC-IA; archetype ordering is
SPEC-RB; widths are SPEC-WS.

**Inputs.** Section registry, tier signal, archetype signal.

**Outputs.** Sidebar/heade­r/drawer contracts; active-state language
(accent left rule, kept).

**Rules.**
1. Any section reachable in ≤ 2 interactions from anywhere.
2. Groups never nest beyond one level; section switching is instant with
   no data refetch when state is unchanged.
3. Active section is always visible in the rail and in the workspace
   header context.
4. Navigation never carries data or badges that fabricate urgency;
   counts appear only when they answer a question (e.g., ungoverned
   decisions count, from real records).

**Acceptance criteria.** Interaction-distance audit passes; grouped rail
matches the taxonomy table exactly; keyboard traversal per SPEC-AX;
switch latency within SPEC-PF budget.

**Non-Goals.** Multi-level trees; breadcrumbs; URL routing rework
(future).

**Future Extensions.** Deep links per section; command palette (with
SPEC-IX); archetype-ordered rails (SPEC-RB).

**Dependencies.** SPEC-IA, SPEC-WS, SPEC-RB, SPEC-AX; principles P1, P5.

**Examples.**
- EVIDENCE & GOVERNANCE group: Governance · Certificate · Audit History —
  the proof shelf, one place.

**Failure Cases.**
- A red badge pulsing on a nav item to drive engagement — fabricated
  urgency; removed.
- A section reachable only through another section — distance violation.

**Governance Rules.** Rail structure changes require SPEC-IA taxonomy
amendment first; header additions require an Existence Test record.

---

# SPEC-DB — Dashboard Manifest 1.0

**Purpose.** The assembly contract: every dashboard is a declared
composition of zones, instruments, and narrative beats — never an
invention.

**Vision.** Dashboards become auditable artifacts: read the manifest,
know the screen — before it is built.

**Responsibilities.**
- Own the manifest schema, required before implementation:

```
Dashboard Manifest (required fields)
- id, title
- primary question (SPEC-QA registry ref, mapped via SPEC-IA)
- decision stages served (SPEC-DM: Observe / Understand / Trust /
  Decide / Execute / Verify / Learn — at least one)
- value classes displayed (SPEC-EV: lost / recoverable / saved /
  protected / at-risk / verified — every money figure classified)
- narrative beat map (SPEC-ST beats → zones)
- hierarchy declaration (SPEC-DL bands, top to bottom)
- zones used (WS catalog refs) + tier visibility row
- instruments used (SPEC-CH registry refs)
- data endpoints consumed (frozen API refs)
- trust artifacts carried (SPEC-TM mechanisms present)
- archetype emphasis notes (SPEC-RB, if any)
- acceptance evidence: tier screenshots, five-second test result,
  compliance checklist outcome
```
- Hold S01 Executive Command Center as the reference manifest.

**Boundaries.** Composition contracts; the parts belong to their owning
specs.

**Inputs.** All Part I–III registries.

**Outputs.** The manifest registry (GOV-DR mirror); the acceptance evidence
packs consumed by GOV-AC.

**Rules.**
1. No dashboard without a ratified manifest; no zone or instrument outside
   the registries.
2. The primary question's answer occupies the visual apex (SPEC-DL).
3. Dashboards degrade across tiers only via the WS visibility matrix —
   never by ad-hoc styling.
4. Manifests are living contracts: implementation drift from manifest is a
   defect on whichever side is wrong — reconciled before ship.

**Acceptance criteria.** Manifest exists and matches implementation
one-to-one; evidence pack archived; checklist passes; drift audit clean at
each release.

**Non-Goals.** User-built dashboards (future); manifest-driven runtime
rendering (future).

**Future Extensions.** Manifests as machine-readable artifacts driving
scaffolding; portfolio and wall-mode manifests.

**Dependencies.** Everything in Parts I–III; principles P1, P2, P6.

**Examples.**
- S01 manifest: Q1 primary; beats 1–6 mapped to Z1/Z2/Z3/Z4(+Z5/Z6 T3+);
  instruments IN-13, IN-01, IN-02; endpoints: audit response (+ live state
  when streaming).

**Failure Cases.**
- A screen shipped from a Figma-style improvisation with no manifest —
  blocked at review regardless of quality.
- Manifest listing IN-09 while the screen renders an unregistered chain
  graphic — drift; reconciliation required.

**Governance Rules.** Manifests are versioned and append-only; amendments
follow GOV-RP; the reference manifest (S01) changes only with re-run
five-second evidence.

---

# SPEC-IX — Interaction Language 1.0

**Purpose.** One interaction grammar: every control behaves predictably in
every state; every data surface declares its lifecycle states.

**Vision.** Interaction so consistent that learning one screen teaches the
whole product.

**Responsibilities.**
- Own the state matrices: interactive elements (default / hover / focus /
  active / disabled / loading) and data surfaces (loading / empty / error /
  populated), with SPEC-ID's state languages as the visual layer.
- Own the action hierarchy: one accent primary per view; quiet neutrals for
  everything else (ratified pattern).
- Own feedback: inline confirmation at the artifact, skeletons shaped like
  incoming answers, recoverable in-place errors, no dead ends.

**Boundaries.** Grammar only; visuals from SPEC-ID/DS; motion from SPEC-MO;
copy from SPEC-ST.

**Inputs.** Request lifecycle; user events; provenance transitions.

**Outputs.** State-matrix templates for component registration; interaction
review checklist.

**Rules.**
1. **No optimistic UI for economic data** — figures render only from server
   truth; pending states are explicit (P2).
2. Empty states are directive; errors state impact + recovery path; neither
   ever fabricates content.
3. Destructive or irreversible actions require explicit typed/structured
   confirmation; uploads validate before submission.
4. Hover is never the sole carrier of information (SPEC-AX parity).
5. Toasts only confirm what the surface already shows; they never carry
   sole evidence.
6. Focus is managed at every transition (modals, drawers, section switch)
   — keyboard users never lose their place.

**Acceptance criteria.** State-matrix audit passes per registered
component; demo→audit→certificate flow has zero dead ends; keyboard parity
verified; optimistic-render grep audit clean for economic surfaces.

**Non-Goals.** Undo infrastructure; collaborative presence.

**Future Extensions.** Command palette; keyboard shortcut map; T4/T5
pin-to-rail interactions.

**Dependencies.** SPEC-ID, SPEC-MO, SPEC-AX, SPEC-ST; principles P3, P5.

**Examples.**
- Running an audit: primary button → engine phrase skeleton in Z2 shapes →
  zones rise-in with results → evidence chip lands last.

**Failure Cases.**
- Leakage number animating to a guessed value before the response —
  optimistic economics; worst-class violation.
- An error modal with only "OK" — dead end; must offer retry/path.

**Governance Rules.** Grammar changes by amendment; every new interactive
pattern registers its matrix before first use.

---

# SPEC-SX — Security UX 1.0

**Purpose.** Render the platform's real security architecture visibly —
trust must be perceivable — without security theater.

**Vision.** Users feel custody: every figure visibly chained to evidence,
every session honestly stated, every boundary quietly firm.

**Responsibilities.**
- Surface the evidence chain: truncated SHA-256 chips with copy-full,
  certificate registry numbers with verification URL, governance/lifecycle
  chain chips (IN-09), provenance badges (CERTIFIED/PROVISIONAL) with
  EDA-RECON semantics.
- Surface session truth: identity, org, trial state and expiry — factual,
  quiet.
- Own data-sensitivity presentation: masked emails, no tokens/secrets in
  URLs or full plaintext, no internal identifiers in errors.

**Boundaries.** Presentation of the frozen security layer only; enforcement
(RBAC, headers, encryption, rate limits, hash chains) is backend-owned.

**Inputs.** Existing fields: manifests, certificates, governance records,
session/trial state, roles.

**Outputs.** Trust-surface inventory per screen; masking rules; error
disclosure policy.

**Rules.**
1. Every economic figure sits within reach of its evidence affordance (P7)
   — hash, badge, grade, or chain link.
2. PROVISIONAL and CERTIFIED are never conflated — visually, verbally, or
   by animation; transitions between them are explicit (SPEC-MO ceremony).
3. Errors disclose what failed and the next step — never stack traces,
   never internals (P4).
4. No decorative security iconography — padlocks appear only where a
   verifiable property exists.
5. Copy-to-clipboard of evidence always copies the full value with its
   context label.

**Acceptance criteria.** Trust-surface inventory complete for every
data-bearing screen; secret-leak audit clean (URLs, DOM, clipboard);
provenance E2E verified; error-disclosure review passes.

**Non-Goals.** New auth flows; changing backend security; compliance
certifications UI (future).

**Future Extensions.** In-UI certificate verifier (existing verify
endpoint); governance-chain explorer as IN-09 deepens.

**Dependencies.** SPEC-ID (evidence styling), SPEC-CH (IN-09), SPEC-IX;
principles P2, P3, P4, P7.

**Examples.**
- Certificate surface: registry number mono, issue context, verification
  URL, DQI/confidence grades — a document with provable anchors.

**Failure Cases.**
- A trial token appearing in a shareable URL — leak class; blocked.
- A padlock icon on a marketing claim — theater; removed.

**Governance Rules.** Masking and disclosure rules amend only by
ratification; every new surface passes the trust-inventory check before
ship.

---

# SPEC-AX — Accessibility 1.0

**Purpose.** WCAG 2.2 AA: institutional software operable by every
executive and operator, under boardroom or plant-floor conditions.

**Vision.** Accessibility as institutional quality — the same rigor the
platform applies to economic truth, applied to human access.

**Responsibilities.** Contrast floors; keyboard completeness; semantic
structure; focus management; non-color encodings; touch targets; motion
opt-out.

**Boundaries.** Token contrast set in SPEC-DS; motion opt-out in SPEC-MO;
state parity in SPEC-IX; responsive targets shared with SPEC-RS.

**Inputs.** Tokens, component registry, instrument registry, audit tooling
results.

**Outputs.** Per-screen audit reports in acceptance packs; the exception
register (empty by default).

**Rules.**
1. Text contrast ≥ 4.5:1 (≥ 3:1 for large text); verified for every text
   token on every sanctioned surface.
2. Color never the sole carrier: grades keep letters, badges keep words,
   trends keep direction glyphs, instruments keep labels/patterns.
3. Full keyboard path through every flow; visible focus ring in accent;
   no hover-only information anywhere (with SPEC-IX).
4. Landmarks and headings semantically ordered; instruments expose text
   alternatives stating their answer ("Capture 3.1% — Severe risk").
5. Touch targets ≥ 44px on T1; reduced-motion honored globally.

**Acceptance criteria.** Zero critical/serious findings per screen in
automated audit; keyboard-only completion of demo → audit → certificate;
instrument text alternatives reviewed; reports archived per release.

**Non-Goals.** AAA conformance; screen-reader table optimization for
288-step ledgers (summary + export covers duty).

**Future Extensions.** High-contrast theme via the token scaffold; RTL
support paired with SPEC-ST localization.

**Dependencies.** SPEC-DS, SPEC-IX, SPEC-MO, SPEC-RS; principles P4, P5.

**Examples.**
- IN-01 Economic Dial exposes: role, label, value, risk verdict — a
  screen-reader user hears the answer, not geometry.

**Failure Cases.**
- Severity conveyed by hue alone in IN-12 — non-color encoding violation.
- Focus trapped in the trial gate modal — flow-blocking defect.

**Governance Rules.** Exceptions require ratified amendment with expiry;
the exception register is reviewed every release.

---

# SPEC-RS — Responsive System 1.0

**Purpose.** Desktop-first adaptation inside the WS tiers: the same truth
from a 49-inch wall to a phone, degrading co-presence — never integrity.

**Vision.** T1 is a faithful pocket briefing of the same institution — not
a different product.

**Responsibilities.** Component-level adaptation: stack order on T1
preserving Q1→Q4; ledger tables transform to evidence cards; header
condenses per existing pattern; numerals scale by clamp; instruments define
their compact renders.

**Boundaries.** Zone visibility is SPEC-WS's matrix; this spec governs
inside-zone reflow.

**Inputs.** Tier signal; existing drawer threshold (720px); instrument
compact contracts.

**Outputs.** Reflow rules per component class; instrument compact-mode
requirements.

**Rules.**
1. Desktop is the origin; T1 reduces faithfully — no separate mobile
   product, no lost evidence.
2. No horizontal scroll; no clipped numerals; clamp scaling mandatory.
3. T1 reading order = Q1→Q4 then beats 5–6 (SPEC-DL/ST preserved).
4. Touch affordances on T1: 44px targets, drawer navigation, no
   hover-dependence.
5. Every instrument ships a compact render or declares itself T2+-only in
   its registry entry (then its answer appears as a stated figure on T1).

**Acceptance criteria.** 390/768/1024/1440/1920/2560/3440 clean renders
(no overflow/clipping); T1 shows all four answers within two screenfuls;
instrument compact audits pass.

**Non-Goals.** Native apps; print styles (PDF path exists); offline mode.

**Future Extensions.** Compact density mode for control rooms; foldable
postures.

**Dependencies.** SPEC-WS, SPEC-DL, SPEC-AX, SPEC-CH; principles P1, P5.

**Examples.**
- T1 S01: leakage card → recoverable card → health card → recommendation
  block → evidence chips — the briefing in one thumb-length.

**Failure Cases.**
- A table forcing horizontal scroll at 390px — law violation.
- An instrument silently absent on T1 with its answer nowhere — integrity
  loss; must state its figure.

**Governance Rules.** Reflow rules amend by ratification; instrument
compact contracts live in the CH registry.

---

# SPEC-PF — Performance 1.0

**Purpose.** Institutional speed: latency erodes trust; the product must
feel instantaneous at every tier.

**Vision.** The instrument responds like a machined dial — immediate,
damped, certain.

**Responsibilities.** Budgets and enforcement: bundle, runtime, streaming,
animation cost; the techniques ledger (splitting, virtualization,
memoization, throttling).

**Boundaries.** Backend latency out of scope (frozen); this spec owns
everything after bytes arrive.

**Inputs.** Build stats, runtime profiles, live message rates, tier
signal.

**Outputs.** Enforced budget gates; the lazy-loading map; virtualization
inventory; per-release performance evidence.

**Rules (budgets).**
1. Initial JS ≤ 250 kB gzip (regression gate at current ~214 kB).
2. Heavy, non-first surfaces split: instrument vendor code, Math Appendix,
   Certificate/PDF, Live Monitor.
3. Lists > 100 rows virtualized or paginated (ledgers, history, streams).
4. Live feed commits batched ≤ 4/s; zone boundaries memoized against
   re-render storms.
5. Animation ≤ 16 ms/frame (SPEC-MO compositor law); tier/section switch
   < 200 ms perceived.
6. Reference scores: Lighthouse desktop ≥ 90 on S01 with demo data.

**Acceptance criteria.** CI bundle gate green; live-mode profile shows
bounded commits; budget evidence archived per release; no jank traces on
instrument entrances.

**Non-Goals.** SSR/SEO; offline caching; premature micro-optimization.

**Future Extensions.** WebGL instrument offload at T5; worker-side series
downsampling; performance telemetry dashboards (internal).

**Dependencies.** SPEC-MO, SPEC-WS, SPEC-CH; principle P5.

**Examples.**
- Opening Math Appendix loads its chunk on demand; S01 never pays for it.

**Failure Cases.**
- A dependency bump pushing initial JS to 280 kB — gate failure, ship
  blocked.
- Live telemetry re-rendering the whole workspace per tick — storm class;
  fix before ship.

**Governance Rules.** Budgets amend only by ratification with evidence;
every release attaches its performance pack to GOV-AC.

---
---

# PART V — GOVERNANCE

---

# GOV-CM — Compliance Matrix 1.0

**Purpose.** The living cross-reference proving that every shipped artifact
satisfies its governing specs and principles.

**Structure.** One row per registered artifact (screen, zone, component,
instrument, animation pattern), columns: artifact id · owning manifest ·
SPEC-IDs satisfied · principles cited (P1–P10) · Existence Test record ·
Five Purposes declaration · last acceptance date · evidence pack reference.

**Rules.**
1. An artifact absent from the matrix may not ship.
2. Empty principle citations fail review — "it looks good" is not a row.
3. The matrix is regenerated and archived at every release; drift between
   matrix and tree is a release blocker.

**Governance Rules.** Matrix format amends by ratification; rows are
append-only with retirement markers.

---

# GOV-DR — Design Registry 1.0

**Purpose.** The registry-of-registries — the frontend's METRIC_REGISTRY.

**Contents.**
- Token Registry (SPEC-DS): every design token with identity citation.
- Component Registry (SPEC-CO): every reusable component with owner spec,
  state matrix, and status (EXISTS / PLANNED / BRIDGE-FROZEN / RETIRED).
- Instrument Registry (SPEC-CH): IN-01…IN-14 founding set with question,
  meaning, inputs; per-instrument contract sheets attach in Phase 5.
- Dashboard Manifest Registry (SPEC-DB): every dashboard's ratified
  manifest and evidence packs; S01 is the reference entry.
- Question Registry (SPEC-IA): Q1–Q9 with API bindings.
- Motion Vocabulary (SPEC-MO): each pattern with its bound meaning.
- Brand Signature list (SPEC-ID): the five marks.

**Rules.**
1. Registration precedes existence: nothing renders before its registry
   entry exists.
2. Every entry carries: owner spec, principle citations, data bindings
   (frozen API refs where applicable), status, and version.
3. Retirement requires proof of zero references (grep-verifiable) and a
   registry marker — entries are never deleted.

**Governance Rules.** The registry lives beside this document and is the
first artifact reviewed at every acceptance; unregistered artifacts found
in the tree are defects regardless of quality.

---

# GOV-AL — Amendment Log 1.0

**Purpose.** The append-only record of every ratified change to any
specification after ratification — the immutability mechanism.

**Format.**

| # | Date | Spec | Change | Rationale | Ratified by |
|---|------|------|--------|-----------|-------------|
| 0 | 2026-07-14 | ALL | PREDAIOT-FE-2.0 ratified in full (Parts 0–V + WS-1.0 annex); execution authorization issued; implementation phases 1–15 commence | Constitution complete after Part 0 consistency review | Platform architect |

**Rules.**
1. Amendments are proposed in writing, reviewed against affected specs
   (cascade analysis mandatory), and ratified explicitly before any
   implementation reflects them.
2. Amendments never rewrite history: the original text stays; the
   amendment states the delta.
3. Emergency changes do not exist. A defect fix that contradicts a spec is
   an amendment like any other — reviewed first.

**Governance Rules.** The log itself is unamendable; only appendable.

---

# GOV-AC — Acceptance Process 1.0

**Purpose.** The gate every artifact passes before shipping — the frontend
analog of the EDA production-verification ritual.

**Process (per artifact / release).**
1. **Manifest first** — the Dashboard Manifest (or registry entry) exists
   and is ratified before implementation begins.
2. **Implementation** — built against RATIFIED specs only.
3. **Evidence pack assembly** — tier screenshots (390 → 3440 as
   applicable), five-second test result (for question-bearing screens),
   accessibility report, performance numbers, axis-truth and identity
   checks, state-matrix walkthrough.
4. **Compliance review** — GOV-CM row completed; Existence Test and Five
   Purposes recorded; SPEC-ST voice review for copy.
5. **Sign-off** — recorded with date and reviewer; artifact status flips
   to ACCEPTED in GOV-DR.

**Global compliance checklist (every screen, every release).**
- [ ] Cites SPEC-IDs and principles; no uncited elements (Existence Test)
- [ ] Composes the Workspace; no max-width container; no centered column
- [ ] Primary question answered at the visual apex; hierarchy bands intact
      (Money → Risk → Opportunity → Decision → Evidence → Details)
- [ ] Six narrative beats mapped and ordered; voice rules pass
- [ ] All data from frozen APIs; provenance honest; basis disclaimers
      present; no fabrication anywhere
- [ ] Recommendation surfaces use the full SPEC-AI anatomy
- [ ] Only registered instruments; no "charts"; axis truth holds
- [ ] Tokens only; identity signature marks present; luxury rubric passes
- [ ] State matrices complete; no dead ends; no optimistic economics
- [ ] Accessibility clean; keyboard parity; reduced-motion honored
- [ ] No horizontal scroll 390 → 5120px; numerals never clip
- [ ] Performance budgets hold; evidence pack archived

**Governance Rules.** The checklist amends only by ratification; skipped
steps void the acceptance.

---

# GOV-RP — Ratification Procedure 1.0

**Purpose.** How this document and its parts become law, and how they
change afterward.

**Procedure.**
1. **Proposal** — a spec (or amendment) is authored in full contract form
   (the fourteen fields) and marked PROPOSED.
2. **Review** — the owner (the platform's architect — the user) reviews;
   amendments are stated explicitly, as in the EDA contract ritual.
3. **Ratification** — an explicit ratification statement freezes the spec:
   status flips to RATIFIED; the text becomes immutable except through
   GOV-AL amendments.
4. **Implementation authorization** — only RATIFIED specs may be
   implemented; implementation follows the phase order below, no phase
   starting before the previous one's acceptance criteria pass:
   1. Workspace System → 2. Information Architecture → 3. Executive
   Dashboard → 4. Role-Based Dashboards → 5. Chart Language (Decision
   Instruments) → 6. Motion System → 7. Accessibility & Responsiveness →
   8. Performance & Load Testing → 9. Design Documentation.
5. **Perpetuity** — future engineers inherit the specs, the registries,
   and the logs; nothing about the product's architecture lives only in
   anyone's memory.

**Rules.**
1. Partial ratification is permitted per-spec (e.g., ratify Part I while
   Part III is amended) — the index tracks status per spec.
2. Ratification of SPEC-WS ratifies its annex (`WORKSPACE_SPEC.md`).
3. A ratified spec contradicted by a later ratified spec requires an
   explicit reconciliation amendment — silent precedence does not exist.

**Governance Rules.** This procedure itself is amendable only by explicit
ratification; the procedure's history lives in GOV-AL like everything
else.

---
---

# CONSISTENCY REVIEW & TRACEABILITY — Part 0 → Parts I–V

**Method.** Every specification in Parts I–V was reviewed against Part 0
after its authoring. Verdicts: **CONSISTENT** (inherits cleanly) or
**HARMONIZED** (a pre-ratification edit was applied to align it; the edit
is listed in the Harmonization Log). No specification was found in
contradiction with Part 0.

## Traceability Matrix

| Spec | Inherits from (Part 0) | Manifesto laws enforced | Verdict |
|------|------------------------|--------------------------|---------|
| SPEC-PR Product Principles | MS (Existence Test), CA (Identity Law), FM (all laws → P1–P10) | FM-4, FM-10 | HARMONIZED (root-of-tree authority transferred to Part 0) |
| SPEC-ID Visual Identity | CA (recognizable category), TM (evidence styling), HM (recognition over recall) | FM-3, FM-4 | CONSISTENT |
| SPEC-DL Executive Design Language | EV (economic hierarchy), HM (answer-first), MS (money as native language) | FM-7 | CONSISTENT |
| SPEC-DS Design System | TR (visual truth in tokens), EV (class-color binding) | FM-4 | CONSISTENT |
| SPEC-WS Workspace System | VS (H3/H4 scaling), HM (attention), QA (zones bind questions) | FM-8 | CONSISTENT |
| SPEC-IA Information Architecture | QA (registry authority), CA (question-driven, not data-driven) | FM-7 | HARMONIZED (registry authority moved to SPEC-QA; IA owns mapping) |
| SPEC-EX Executive Experience | QA (Q1–Q4 supremacy), DM (Observe/Decide), HM (5-second law) | FM-7, FM-8 | CONSISTENT |
| SPEC-RB Role-Based Experience | HM (cognitive lenses), DM (stage emphasis per archetype), TR (truth invariant across lenses) | FM-1 | CONSISTENT |
| SPEC-ST Narrative Experience | DM (beats ≈ stages), HM (briefing cognition), QA (Q9 honesty) | FM-1, FM-2 | CONSISTENT |
| SPEC-AI AI Interaction Language | TR (decision truth), TM (governance status), FM (explanation duty) | FM-5, FM-3 | CONSISTENT |
| SPEC-DV Data Visualization | TR (visual truth), EV (value orientation in plots) | FM-2 | CONSISTENT |
| SPEC-CH Decision Instrument Library | QA (instruments bind to questions), DM (instruments serve stages), CA (instruments ≠ charts) | FM-4 | CONSISTENT |
| SPEC-MO Motion Language | HM (attention protection), TR (motion as true state change) | FM-8 | CONSISTENT |
| SPEC-LX Industrial Luxury Language | CA (anti-drift enforcement), Experience (institutional custody feel) | FM-4 | CONSISTENT |
| SPEC-CO Component Registry | MS (governed instruments of the mission), TM (registered provenance) | FM-4 | CONSISTENT |
| SPEC-NV Navigation | QA (navigation = choosing the next question), DM (loop reachability) | FM-8 | CONSISTENT |
| SPEC-DB Dashboard Manifest | DM (stage declarations), EV (value-class declarations), QA (primary question), TM (trust artifacts) | FM-10 | HARMONIZED (manifest schema extended: stages, value classes, trust artifacts) |
| SPEC-IX Interaction Language | TR (no optimistic economics), TM (honest states), HM (no dead ends) | FM-1 | CONSISTENT |
| SPEC-SX Security UX | TM (renders the trust ladder), TR (evidence truth surfaces) | FM-6 | CONSISTENT |
| SPEC-AX Accessibility | HM (access as cognitive equity), TM (trust must be perceivable by all) | FM-8 | CONSISTENT |
| SPEC-RS Responsive System | HM (Q1→Q4 reading order preserved), TR (no integrity loss on reduction) | FM-7 | CONSISTENT |
| SPEC-PF Performance | HM (latency is cognitive load), TM (speed is trust) | FM-8 | CONSISTENT |
| GOV-CM Compliance Matrix | MS/FM (mission-grade enforcement machinery) | all | CONSISTENT |
| GOV-DR Design Registry | TM (auditability applied to design itself) | FM-4, FM-6 | CONSISTENT |
| GOV-AL Amendment Log | TM (append-only trust discipline) | FM-1 | CONSISTENT |
| GOV-AC Acceptance Process | FM (attests all ten laws per release), HM (measured cognitive tests) | all | CONSISTENT |
| GOV-RP Ratification Procedure | MS (perpetuity beyond any engineer), CA (immutability mechanics) | all | CONSISTENT |

## Principles → Philosophy mapping (P1–P10 inherit from Part 0)

| Principle | Derives from |
|-----------|--------------|
| P1 Executive Clarity | SPEC-HM (answers, not dashboards), SPEC-QA (question charter) |
| P2 Economic Truth | SPEC-TR (truth pipeline), SPEC-EV (value classes), FM-1/2/9 |
| P3 Decision Confidence | SPEC-TM (confidence mechanism), SPEC-TR (INDETERMINATE as truth), FM-3 |
| P4 Institutional Trust | SPEC-CA (category dignity), SPEC-TM (trust ladder) |
| P5 Operational Efficiency | SPEC-HM (cognitive load), SPEC-VS (operating-system ambition) |
| P6 Narrative Intelligence | SPEC-DM (decision journey), SPEC-HM (answer-first cognition) |
| P7 Evidence First | SPEC-TM (evidence mechanism), SPEC-TR (evidence truth), FM-6 |
| P8 Industrial Luxury | SPEC-CA (not consumer software), The PREDAIOT Experience (institutional custody) |
| P9 AI Transparency | SPEC-TR (decision truth), FM-5 |
| P10 Visual Calm | SPEC-HM (attention as capital), FM-4/8 |

## Harmonization Log (pre-ratification edits applied during this review)

1. **Header** — authority chain extended: PART 0 inserted above Parts I–V;
   Identity Law now cites SPEC-CA as its constitutional source.
2. **SPEC-PR** — no longer "root of the tree": explicitly inherits Part 0;
   the P1–P10 → philosophy mapping fixed above.
3. **SPEC-IA** — Question Registry authority transferred to SPEC-QA
   (Part 0); SPEC-IA retains question-to-surface mapping and taxonomy.
4. **SPEC-DB** — manifest schema extended with three Part 0 declarations:
   decision stages served (SPEC-DM), value classes displayed (SPEC-EV),
   trust artifacts carried (SPEC-TM).
5. **Preamble** — constitutional contract form declared for Part 0 specs
   (Purpose · Declaration · Rules · Inheritance · Acceptance · Governance),
   distinct from the fourteen-field operational form of Parts I–IV.

No other inconsistencies were found. The beats-to-stages relationship
(SPEC-ST ↔ SPEC-DM) and the value-class-to-color binding (SPEC-EV ↔
SPEC-DS) were verified as compatible without edits.

## Eligibility statement

Every specification in Parts I–V inherits from the Product Philosophy, as
proven above. **PREDAIOT-FE-2.0 is now eligible for ratification** under
GOV-RP.

---
---

*End of PREDAIOT-FE-2.0. Status: RATIFIED 2026-07-14 in every part. This
specification is the immutable governing contract for every future
frontend implementation of the PREDAIOT Economic Decision Intelligence
Platform. Implementation is authorized strictly in phase order; changes
only through GOV-AL amendments.*




