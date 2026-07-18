# ADR 0004 — File-size budget (≤300–400 lines)

**Status:** Accepted

## Context
Large files are a maintainability and review-quality risk and hide poor
boundaries. A 50-engineer org reviews small, single-responsibility modules.

## Decision
No module should exceed ~300–400 lines unless there is a documented
architectural justification (e.g. `models/tables.py` at 402 L holds 17 cohesive
ORM tables). This budget drives boundary decisions: the audit hub is split three
ways (`services/ingestion.py`, `domain/economics.py`, `services/audit_service.py`)
rather than one ~900-line file. `tools/arch_graph.py` reports the largest module
per package so drift is visible.

## Consequences
- Smaller review surface; clearer ownership; forces early folder splits (Rule 3).
- Justified exceptions are explicit, not accidental.

## Alternatives
- No limit (rejected: monoliths re-form).
