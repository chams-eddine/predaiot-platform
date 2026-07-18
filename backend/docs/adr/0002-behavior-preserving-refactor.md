# ADR 0002 — Behaviour-preserving structural refactor (Phase 3)

**Status:** Accepted

## Context
The platform is live in production. Restructuring risks changing behaviour of a
revenue system whose economic outputs and certificates must remain trustworthy.

## Decision
Phase 3 is **structural moves only** — verbatim extraction, no redesign, no new
abstractions, no renames/merges/splits of business logic. `app/domain/` is
created now as **Structural Domain** (the new physical location of existing
economic-rule functions), NOT a redesigned Domain Model. Real DDD (entities,
value objects, aggregates, policies, repositories, domain services) is **P6**,
performed intentionally and separately.

## Consequences
- Preserves a provable guarantee: every economic rule is byte-for-byte identical
  through Phase 3 (golden fingerprint gate).
- P6 becomes a `git mv` + intentional redesign, not a rewrite.
- Two refactor concerns (structural vs. behavioural) never mix in one phase —
  easy to justify to an external reviewer.

## Alternatives
- Do DDD now (rejected: would break the behaviour-preserving guarantee and blur
  two distinct phases).
