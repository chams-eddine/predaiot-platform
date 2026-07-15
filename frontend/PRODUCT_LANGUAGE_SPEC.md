# PREDAIOT Product Language Specification — PL-1.0

**Status:** PROPOSED — awaiting ratification. On ratification it becomes the
governing contract for how every PREDAIOT screen *speaks*, and Waves 1–6 of
the Product Language Unification become mechanical application of this contract.
**Class:** Governed contract, derived from PREDAIOT-FE-2.0 (RATIFIED). It does
not supersede FE-2.0; it **concretizes** FE-2.0's language dialects into
operational law with a controlled vocabulary and an editorial system.
**Authority chain:** PLATFORM_BLUEPRINT.md → PRODUCT_SPEC.md (FE-2.0) →
**PL-1.0** → its annexes `LANGUAGE_REGISTRY.md` (LR-1.0, the lexicon) and
`EDITORIAL_SYSTEM.md` (ED-1.0, the style manual) → implementation waves.
**Backend:** FROZEN. Every clause binds to existing API fields only.
**Reference speaker:** S01 (the six-act Executive Briefing) is the canonical
implementation of this language; PL-1.0 generalizes it to the whole product.

---

## 0. The One-Language Law

> PREDAIOT is one product with one voice. Every screen is a page of the same
> briefing, not a member of the same React app.

Three inviolable laws govern the language (each derived, cited):

- **L1 — One meaning, one word.** A concept has exactly one canonical term
  across the product; synonyms are forbidden. (LR-1.0; SPEC-ID.)
- **L2 — One number, one voice.** Money, percentages, grades, and hashes are
  formatted one way everywhere; there is no second accent. (ED-1.0 §3;
  SPEC-DS rule 3.)
- **L3 — Truth is the vocabulary.** The product may only speak what the API
  reported; forbidden terms name things the platform disavows (fabrication,
  forward projection, monitoring identity). (SPEC-TR, SPEC-CA; P2/FM-1/FM-2.)

Every UI element must be pronounceable in this language. An element that
cannot be — a fabricated figure, an un-registered synonym, a forward
projection — does not exist (the Existence Test, applied to words).

---

## 1. The dialect contracts

The nineteen dialects of PLA-1.0 §4, elevated to formal clauses. Each carries
**Rule** (the law), **Acceptance** (how compliance is judged), **Derives**
(the FE-2.0 source), and **Registry/Editorial** (where the words and style
live). Every clause is cited by implementation and review as `PL-xx`.

### Foundational

**PL-TY — Executive Typography.**
Rule: two type voices only — Inter for prose, JetBrains Mono for every
numeral, hash, ID, and grade. Answers are 800-weight; context 400–600; money
and hashes always mono. Derives: SPEC-ID, SPEC-DS. Editorial: ED-1.0 §6.
Acceptance: no third typeface; every numeral mono.

**PL-CO — Economic Color.**
Rule: color is meaning — rose=loss, green=recovered/verified/protected,
amber=caution/provisional, teal=PREDAIOT intelligence, gold=certification;
saturated area < 10% of any screen. Never decorative. Derives: SPEC-DS,
SPEC-EV, SPEC-ID. Registry: LR-1.0 §2 (state→color). Acceptance: every color
maps to a registered meaning.

**PL-DEN — Information Density.**
Rule: dense evidence tables are lawful; dense *answers* are not. Density is
earned only when it reduces total effort. Derives: SPEC-HM, SPEC-LX.
Acceptance: the answer wins the squint test on every screen.

**PL-ED — Editorial.**
Rule: every screen reads answer-first — standfirst states the question, the
dominant figure answers, support follows, proof closes; alternating
containment, never a widget grid. Derives: SPEC-ST, SPEC-DL, SPEC-ID,
SPEC-LX. Editorial: **ED-1.0 in full** (this clause delegates to the annex).

### Evidence & Trust

**PL-EV — Evidence.**
Rule: evidence is jewelry — truncated mono hash chips with copy-full,
adjacent to the figure they certify; honest absence over silence. Derives:
SPEC-SX, SPEC-TM, P7. Registry: LR-1.0 §4. Acceptance: every economic figure
within reach of its proof; "None — …" where no artifact exists.

**PL-CF — Confidence.**
Rule: grade letter + % where present; **INDETERMINATE** is a first-class
honest state (neutral slate), never a fake grade. Derives: SPEC-AI, SPEC-TR,
SPEC-ID. Registry: LR-1.0 §4. Acceptance: no invented confidence; absence
stated.

**PL-GV — Governance.**
Rule: verdicts (VERIFIED / REJECTED / INCONCLUSIVE / PENDING) and lifecycle
states render as hash-linked chips — the loop as evidence, never as workflow
status. Derives: SPEC-TM, SPEC-CH (IN-09). Registry: LR-1.0 §3.

### Decision & Economic

**PL-DE — Decision.**
Rule: a recommendation is never bare — designation + reasoning + evidence +
confidence + expected impact + alternatives; a decision is text, its worth
and proof follow it. Derives: SPEC-AI. Registry: LR-1.0 §3. Acceptance: the
lawful anatomy present wherever a machine recommendation renders.

**PL-EC — Economic.**
Rule: every money figure declares exactly one value class — lost /
recoverable / saved / protected / at-risk / verified; benchmarks are context,
never a class; recorded-period only, never annualized/forward. Derives:
SPEC-EV, SPEC-AI rule 5, SPEC-QA Q9, FM-2. Registry: LR-1.0 §1, §5.
Acceptance: every money figure classified; zero forbidden temporal terms.

**PL-IN — Instrument.**
Rule: no "charts" — only registered Decision Instruments (IN-xx), each
answering one question, with hairline grids, mono axes, panel tooltips, axis
truth. Derives: SPEC-CH, SPEC-DV. Registry: LR-1.0 §6 (bans "chart").

### Experience & Interaction

**PL-AT — Attention.**
Rule: one primary emphasis per screen; the money answer wins the squint test;
nothing below the fold competes for attention. Derives: SPEC-DL, SPEC-HM,
P10. Acceptance: exactly one attention apex per view.

**PL-MO — Motion.**
Rule: four verbs only — rise (arrived), count-up (money changed), pulse
(live), sweep (verdict); transform/opacity only; loops only on live data;
reduced-motion honored. Derives: SPEC-MO. Acceptance: no motion without a
named meaning; no layout-property transitions.

**PL-NV — Navigation.**
Rule: the grouped instrument rail is the map (ratified taxonomy); one accent
primary action; active = accent left-rule; any section ≤ 2 interactions away.
Derives: SPEC-NV, SPEC-IA.

**PL-IX — Interaction.**
Rule: one accent primary per view, quiet neutrals for the rest; no optimistic
UI for economic data; hover never the sole carrier; every state matrix
complete. Derives: SPEC-IX, SPEC-AX.

**PL-SEL — Selection.**
Rule: selection is a quiet state change (accent rule / tint), reversible in
one interaction, keyboard-parity. Derives: SPEC-IX, SPEC-AX.

### System states

**PL-EM — Empty-State.**
Rule: honest + directive — name what is absent and the single action that
fills it; never sample data, never mascots. Derives: SPEC-ID, SPEC-IX.
Editorial: ED-1.0 §7. Registry: LR-1.0 §7 (bans fabricated fillers).

**PL-LD — Loading.**
Rule: skeletons shaped like the incoming answer; one quiet engine phrase for
compute; no spinners after first paint, no shimmer. Derives: SPEC-ID,
SPEC-IX, SPEC-MO. Editorial: ED-1.0 §7.

**PL-ER — Error.**
Rule: institutional candor in place — what failed, its impact, the recovery
path; no native dialogs, no stack traces, no dead ends. Derives: SPEC-IX,
SPEC-ID. Editorial: ED-1.0 §7. Acceptance: zero `alert()`; every failure
recoverable in place.

**PL-SU — Success.**
Rule: understated — the artifact (certificate, badge, notice) is the
celebration; no confetti, no exclamation. Derives: SPEC-ID. Editorial:
ED-1.0 §1, §7.

**PL-NT — Notification.**
Rule: quiet, factual, dismissible; confirms only what the surface already
shows; never fabricates urgency. Derives: SPEC-IX, SPEC-NV.

---

## 2. Compliance — the Language Gate

Every screen, before ship, passes the **Language Gate** (added to GOV-AC):

- [ ] Speaks all Five Questions (PLA-1.0 §1) or is an exempt reference surface
      carrying the Economic Context Strip (PL-EC / SPEC-DL Money-First Law).
- [ ] Every displayed term is in `LANGUAGE_REGISTRY.md` as canonical or
      allowed; zero forbidden terms (grep-verifiable set in LR-1.0).
- [ ] Every number obeys `EDITORIAL_SYSTEM.md` (one formatter, mono, units,
      basis disclosure on any period figure).
- [ ] Every money figure declares a value class; zero forward/annualized terms.
- [ ] Evidence/Confidence/Governance render in the PL-EV/PL-CF/PL-GV voice;
      absence stated honestly.
- [ ] One attention apex; motion vocabulary only; empty/loading/error/success
      in the PL-EM/LD/ER/SU voice.
- [ ] Cites the PL-xx clauses it satisfies (recorded in GOV-CM).

A screen that fails the Gate is not a "polish" defect — it does not yet speak
the language and does not ship.

---

## 3. Governance

- PL-1.0 and its annexes are ratified via the FE-2.0 procedure (GOV-RP):
  propose → architect ratifies with amendments → freeze → apply.
- After ratification, changes are **append-only amendments** logged in the
  master GOV-AL (PRODUCT_SPEC.md §17), referencing PL-xx / LR-§ / ED-§.
- The `LANGUAGE_REGISTRY` is append-only: terms are added or marked forbidden,
  never silently redefined. A term without an API binding cannot be canonical.
- Waves 1–6 (PLA-1.0 §5) implement this contract; each wave re-scores the
  Product Language Matrix until every row reads ✅.

---

## 4. Relationship to FE-2.0

PL-1.0 is to FE-2.0 what a nation's civil code is to its constitution: FE-2.0
declares the principles and the language dialects; PL-1.0 makes them
enforceable law with a dictionary (LR-1.0) and a style manual (ED-1.0). No
clause here originates new philosophy — each derives from a cited FE-2.0
specification. Where PL-1.0 and FE-2.0 appear to differ, FE-2.0 governs and a
reconciliation amendment is required.

---

*End of PL-1.0. Status: PROPOSED. On ratification, the PREDAIOT Product
Language is contract, not preference — consistent and sustainable across every
future screen, not a series of per-screen improvements.*
