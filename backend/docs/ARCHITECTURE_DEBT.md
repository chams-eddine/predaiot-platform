# PREDAIOT — Architecture Debt Log

> **Policy:** never hide technical debt — track it. Every deliberate compromise made
> during the modularization is recorded here with **Reason · Risk · Removal Phase ·
> Owner**. This is a living document; DD reviewers should read it first.
>
> Target end-state (drives every "Removal Phase" below):
> `app/{api, services, domain/{optimization,dispatch,storage,economics}, telemetry,
> certificates, reporting, repositories, workers, events, schemas, models, core,
> infrastructure}` + `tests/` + `docs/`.
> Dependency direction (allowed only): **API → Application Services → Domain →
> Repositories → Infrastructure**. No upward, no circular, no peer-to-peer.

Legend — Risk: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low.

| # | Debt | Risk | Reason (why now) | Removal phase | Owner |
|---|------|:---:|------|------|------|
| D1 | **Flat `app/services/*.py`** instead of domain packages | 🟢 | Incremental behaviour-preserving refactor; big-bang re-layout is riskier on a live system | **P6 DDD** — promote to `domain/`, `optimization/`, `reporting/`, `certificates/`, `telemetry/` | Architecture |
| D2 | **`_classify_decision` + `_dispatch_mode` (economic taxonomies) live in `optimization_service`** | 🟢 | Shared domain logic on the economic leaf (domain-by-intent in `arch_graph`) so audit+telemetry+`domain/economics` depend downward without a peer edge; `domain/economics` imports `_dispatch_mode` from here | **P6** → move both into `domain/` alongside `economics.py`; the physical `domain→services` edge then disappears | Economics |
| D3 | **`_MILP_LAST` mutable module-global** (last-solve status) | 🟡 | Verbatim extraction preserved existing behaviour; read by ingestion to disclose time-limited solves | **P4/P9** — make request-scoped (blocks clean multi-instance disclosure) | Economics |
| D4 | **Economic rules split across `services` + `eda_metrics`** (DQ, leakage, root-cause, opportunity, optimization) — not a single Domain layer | 🟠 | Rules are currently where they were written; moving them is the DDD step, not an extraction step | **P6** — consolidate into `domain/` (business rules must not live in api/routers/pdf/telemetry) | Economics |
| D5 | **DB access inside services** (`certificate_service`/`audit_service` call `SessionLocal`, `_register_certificate` writes rows) | 🟠 | Verbatim extraction kept the existing persistence pattern | **P?/repositories** — persistence moves to a `repositories/` layer; services orchestrate, domain computes, infra stores | Backend |
| D5b | **`_security_log` (writes SecurityAuditLog) in `core/logging`** | 🟢 | Needed a shared home below cert+main; core.logging already owns audit-log writes | **P9** → `infrastructure/` or a security repository | Security |
| D6 | **Ledger-CSV built inline in the route handler** (not in `report_service`) | 🟢 | It's endpoint code; moves with the endpoints | **P5 Routers** → `report_service` | Reporting |
| D7 | **In-process state / singletons in `main.py`** (`_latest_by_token`, `_BOOT_ID`, `limiter`, live WS state) | 🔴 | Existing runtime behaviour; not touched during structural extraction | **P4/P9** — externalize to Redis; **blocks horizontal scaling today** | Infrastructure |
| D8 | **`main.py` ~3.0k lines** (55 routes still inline; static mount must stay last) | 🟠 | Routers phase not started; extraction order was core→models→schemas→services first | **P5 Routers** → `api/` `APIRouter`s; `main.py` → ~200-line bootstrap | Architecture |
| D9 | **`core/versions.py` imports `pulp`** (for `SOLVER_VERSION`) | 🟢 | `SOLVER_VERSION = pulp.__version__` needs the lib | **P9** — inject via config/build metadata | Infrastructure |
| D10 | **No CI-enforced SAST/DAST/coverage gate / IaC** (functional CI only) | 🟠 | Test gate exists; static-analysis + Docker gates are the next phase | **Production Safety Phase** — ruff/black/mypy/bandit/pip-audit/coverage/Docker | DevEx |
| D11 | **No repository/domain/infrastructure layers yet**; services still mix orchestration + persistence + rules | 🟠 | Current phase is service extraction, not layering | **P6** | Architecture |
| D12 | **`_LETTERHEAD_PATH` `__file__` resolution adjusted** (only non-verbatim line in Phase 3) | 🟢 | Module moved; path re-resolved to the same asset (output proven byte-identical) | **P9** — asset path via config/infrastructure | Reporting |
| D13 | **No structured logging / metrics / tracing / correlation IDs** (print-based) | 🟠 | Not introduced during behaviour-preserving extraction | **P8 Observability** — OpenTelemetry-ready structured logging | DevEx |
| D14 | **Ingestion submodules carry the full shared import header** (some imports unused-but-`# noqa: F401`) | 🟢 | Structural split kept a uniform header to avoid a missing-import regression; the battery is the safety net, not per-file import surgery | **Production Safety Phase** — ruff auto-removes unused imports | DevEx |
| D15 | **`domain/economics.py` is 451 L** (51 over the ADR-0004 budget) | 🟢 | Cohesive economic-findings set moved VERBATIM (incl. the ~110-line narrative builder `_build_ai_commentary` and rich No-Fabrication derivation comments); splitting mid-Phase-3 would be redesign, not extraction | **P6 DDD** — split findings (`root_cause`/`opportunity`/`heat_map`/`eda_metrics`) from narrative (`ai_commentary`) as value objects emerge | Economics |

## Resolved debt (kept for DD traceability)
- **Ingestion 1,015-line budget breach** (service 5 part 1) — RESOLVED by splitting
  `services/ingestion.py` into the cohesive package `services/ingestion/` (6 submodules
  ≤ 265 L), see [ADR 0005](adr/0005-ingestion-package-split.md). Public surface and
  output byte-identical.

## Invariants held throughout (NOT debt — guardrails)
- Economic engine **byte-for-byte frozen** — golden Ibri2 fingerprint identical at every commit.
- Cryptography frozen — cert id / SHA-256 / Ed25519 signature byte-identical; historical certs still verify.
- PDF output frozen — layout hash + `pdf_size` + ledger CSV byte-identical (timestamps normalized, documented).
- No API/route/schema/DB/output change. Every step gated by the committed pytest suite + golden + twin + perf + security battery.

_Last updated: Phase 3 COMPLETE — service 5 part 3 (`audit_service.py` orchestrator). All 5 services extracted; `main.py` at 2,385 L (from 6,157)._
