# PREDAIOT — Independent Technical Due-Diligence Review

**Reviewer stance:** independent Principal Software Architect, pre-acquisition
technical DD (~$10M). Evidence-based, adversarial, quantified. **No claim here is
taken on trust — every finding cites a measured artifact** (radon, ruff, bandit,
`arch_graph`, git, file inspection). Where my assessment diverges from the team's
own optimistic self-rating (8.8/10), the divergence is stated and justified.

**Date:** 2026-07-19 · **Commit:** `ed44820` (Phase 3 complete) · **Branch:** `main`

---

## 0. Executive summary

PREDAIOT is a genuinely differentiated product — a frozen, cryptographically
certified economic-audit engine with an exceptional *behavioural* test discipline
(golden fingerprint + digital-twin + Ed25519 compatibility gating every commit).
That is a real moat and a rare thing to find in a company this size.

It is **not yet an enterprise-grade platform**, and the gap is honest and
*documented by the team itself* (15-item debt log). The three things that would
sink a naive "9/10" claim under real DD:

1. **Horizontal scaling is architecturally blocked today** (in-process singletons /
   live WebSocket state — debt D7). This is a single-instance app wearing a
   multi-tenant SaaS costume.
2. **`main.py` is still a 2,385-line, 56-route monolith** with a maintainability
   index of **0.00** and a route handler at cyclomatic complexity **F(52)**.
3. **Supply chain is unpinned** — 11 of 16 core dependencies have no version and
   there is no lockfile; builds are not reproducible.

None of these are fatal, all are on a credible roadmap, and the refactor now
underway is exactly right. My honest composite is **6.8/10 (68/100)** —
"fundable and productionised, not yet enterprise-hardened."

---

## 1. Clean Architecture / layering

**Evidence:** `tools/arch_graph.py` → 28 modules, **0 upward/circular violations, 0
peer edges**; enforced direction `api → services → domain → {core, utils, models,
schemas}`.

| Strength | Weakness |
|---|---|
| Machine-checked dependency direction (a *fitness function*, not a doc) | No `repositories/` layer — 40 raw `SessionLocal()` sites live in route bodies (D5/D11) |
| First `domain/` module (`economics.py`) extracted; economic findings isolated | No `infrastructure/` layer — SMTP/urlopen/PDF/JWT still scattered |
| Verbatim, behaviour-preserving extraction with golden-fingerprint gate | `api/` layer doesn't exist yet — 56 routes remain in `main.py` (D8) |
| ADRs (5) + living debt log document every compromise | Domain is 1 module; business rules still split with `eda_metrics.py` (D4) |

The **direction** is textbook; the **completeness** is early. The fitness function
is the single most impressive artifact in the repo — most Series-A codebases have
nothing comparable. **Score: 7.5/10.**

## 2. ISO/IEC 25010 quality characteristics

| Characteristic | Grade | Evidence |
|---|---|---|
| Functional suitability | **A** | Frozen engine, golden 188.62 byte-identical, 222+ twin scenarios, No-Fabrication purge |
| Reliability | **A−** | 149-test gate + twin determinism OK; but single-instance, no HA, no health SLO |
| Performance efficiency | **B−** | 16.8 s @ 4,032 rows within budget; but sync compute in request path, no queue, no horizontal scale |
| Maintainability | **C+** | Extracted modules all radon-A; `main.py` MI **0.00**; FE `App.jsx` 2,998 L |
| Security | **B** | Strong fundamentals (§4); gaps in secret hard-fail, token revocation, SAST |
| Portability | **B** | Env-driven config, SQLite↔Postgres, on-prem-friendly (no external IdP); no Docker in CI |
| Compatibility | **B+** | Clean REST + OpenAPI; parallel Node/MILP engines cross-validated |
| Usability (product) | **B+** | FE 2.0 design system, AA pass, Lighthouse 95+ (team-reported) |

## 3. SaaS architecture

- **Multi-tenancy:** org-scoped — **32 `org_id == user.org_id` filters**, 404 across
  org boundaries (verified on decisions/audits). Real tenant isolation, and the
  security smoke proves A/B separation (PASS 11/FAIL 0).
- **Scaling blocker (🔴 D7):** `_latest_by_token`, `_BOOT_ID`, live WebSocket state,
  and the rate limiter are **in-process module globals**. Two instances behind a load
  balancer would serve inconsistent live/cache state. **This is the #1 SaaS gap** —
  the app is multi-tenant but not multi-instance.
- No per-tenant rate quotas, no usage metering, no tenant-level config/feature flags.

**Score: 6/10** (isolation good, elasticity absent).

## 4. Security (OWASP Top-10 / ASVS / NIST)

**Scanned:** bandit (`main.py`, `eda_metrics`, `app`) → **0 HIGH**, 3 MEDIUM.

| Area | Finding | Sev |
|---|---|---|
| A01 Broken Access Control | Org-scoping consistently applied (32 sites); RBAC roles (6) defined | ✅ good |
| A02 Crypto | Ed25519 cert signing (deterministic), bcrypt, encryption-at-rest (DataProtector), SHA-256 hash-chain audit log | ✅ strong |
| A03 Injection | 2× `B608` string-interpolated DDL (`main.py:437, 2747`) — **hardcoded identifiers, NOT user input → not exploitable**, but violates parameterization discipline & trips SAST | 🟠 MED |
| A05 Misconfig | JWT secret **dev-fallback derives from file path** and only *warns* — production that forgets `PREDAIOT_AUTH_SECRET` silently runs on a weak secret | 🟠 MED |
| A07 Auth | Login/register rate-limited (10/min, 5/min); **no token revocation / rotation** — a stolen 24 h JWT can't be killed | 🟠 MED |
| A10 SSRF | `B310` urlopen (lead push) — low risk if endpoint hardcoded; confirm no user-controlled URL | 🟡 LOW |
| Secrets mgmt | **No secrets committed** (git-tracked scan clean), env-var driven; but no vault/secrets-manager | 🟡 LOW |
| Supply chain | **No SAST/DAST/dependency-scan in CI**; deps unpinned (§6) | 🟠 MED |

Fundamentals are **above** the median Series-A SaaS. The stale internal note that
"IDOR isn't done" is **inaccurate** — object-level authz *is* enforced. Real gaps
are operational-security maturity (secret hard-fail, revocation, SAST), not broken
access control. **Score: 7/10.** ASVS L1 largely met; L2 has clear gaps.

## 5. Code quality

- **radon CC average = B (5.53)** across the backend — healthy. Hotspots: route
  `audit_from_file` **F(52)**, `process_calculation` E(40), `_build_audit_pdf` E(38),
  `_parse_file_bytes_raw` E(37), `_build_ai_commentary` D(29).
- **ruff = 62 issues**: 52 `F401` unused-import (extraction cruft, auto-fixable),
  3 unused-var, minor style. No functional bugs surfaced.
- **67 `except` clauses in `main.py`**, several `except Exception: continue/pass`
  (silent swallowing — e.g. gap-attribution, migration introspection). Acceptable for
  "enrichment never fatal" but hides failures without structured logging.
- Docstrings on extracted modules are **excellent** (Purpose/Deps/Direction/Used-By).
- **No black, no isort, no mypy config** committed; type hints partial.

**Score: 6.5/10.**

## 6. Python engineering / dependencies

- 🔴 **Unpinned deps + no lockfile:** `requirements.txt` pins only 5 of 16 (psycopg2,
  PyJWT, bcrypt, alembic, cryptography); **fastapi, uvicorn, sqlalchemy, pandas,
  pulp, reportlab, pypdf, rapidfuzz, slowapi, openpyxl, pg8000 are floating.** Builds
  are not reproducible; a transitive bump can break prod or introduce a CVE silently.
  **Highest-ROI single fix in this report.**
- Redundant DB drivers: both `pg8000` and `psycopg2-binary` present.
- Runtime pinned to Python 3.12.6 in CI (matches Render) — good.
- Graceful optional-dep degradation (lxml/pyarrow/paho lazy-imported → 503 with
  install hint) — a nice production touch.

**Score: 6/10** (code is fine; dependency governance is the drag).

## 7. React / frontend

- `App.jsx` = **2,998 lines** (67% of a 4,477-LOC, 20-file frontend). A monolith of
  the same class `main.py` was — **not yet refactored** (FE decomposition is a later
  phase).
- Design system exists and is good: `design/tokens.css`, `design/components.jsx`,
  `instruments/charts.jsx`, workspace tiering. FE 2.0 spec, AA accessibility, and
  Lighthouse 95+ are team-reported.
- No component tests / no Storybook / no visual regression evident.

**Score: 6/10** (strong design system, undecomposed shell).

## 8. API design

- 56 REST endpoints + WebSocket live stream, FastAPI → **auto OpenAPI/Swagger** ✅,
  Pydantic request/response validation ✅, consistent `{code, message}` error envelope
  on core routes ✅, `/api/v1` prefix.
- Gaps: single monolithic router (no `APIRouter` split), list endpoints use a
  hardcoded `limit(200)` (no cursor pagination), no ETag/idempotency keys, no explicit
  API deprecation policy.

**Score: 7.5/10.**

## 9. Database

- Postgres (Render, pooled: `pool_size=5, max_overflow=10, pre_ping, recycle=300`) ✅;
  SQLite for dev.
- **Alembic chain 0001→0010** present and coherent ✅ (17 ORM models).
- 🟠 **Dual migration mechanism:** Alembic *and* `_apply_additive_migrations()` running
  ad-hoc `ALTER TABLE` DDL at startup. Two sources of schema truth — reconcile.
- No repository abstraction (raw sessions in routes, D5/D11).
- 🟡 `predaiot_audit.db` is **git-tracked** despite `*.db` in `.gitignore` (added before
  the rule) — remove from tracking.

**Score: 7/10.**

## 10. Performance & scalability

- Compute within budget (MILP 16.8 s @ 4,032 rows; hourly day 0.4 s). Connection
  pooling + rate limiting in place.
- 🔴 **Synchronous heavy compute in the request path** (`process_calculation` runs the
  MILP inline) — no task queue / async offload for large audits; a big upload blocks a
  worker.
- 🔴 **In-process state (D7)** caps you at one instance — see §3.
- No caching layer, no CDN strategy for the API, no load/soak testing evidence beyond
  the twin perf harness.

**Score: 6/10.**

## 11. Enterprise readiness

| Have | Missing |
|---|---|
| Multi-tenant org isolation, 6-role RBAC | Structured logging / metrics / tracing (D13 — print-based) |
| Cryptographic audit certificates + hash-chain log | Horizontal scale / HA (D7) |
| Alembic migrations, encryption-at-rest | Secrets manager (env vars only) |
| Functional CI gate | SAST/DAST/coverage/Docker/IaC in CI (D10) |
| Living architecture debt log (rare & excellent) | SLO/alerting/on-call runbook |

**Score: 6.5/10.**

## 12. Technical debt

**Exceptionally well-governed** — `ARCHITECTURE_DEBT.md` tracks D1–D15 with Reason ·
Risk · Removal Phase · Owner. This transparency is worth real money in DD: it turns
unknown risk into scheduled work. Headline open items: D7 (singletons 🔴), D8 (routes
🟠), D4/D11 (domain/repositories 🟠), D13 (observability 🟠), D10 (SAST/DAST 🟠).
**Score (debt management, not debt level): 9/10.**

## 13. Refactoring opportunities (prioritised by ROI)

1. **Pin every dependency + add a lockfile** (hours; removes an entire class of
   prod/CVE risk). *Do this first.*
2. **Externalise in-process state to Redis (D7)** — unblocks horizontal scale; the
   single highest-value architectural fix.
3. **Wire `arch_graph --check`, ruff, bandit, pip-audit, coverage into CI** (the
   fitness function already exists — just gate on it). Auto-fix the 52 unused imports.
4. **Split `main.py` into `api/` routers (D8)** — targets the 0.00 MI and F(52) hotspot.
5. **Introduce a `repositories/` layer** — remove 40 raw sessions from routes.
6. **Structured logging + OpenTelemetry (D13)** — replace 67 print/except-swallow sites.
7. **Reconcile dual migrations**; remove tracked `.db`; decompose `App.jsx`.

## 14. Final scores

| Dimension | /10 |
|---|---|
| Architecture & layering | 7.5 |
| Maintainability | 7.0 |
| Security | 7.0 |
| Code quality | 6.5 |
| Testing & validation | 7.5 |
| Database | 7.0 |
| API design | 7.5 |
| Performance & scalability | 6.0 |
| Frontend | 6.0 |
| DevOps / CI-CD | 5.5 |
| Observability | 4.0 |
| Enterprise readiness | 6.5 |
| Debt governance | 9.0 |
| **Composite (weighted)** | **6.8 / 10 → 68 / 100** |

*Weighting favours scalability, security, and maintainability (acquirer-relevant)
over debt-governance. The team's 8.8 self-rating over-credits the excellent
*direction*; my 6.8 marks the current *state*. Both are defensible — the delta is
"roadmap vs. reality."*

## 15. Verdicts

| Question | Verdict | Basis |
|---|---|---|
| **Production-ready?** | ✅ **YES** (single-instance) | Deployed, byte-identical, test-gated; serving real audits |
| **Enterprise-ready?** | 🟠 **PARTIAL** | Multi-tenant + RBAC + audit ✅; observability + HA + SAST ❌ |
| **ISO 25010-aligned?** | 🟠 **PARTIAL** | Strong Functional/Reliability; Maintainability + Performance weak |
| **Cyber-ready (ASVS)?** | 🟠 **L1 yes, L2 gaps** | Authz/crypto/rate-limit ✅; secret hard-fail, revocation, SAST ❌ |
| **Investor-ready?** | ✅ **YES (seed/Series-A)** | Real moat (engine + certs + validation rigor), debt tracked & roadmapped |
| **SaaS-scale-ready?** | 🔴 **NO (yet)** | D7 in-process state blocks horizontal scaling — the gating item |

**Bottom line for an acquirer:** buy the **engine, the certification IP, and the
test discipline** — they are the durable assets and are excellent. Price in ~2–3
engineer-quarters to reach true multi-instance SaaS + enterprise ops (D7, D8, CI
hardening, observability). The debt is real but **quantified, contained, and
scheduled** — which is the best thing you can say about technical debt in a DD.
