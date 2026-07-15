# PREDAIOT Editorial System — ED-1.0

**Status:** PROPOSED — awaiting ratification. Normative annex of PL-1.0 (the
style manual). Governs how PREDAIOT *writes* — tone, sentence, number, unit,
order, and per-surface copy. Where LR-1.0 fixes *which* words are allowed,
ED-1.0 fixes *how* they are composed.
**Derives from:** SPEC-ST (narrative), SPEC-DL (hierarchy), SPEC-HM (executive
cognition), SPEC-ID (typography/financial), SPEC-AI (recommendation voice),
SPEC-QA Q9 (basis). Backend frozen; every number binds to an API field.

---

## 1. Voice & tone

The voice is a **senior risk officer briefing the board**: calm, precise,
declarative, slightly austere, never excited.

- **Declarative, not conversational.** "Execution gap: 6,710.39 USD." Never
  "Let's look at the execution gap…".
- **No exclamation marks. No hedging. No hype.** Banned: "!", "massive",
  "huge", "amazing", "significant" (as filler), "could potentially".
- **No anthropomorphism.** The platform *states* and *records*; it never
  "thinks", "feels", "found", or apologizes. Machine output is impersonal
  ("PREDAIOT Recommendation", not "I recommend").
- **Active, specific verbs.** "captured", "leaked", "attributed", "verified" —
  not "was impacted", "saw", "experienced".
- **Confidence without bravado.** State findings plainly and stop; do not
  oversell, do not add AI disclaimers.

## 2. Sentence & structure

- **Answer-first (pyramid).** Every screen and every zone opens with its
  conclusion; support follows. The reader must be able to stop after the first
  line and be correct.
- **Standfirst ≤ ~14 words**, one clause, states the act's question or claim.
- **Body: one thought per line**; prose measure ≤ **72ch** (`--pds-prose-max`).
- **Micro-copy (labels, kickers): 1–4 words.** Kickers are noun phrases, not
  sentences.
- **No paragraph exceeds four lines** on an answer surface; evidence tables may
  be denser (PL-DEN).

## 3. Numbers

- **One formatter.** All money flows through the single institutional
  formatter (`ds.js` `fmtMoney`); no ad-hoc `toLocaleString`/`toFixed`/`$`.
- **Grouping:** en-US thousands (`7,038.75`), never locale-variant
  (`7 038,75`). All numerals are **mono** (`.pds-num`, tabular-nums).
- **Money precision:** full 2-decimal precision at the *primary* mention of a
  figure; compact `B / M / K` (2/2/1 dp) at *secondary* mentions.
- **Percentages:** 1 decimal for headline (`94.9%`), 0 decimals for dense
  legends (`95%`).
- **Currency:** the code (USD, OMR) sits beside the numeral in text-2 weight;
  never a bare `$` for a non-USD currency; symbol-only is not used for
  identity-critical figures.
- **Negatives / loss:** carry the loss color, never parentheses; a leakage
  figure is shown as a positive magnitude in the loss color, framed by words
  ("value left unrealized"), not as `-N`.
- **Grades:** letter + optional `· {n}%` (`Grade B · 82%`); `INDETERMINATE`
  spelled in full, neutral slate.
- **Hashes/IDs:** mono, truncated to ~10–18 chars + `…`, with copy-full.

## 4. Units & time

- **Energy:** `MW`, `MWh`, `MW/step`; **price:** `{currency}/MWh`.
- **Period:** name the audited period exactly once per screen using
  `audit_period_label` (e.g., "288 Steps (24h)"); do not echo it in every zone.
- **Timestamps:** `HH:MM` for intra-day steps; ISO date for audit dates; never
  raw epoch or serial.
- **No invented units** or precision the API did not provide.

## 5. Order (the hierarchy, in words)

Within any screen and any block, information appears in this order
(SPEC-DL, inviolable):

> **Money → Risk → Opportunity → Decision → Evidence → Details.**

Editorially: **standfirst (question) → dominant figure (answer) → one support
sentence → proof → fine print.** Never invert; details never precede the
answer they support. Non-monetary reference screens open with the Economic
Context Strip so money still leads.

## 6. Capitalization & typographic copy

- **Kickers / group labels:** ALL-CAPS microcaps with wide tracking
  (`.pds-kicker`), 1–4 words.
- **Titles / asset names:** Title Case, no ALL-CAPS sentences.
- **Body:** sentence case.
- **Verdict words** (Severe risk, CERTIFIED, INDETERMINATE): as registered in
  LR-1.0 — risk bands Title Case in prose, provenance/confidence states in
  caps as chips.
- **™** appears once per proper product name per screen (Executive Briefing™
  usage), not on every mention.
- **No decorative glyphs or emoji** in copy (LR-1.0 §7).

## 7. Per-surface copy patterns (templates)

Canonical templates every wave reuses. `{}` = API-bound value.

- **Standfirst:** `{ACT/SECTION KICKER}` + right-aligned question
  ("What is our current economic reality?").
- **Headline figure:** the dominant numeral + currency; framed by one
  sentence naming its value class ("value left unrealized").
- **KPI/label:** `{NOUN PHRASE, 1–4 WORDS}` over a mono figure over an optional
  one-line basis.
- **Evidence line:** `Evidence · {opportunities[].evidence}` (verbatim engine
  text).
- **Confidence line:** `Confidence · Audit Confidence {grade} · {n}%` — or
  `Confidence · INDETERMINATE — data-quality index not computed on this audit
  path` when absent.
- **Method footnote:** `Method · {derivation}` in fine print below a rule.
- **Recommendation (SPEC-AI):** `PREDAIOT Recommendation` + `{name}` +
  `{description}`; worth and proof in the following act.
- **Empty state:** what is absent + the single action —
  "No audit loaded. Run a demo or upload dispatch data."
- **Loading:** engine phrase — "Optimizing against the hindsight benchmark…";
  never "Please wait" or a bare spinner.
- **Error (PL-ER):** `UNABLE TO COMPLETE` + what failed + the recovery path,
  dismissible in place.
- **Notice (PL-SU/NT):** `DONE` + the factual confirmation, auto-clearing.

## 8. The basis-disclosure rule (mandatory)

Any figure that could be read as forward-looking — a per-period recoverable or
gain — carries, verbatim in class:

> "Basis: recorded period only — no forward projection."

The words "annualised / annual / per-year / projected / forecast / will" are
banned from any surface stating an economic figure (LR-1.0 §5). Q9
(cost-of-waiting) is always recorded-rate framing.

## 9. Forbidden editorial patterns

Cross-references LR-1.0 §5 and §7: no exclamation, no hype, no
anthropomorphism, no emoji/dingbats, no forward projections, no fabricated
constants, no bare `$` non-USD, no parenthesized-negative money, no
ALL-CAPS sentences, no marketing CTAs inside the workspace.

## 10. Acceptance (copy review)

Every screen passes a copy review against ED-1.0 as part of the Language Gate
(PL-1.0 §2): voice, sentence length, one-formatter numbers, unit correctness,
order, basis disclosure, and zero forbidden patterns. A copy failure blocks
ship exactly like a truth failure.

---

*End of ED-1.0. How PREDAIOT writes: answer-first, recorded-truth, one number,
a risk officer's calm — the same on every page.*
