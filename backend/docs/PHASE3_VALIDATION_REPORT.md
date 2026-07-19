# PREDAIOT — Phase 3 Final Validation Report

**Scope:** Behaviour-preserving structural extraction of the FastAPI monolith
(`backend/main.py`) into a layered/domain architecture. **Economic engine, MILP
optimization, DQ/leakage math, cryptography, and PDF/CSV outputs are frozen** —
this phase moved code, it did not change behaviour.

**Verdict:** ✅ **COMPLETE — all 5 services extracted, every gate green, output
byte-for-byte identical to the pre-phase baseline.**

---

## 1. Services extracted (5/5)

| # | Service | Layer | Commit | Notes |
|---|---------|-------|--------|-------|
| 1 | `optimization_service` | services (domain-by-intent) | `5bd8d62` | MILP dispatch optimizers + `_classify_decision`, `_dispatch_mode` (economic leaf) |
| 2 | `certificate_service` | services | `289e7f1` | Ed25519 build/register/verify, canonical JSON |
| 3 | `report_service` | services | `f92053b` | PDF audit report + letterhead + ledger CSV |
| 4 | `telemetry_service` | services | `160101c` | live decision core |
| 5 | **audit-hub** | services + **domain** | `6d21650`,`e84b2e0`,`ef4921b`,`b321add` | ingestion package + `domain/economics` + `audit_service` orchestrator |

Audit-hub split (as directed): `services/ingestion/` (6-module package) +
`domain/economics.py` (first domain-layer module) + `services/audit_service.py`
(orchestrator only).

## 2. `main.py` reduction

| Milestone | Lines |
|---|--:|
| Refactor start | **6,157** |
| After Phase 2 (core/models/schemas) | ~4,400 |
| After service 4 (telemetry) | ~3,426 |
| After ingestion (pt 1) | 2,999 |
| After economics (pt 2) | 2,612 |
| **After audit_service (pt 3) — Phase 3 end** | **2,385** |

Net: **−3,772 lines (−61%)**. Remaining `main.py` = 55 route handlers + bootstrap
+ startup/migration (Routers phase P5 target → ~200-line bootstrap; debt D8).

## 3. Package map (auto-generated, `tools/arch_graph.py`)

| Layer | Files | LOC | Largest module |
|---|--:|--:|---|
| services | 13 | 2,498 | `report_service` (354 L) |
| domain | 2 | 462 | `economics` (451 L — D15) |
| core | 7 | 360 | `dependencies` (153 L) |
| models | 2 | 411 | `tables` (402 L) |
| schemas | 1 | 266 | `schemas` (266 L) |
| utils | 2 | 27 | `formatting` (27 L) |

**28 modules scanned.**

## 4. Dependency graph — before / after

- **Before:** one 6,157-line module; no enforceable direction.
- **After:** strict layering, machine-checked every commit —
  `api → services → domain → {core, utils, models, schemas}`.

```
core --> models
domain --> schemas
domain --> utils
services --> core
services --> domain
services --> models
services --> schemas
services --> utils
```

**`arch_graph.py --check`: hard violations = 0, peer edges = 0** (upward &
circular imports are a CI-failing condition).

## 5. Behaviour-preservation evidence (final commit `b321add`)

| Gate | Baseline | Phase-3 end | Result |
|---|---|---|---|
| pytest characterization | 149 | **149 passed** | ✅ |
| Golden Ibri2 `total_gap` | 188.62 | **188.62** | ✅ identical |
| Golden shape | 288 dec / 3 RC / 6 opp / A·A / Severe | same | ✅ identical |
| Certificate id | `EDPC-947D2AD6D76B8B30` | same | ✅ identical |
| Ed25519 signature | `iAKrPHk…DXBA==` | same | ✅ byte-identical |
| Determinism (2× audit) | all fields True | **all True** | ✅ |
| PDF `pdf_size` | 562,731 | **562,731** | ✅ identical |
| Ledger CSV `csv_size` | 2,006 | **2,006** | ✅ identical |
| PDF layout hash | `c17e4b72…` | same | ✅ identical |
| Twin campaign | 160/160 valid | **160/160** | ✅ |
| Twin determinism | OK | **OK** | ✅ |
| Twin fault coverage | 24/24 | **24/24** | ✅ |
| Twin residuals | S0095, S0107 (I5) | **same 2** | ✅ baseline-matched |
| Performance | within budget | **FAIL 0** (≤ 16.8 s @ 4,032 rows) | ✅ |
| Security | tenant isolation | **PASS 11 / FAIL 0** | ✅ |

The 2 twin "defects" (`I5_negative_gap_unflagged` on S0095/S0107) are the
**pre-existing documented residuals** recorded in `twin_report.json` before Phase 3
— identical scenario IDs, sectors, fault combos, and flagged invariant. Not
regressions.

## 6. Governance produced

- **5 ADRs** (`docs/adr/`): layered architecture, behaviour-preserving refactor,
  frozen engine + test gate, file-size budget, ingestion package split.
- **Architecture fitness function** (`tools/arch_graph.py`) with `--check` for CI.
- **Living debt log** (`ARCHITECTURE_DEBT.md`) — D1–D15, each with Reason · Risk ·
  Removal Phase · Owner. **Nothing hidden.**
- **Auto-generated** dependency graph + package metrics (`ARCHITECTURE.md`).
- **Dependency rules** (`DEPENDENCY_RULES.md`).

## 7. Tech-debt movement

| | Start of Phase 3 | End of Phase 3 |
|---|---|---|
| Largest module | 6,157 L (`main.py`) | 451 L (`domain/economics.py`) |
| Layers with enforced direction | 0 | 6 |
| Machine-checked import rules | none | `--check` 0/0 |
| Domain layer | none | created (`domain/economics.py`) |
| Documented debt items | ad-hoc | 15 tracked (D1–D15) |

Debt **resolved** this phase: ingestion 1,015-line budget breach (→ package, ADR 0005).
Debt **added/updated**: D14 (ingestion import trim → ruff), D15 (economics 451 L → P6 split),
D2 (extended: `_dispatch_mode` now imported by `domain/economics`).

## 8. Rollback strategy

- Every service is **one small commit**; `git revert <sha>` restores the prior
  state without touching any other extraction.
- Import-back pattern means each revert is self-contained (the moved code returns
  to `main.py`; entrypoint `main:app` never changed).
- The golden fingerprint + twin baseline are the **objective rollback trigger**: any
  future change that alters `188.62` / cert id / `pdf_size` / the 2 residuals is
  rejected before merge.
- No DB migration, no API/route/schema change across the entire phase → rollback is
  code-only, zero data risk.

## 9. Residual risk (carried forward — see debt log)

- 🔴 **D7** in-process singletons (`_latest_by_token`, live WS state) block
  horizontal scaling — **P4/P9** (externalize to Redis).
- 🟠 **D8** `main.py` still holds 55 routes — **P5 Routers**.
- 🟠 **D4/D11** economic rules not yet consolidated into a pure Domain; **D5**
  persistence still in services — **P6 DDD / repositories**.
- 🟠 **D10** no CI SAST/DAST/coverage gate — **Production Safety Phase**.
- 🟠 **D13** print-based logging, no tracing — **P8 Observability**.

---

_All Phase-3 commits are on `main` (local). Deploy is a single step at phase end,
gated on the evidence in §5._
