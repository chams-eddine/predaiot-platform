# Repository Architecture Review — pre-implementation gate (step 7)

**Status: AWAITING RATIFICATION.** No further repository is implemented until this
document is reviewed. Objective test for every choice herein: does it make a
Siemens / Schneider / Honeywell / acquisition-DD committee **more confident**?

**Evidence date:** 2026-07-20 · commit `9efbad3`+ · measurement tool:
[`tools/bench_seclog.py`](../tools/bench_seclog.py) (committed, reproducible).

---

## 0. Findings classification (fact vs. recommendation)

| # | Finding | Classification | Evidence |
|---|---|---|---|
| F1 | `_persist_audit_record` executes **3 separate commits** (audit.py:84, :102, :120) | **Verified defect** | code |
| F2 | Partial persistence is reachable **and the request still returns 200** (caller wraps in `except Exception` at audit.py:497→500, swallowed) | **Verified defect** | code |
| F3 | Security-log **append race forks the hash chain**: 8 threads × 25 appends → **7 duplicate `prev_hash`, `chain_valid=False`, zero errors raised** (silent corruption) | **Verified defect** (reproduced in-process; see reachability note §3) | measured |
| F4 | `/security/log/verify` is O(n) full-scan: **272 ms @ 10K, 1.69 s @ 50K, 3.02 s @ 100K** rows → linear ⇒ **~34 s @ 1M, ~340 s @ 10M**, per request, unauthenticated, entire table in RAM | **Verified (measured to 100K) + extrapolated concern beyond** | measured |
| F5 | `_security_log` opens a **second DB session inside request flows that already hold one** → 2 connections/request vs pool 5+10 | **Verified fact; impact = future concern** (needs load measurement) | code |
| F6 | Repositories return **live ORM entities** across the boundary (lazy-navigation + mutate-on-commit possible) | **Verified fact; risk = architectural recommendation** (DTOs later) | code |
| F7 | Repositories constructed **inline in handlers** → not substitutable without monkeypatching; testability claim unrealized | **Verified fact; fix scheduled** (Composition Root, step 8) | code |
| F8 | Planned `audit_repo` / `decision_repo` split **cuts the audit aggregate** (one transaction writes all three) | **Architectural recommendation** (fix the plan; see §1) | code-derived |
| F9 | `DOMAIN_BY_INTENT` allowlist masks the physical `domain→services` edge in the fitness tool | **Verified fact → converted to temporary debt D20 with removal milestone** | code |
| F10 | Hash-chain computation (integrity rule) lives inside the repository, contradicting the layer's "data access only" doctrine | **Doctrine inconsistency** — resolved by amending the doctrine (integrity-adjacent persistence allowed, documented) rather than pretending | code |
| F11 | org_id / created_at indexes exist on all hot tables | **Verified fact (positive)** — composite `(org_id, created_at)` is a future optimization, not a defect | code |

Race reachability today (§F3): all current `_security_log` callers are `async def`
handlers on one event loop with no awaits inside the helper ⇒ serialized **in the
current single-worker deployment**. The defect becomes live the day any of: a sync
route calls it (threadpool), `--workers > 1`, or a second instance. Since
multi-instance is the roadmap's explicit destination, this is a defect, not a
hypothetical.

## 1. Aggregate Map (derived from transactions + invariants in code, not theory)

| Aggregate | Root | Members (one consistency unit) | Evidence |
|---|---|---|---|
| **Audit** | `AuditRecord` | `EconomicState`, initial `Decision` rows (materialization) | written in ONE unit by `_persist_audit_record`; decisions must reference the audit + ES version |
| **Decision lifecycle** | `Decision` | `DecisionEvent`, `Outcome`, `GovernanceRecord` | transition/outcome/governance flows mutate these together; reference audits by id only |
| **Identity** | `Organization` | `User` (org-scoped), `TrialLead` (funnel identity) | register creates Org+User in one unit; every access check joins them |
| **Live stream** | stream (`stream_id`) | `LiveEvent` window, `LiveState`, `Reconciliation` | reconcile writes state+reconciliation over one stream's window |
| **Certificate** | `CertificateRecord` | (self-contained; content-addressed id) | issued/verified independently; refs audit by hash only |
| **Security log** | append-only chain | `SecurityAuditLog` | trivial aggregate; the chain IS the invariant |
| *(infra, not an aggregate)* | — | `APIAccessLog` | forensic stream, no invariants |

**Repository boundaries recommended from the map** (supersedes the table-based plan):

| Repository | Owns | Explicitly NOT |
|---|---|---|
| `audit_repo` | AuditRecord + EconomicState + decision materialization + reads for records.py | decision lifecycle |
| `decision_lifecycle_repo` | Decision mutations, DecisionEvent, Outcome, GovernanceRecord | audit creation |
| `identity_repo` | Organization, User, TrialLead | — |
| `live_repo` | LiveEvent, LiveState, Reconciliation | — |
| `certificate_repo` | CertificateRecord | — |
| `security_log` (done) | SecurityAuditLog | — |
| `access_log` (with middleware later) | APIAccessLog | — |

`asset_repo` folds into `identity_repo`? **No** — Asset is org-scoped registry data
with its own lifecycle; keep `asset_repo` separate (7th entry). Small is fine.

## 2. Transaction boundaries & commit ownership

- **Rule (unchanged):** repositories NEVER commit; the session owner commits.
- **Current owner:** HTTP handlers (API layer) — correct only as a transitional
  state; consistency semantics do not belong in route functions.
- **Target owner:** application services via session-per-request injected at the
  Composition Root (step 8). One request = one session = (by default) one commit.
- **Critical Integrity Debt (ADR 0006):** F1/F2 — the audit-persistence unit must
  become ONE transaction (single commit; `_security_log` after commit). This is a
  deliberate BEHAVIOUR CHANGE (windows removed) and therefore is scheduled work
  with its own test, not a silent refactor: **milestone = step 7 completion,
  before the phase deploy.**

## 3. Dependency graph (honest version)

Machine-checked (`arch_graph --check`, CI): `api(5) → services(4) → domain(3) →
repositories(2) → core(1) → models/schemas(0)`; 44 modules; 0 upward/circular/peer
**within its scope**. Outside its scope, disclosed: `main.py` (composition root)
is not scanned; intra-package edges are invisible; `DOMAIN_BY_INTENT` masks one
physical `domain→services` edge → **D20, temporary, removal milestone = first DDD
slice (move `_dispatch_mode`/`_classify_decision` into `domain/`, delete the
allowlist)**. Until D20 closes, "0 violations" claims MUST carry this footnote.

## 4. ORM leakage analysis

All repository methods return live SQLAlchemy entities; handlers serialize
manually. Risks: lazy-load queries after the repo call (hidden N+1), attribute
mutation + accidental flush, schema coupling of every consumer. **Decision:**
accepted for the transitional layer (verbatim rule); DTO/row-mapping becomes part
of the Ports & Adapters step — a port that returns ORM rows is not a port.
Tracked as D21 (must close before step 9 claims "Ports").

## 5. Repository responsibility matrix

| Concern | Repository | Service | Domain | API |
|---|---|---|---|---|
| Query construction / persistence | **✔** | — | — | — |
| Commit / transaction scope | — | **✔ (target; API today)** | — | (today) |
| Integrity-adjacent persistence (hash-chain append) | **✔ (doctrine amended, F10)** | — | — | — |
| Chain/graph VERIFICATION presentation | — | — | — | **✔** |
| Economic rules | — | — | **✔** | — |
| DTO mapping (future) | boundary of ✔ | — | — | — |

## 6. Migration path → Ports & Adapters (no work starts now; order is binding)

1. **Step 7 (remaining):** repositories per §1 map + fix F1/F2 (atomic audit
   persist) + fix F3 (serialized append: `UNIQUE(prev_hash)` constraint + retry,
   works on Postgres AND SQLite) + F4 mitigation (incremental verify watermark or
   rate-limit + cap). Battery gates every slice.
2. **Step 8 (Composition Root):** session-per-request; repositories injected
   (closes F7); commit ownership moves out of handlers.
3. **Step 9 (Ports):** lift interfaces from repository signatures; introduce DTOs
   at the boundary (closes D21); adapters (Postgres/SQLite today, others on need).
4. **DDD phase:** aggregates become domain objects; repositories return them.

## 7. Explicit status

This repository layer is a **transitional extraction** (ADR 0007), not a
production-grade boundary. Production-grade requires closing: F1/F2 (atomicity),
F3 (append race), F4 (verify strategy), F7 (injectability). Nothing else blocks.
