# ADR 0001 — Layered architecture + dependency direction

**Status:** Accepted

## Context
PREDAIOT began as a ~6,200-line `main.py` monolith. It must become an
enterprise SaaS platform maintainable by a large team and defensible in
technical due diligence.

## Decision
Adopt a strict layered architecture with one allowed dependency direction:
`api → services → domain → repositories → infrastructure`, with `models`/`schemas`
as innermost entities and `core`/`utils` as foundation (anyone may import them
downward). No upward imports, no circular imports, no peer-to-peer service
imports. See `docs/DEPENDENCY_RULES.md`; enforced by `tools/arch_graph.py --check`.

## Consequences
- Clear ownership boundaries; testable in isolation; multi-team friendly.
- Requires shared logic to live in the correct layer (domain/core), not sideways.
- CI gate prevents architectural erosion over time.

## Alternatives
- Flat modules (rejected: no ownership, erodes under many contributors).
- Full hexagonal/ports-and-adapters now (deferred: too large a leap for a live
  system; P6+ evolves toward it).
