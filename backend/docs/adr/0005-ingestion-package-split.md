# ADR 0005 — Ingestion decomposed into a cohesive package

**Status:** Accepted

## Context
Phase-3 service 5 part 1 extracted the ingestion + data-quality cluster from
`main.py` into a single `app/services/ingestion.py` (VERBATIM). That module was
1,015 lines — ~2.5× the ADR 0004 file-size budget — so the budget breach was
recorded and a boundary review scheduled before continuing to `domain/economics.py`.

The call-graph analysis showed five natural responsibility groups (file decoding,
column resolution, timestamp handling, value normalisation, data-quality
assessment) with only 7 cross-group references, all funnelling into two shared
leaf helpers (`_dq`, `_normalise_col`).

## Decision
Split `ingestion.py` into a **package** `app/services/ingestion/` of cohesive
submodules, each ≤ ~265 lines (under the 0004 budget):

- `_primitives.py` — shared leaves `_normalise_col`, `_dq` (package leaf, no
  intra-package deps)
- `columns.py` — alias tables + fuzzy column resolution → `_primitives`
- `timestamps.py` — detect/parse/resample/dedupe timestamps → `_primitives`
- `values.py` — units + numeric coercion + display-currency → `_primitives`
- `quality.py` — sensor-quality flags, DQ counts, DQI, forecast reliability → `_primitives`
- `formats.py` — raw bytes → DataFrame + banner repair → `_primitives`, `columns`

The internal dependency graph is acyclic and one-directional:
`formats → columns → _primitives` and `{timestamps, values, quality} → _primitives`.

`__init__.py` re-exports the exact public surface `main.py` imports, so the
import-back line (`from app.services.ingestion import …`) is **unchanged**. The
moves are structural/verbatim — no redesign, no new abstractions (consistent with
ADR 0002; Structural Domain now, DDD in P6).

All submodules are services-tier, so `tools/arch_graph.py` (which records only
cross-layer edges) reports the intra-package imports as neither violations nor
peers: `--check` stays `violations=0 peers=0`.

## Consequences
- Six single-responsibility modules under budget; the 0004 breach is resolved.
- Public API and behaviour unchanged — full battery byte-identical after the split
  (golden 188.62 / 288 decisions; cert `EDPC-947D2AD6D76B8B30` + Ed25519; PDF
  `pdf_size 562731` / layout `c17e4b72…`; twin 160/160, determinism OK, same 2 I5
  residuals; perf FAIL 0; security PASS 11 / FAIL 0; pytest 149 passed).
- Each submodule carries the shared import header (some imports unused-but-`# noqa`);
  lint-driven trimming deferred to the Production Safety Phase (ruff). Tracked as D14.

## Alternatives
- **Two-way parsing/quality split** (rejected: parsing half stays ~800 L, still 2× budget).
- **Keep single 1,015-line file with a documented exception** (rejected: 2.5× budget is
  a far weaker justification than `models/tables.py` at 402 L, and defers the debt).
