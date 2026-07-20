# Architecture Decision Records (ADRs)

Every significant architectural decision is recorded here (Rule 5). One file per
decision, immutable once accepted; superseding decisions get a new ADR that
references the old one.

**Format:** `NNNN-title.md` with sections — Status · Context · Decision ·
Consequences · Alternatives.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-layered-architecture.md) | Layered architecture + dependency direction | Accepted |
| [0002](0002-behavior-preserving-refactor.md) | Behaviour-preserving structural refactor (Phase 3); Structural Domain now, DDD in P6 | Accepted |
| [0003](0003-economic-engine-frozen.md) | Economic engine frozen + characterization-test gate | Accepted |
| [0004](0004-file-size-budget.md) | File-size budget (≤300–400 lines) | Accepted |
| [0005](0005-ingestion-package-split.md) | Ingestion decomposed into a cohesive package | Accepted |
| [0006](0006-critical-integrity-debt-audit-persistence.md) | Critical Integrity Debt: non-atomic audit persistence | Accepted |
| [0007](0007-transitional-repository-layer.md) | Repository layer is transitional, not a production boundary | Accepted |
