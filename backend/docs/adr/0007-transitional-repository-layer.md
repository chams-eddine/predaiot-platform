# ADR 0007 — Repository layer is TRANSITIONAL, not a production boundary

**Status:** Accepted

## Context
Step 7 introduced `app/repositories/` (session-bound repositories; caller owns
session + commit; no ABC interfaces). The architecture review
(docs/REPOSITORY_ARCHITECTURE_REVIEW.md) classified the layer's findings and
measured its hot spots (`tools/bench_seclog.py`: verify-scan 3.02 s @ 100K rows,
linear; append race reproduced — 7 chain forks under 8 threads).

## Decision
The current repository layer is explicitly a **transitional extraction**: it
organizes queries behind named seams and preserves behaviour byte-for-byte, but
it is NOT yet a production-grade architectural boundary, because:
1. F1/F2 — audit persistence is non-atomic (ADR 0006, D16);
2. F3 — security-log append race forks the hash chain under concurrency (D17);
3. F4 — public O(n) chain verification (measured; D18);
4. F7 — repositories are not injectable (closed by the Composition Root, step 8);
5. F6 — live ORM entities cross the boundary (DTOs arrive with Ports, step 9; D21).

Boundaries follow the ratified **Aggregate Map** (review §1) — aggregate-aligned,
not table-aligned; the previously planned audit/decision split (which cut the
Audit aggregate) is superseded.

## Consequences
- "Production-grade repository layer" may be claimed only when D16, D17, D18 and
  F7 are closed; the debt log carries each with severity/owner/milestone/
  verification.
- DD reviewers get an honest map instead of an overstated abstraction.

## Alternatives
- Declare the layer production-grade now (rejected: contradicted by measured
  evidence).
- Skip the transitional layer and jump to Ports+DTOs (rejected: big-bang change
  on a live system; violates the behaviour-preservation gate).
