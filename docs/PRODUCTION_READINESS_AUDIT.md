# PREDAIOT — Production Readiness Audit

**Independent technical audit.** Conducted as an external review, not by the
author of the code. Every score is **earned by measured evidence** — test
counts, coverage %, arch-graph coupling numbers, specific `file:line` findings —
never by feel. This is a deliberate constraint: PREDAIOT enforces a
No-Fabrication rule on its own engine, and this audit holds itself to the same
standard. An audit that returns only 9s is theatre; where a domain is weak, it
is scored weak.

- **Audited commit:** `14066b7` (main / production).
- **Audit opened:** 2026-07-23.
- **Method:** static analysis + full test-suite execution + coverage
  instrumentation + architecture-graph check + manual source review, domain by
  domain. Scores are assigned to a domain ONLY after its deep read is complete;
  until then it is marked `PENDING`.
- **Scoring rubric (objective anchors, not vibes):**
  - **9.5–10** — measured excellence, no material finding.
  - **9.0–9.4** — strong, only minor/cosmetic findings.
  - **8.0–8.9** — solid, 1–2 medium findings with clear remediation.
  - **7.0–7.9** — acceptable but with a real gap that must be scheduled.
  - **< 7.0** — a gap that blocks the relevant readiness gate.

---

## 0. Objective baseline (measured 2026-07-23)

These are raw measurements, reproducible by anyone with the repo. They are the
foundation every domain score is argued from.

| Metric | Value | Tool / how measured |
|---|---|---|
| Backend app code | **8,627 LOC**, 62 `.py` files | `find backend/app -name '*.py'` |
| Test code | **2,229 LOC**, 29 files, **142 test fns / 205 cases** | `pytest --co` |
| Test result | **205 / 205 PASS** (0 fail, 0 error) | `python -m pytest -q` |
| **Line coverage** | **75.5%** (3,711 stmts, 908 missed) | `pytest --cov=app` |
| Frontend code | **6,270 LOC** (`.jsx`/`.js`) | `find frontend/src` |
| Architecture layering | **violations=0, peers=0** | `tools/arch_graph.py --check` |
| Knowledge packs | 15 YAML | `find app/knowledge/packs` |
| Largest module | `api/audit.py` **841 LOC** | `wc -l` |
| TODO/FIXME/HACK/XXX in code | **0** | `grep` |
| Hardcoded secret defaults | **0** (all via env) | `grep` |
| Frontend XSS surface (`dangerouslySetInnerHTML`/`innerHTML`/`eval`) | **0** | `grep` |
| CORS | explicit `ALLOWED_ORIGINS` env allowlist (not `*`) | `main.py:152-162` |
| Broad `except` | 32 total; **4 silent `pass`** (all benign fallbacks) | `grep` |
| SQL string interpolation | 2 f-strings — internal table names only, **to verify whitelisted** | `health.py:116`, `main.py:231` |

---

## GATE REVIEW (2026-07-23) — "What could prevent the first commercial pilot?"

Breadth-first triage across all 12 domains. **No fixes, no scores** — only
classification of what stands between PREDAIOT and a successful first paying
pilot. Every item carries its evidence.

### Scope assumption (MUST be confirmed — it changes the classification)

First pilot = **Offline Economic Decision Audit for one industrial facility**
(upload file → executive report → signed certificate → PDF). Per the ratified
roadmap, **Live/Real-Time is NOT part of pilot-1** (the Industrial Live Decision
Engine is a separate post-pilot project). Under this scope, the Live storage-core
debt (TD-001) is an *Observation*, not a blocker. **If pilot-1 does sell Live,
TD-001 jumps to High Risk.**

### Config facts to confirm (not derivable from the repo — they gate the tiers)

1. **Pilot surface = offline audit only?** (Yes → TD-001 stays an Observation.)
2. **Is `ANTHROPIC_API_KEY` set in prod?** (Yes → H2 cost-abuse is *active*; No → latent.)
3. **Does the managed Postgres have automated backups + what plan/retention?**
   (No backups → H4 becomes a Launch Blocker: a pilot's data loss is unrecoverable.)
4. **Are the ED25519 certificates shown to customers/investors as proof?**
   (Yes → H1 unauth cert-mint becomes a Launch Blocker.)

### Launch Blockers

**None confirmed *active* in code** for the offline-audit surface — the core
run/report endpoints are auth-gated + rate-limited, tenant isolation holds
(every read filters `org_id == user.org_id`, `records.py:38-159`), prod runs a
**persistent Postgres** with `auth_secret_configured: true`,
`cert_signing_key: valid` (`/health/db`), and CI gates every push. The blockers
below are **conditional** on the 4 config answers above (H1, H2, H4).

### High Risk

- **H1 · Unauthenticated certificate minting.** `POST /api/v1/certificate`
  (`certificates.py:39`) takes client-supplied numbers and returns a certificate,
  **no auth, no rate limit**. If it ED25519-signs (cert key is configured in
  prod), anyone can mint a validly-signed "PREDAIOT-certified" result for
  fabricated figures — this destroys the trust artifact the whole sale rests on.
  → **Launch Blocker if certificates are used as external proof (confirm #4).**
- **H2 · Unauthenticated paid-LLM endpoint.** `POST /api/v1/ai-enhance`
  (`audit.py:817`) — **no auth, no rate limit**, calls the Anthropic API.
  Uncapped financial-DoS: a script can run your model bill to infinity.
  Active if `ANTHROPIC_API_KEY` is set in prod (confirm #2).
- **H3 · Auth secret fails open.** `_AUTH_SECRET = os.environ.get(
  "PREDAIOT_AUTH_SECRET", "")` (`security.py:17`) — if the env var is ever unset,
  the app **boots and signs/verifies JWTs with an empty string** (forgeable by
  anyone) instead of refusing to start. Prod has it set today (latent), but there
  is no fail-closed guard — one misconfig = silent full auth bypass.
- **H4 · Database backup / DR unverified.** `render.yaml` points at an existing
  managed Postgres with no visible backup policy. Prod holds real data (17
  audits, 15 certs, 22 users). If the managed PG plan has no automated backups,
  a pilot's data loss is unrecoverable. → **Launch Blocker if no backups (confirm #3).**

### Medium Risk

- **M1 · Unauthenticated file-parse endpoint.** `POST /api/v1/audit/inspect`
  (`audit.py:629`) — no auth, **no rate limit**; parses uploaded files (CPU/mem).
  Compute-abuse surface.
- **M2 · Ephemeral share links.** `POST /api/share` (`legacy.py:46`) stores full
  audit data in an **in-process dict** — links die on every restart/redeploy and
  break under >1 instance; unauthenticated. Confirm it is still used, else it is
  dead code to remove.
- **M3 · Migration strategy is hybrid.** Startup does `create_all()` +
  ad-hoc `ALTER TABLE ADD COLUMN` + `alembic stamp head` **without running
  `upgrade`** (`main.py:206-258`). Additive columns work; any non-additive change
  (rename/type/drop/data migration) is unmanaged and risky against live prod data.
- **M4 · Two-number trust gap (Daily vs TOU).** The manager's "which number is
  right?" question (product risk). Latent today (TOU not wired) but surfaces the
  moment both reports exist. Tracked as TD-003.
- **M5 · Critical-path coverage unproven.** 75.5% overall is good, but the CI
  floor is only 64% and it is not yet shown that the *engine / economics /
  validation* paths are the covered ones vs boilerplate.

### Low Risk

- **L1 ·** 4 silent `except: pass` (`logging.py:27`, `formats.py:249`,
  `timestamps.py:125`, `report_service.py:339`) — the 2 ingestion swallows could
  mask parse degradation.
- **L2 ·** `api/audit.py` at 841 LOC — orchestration hotspot; maintainability, not
  correctness.
- **L3 ·** 2 SQL f-strings interpolate internal table names (`health.py:116`,
  `main.py:231`) — confirm the sources are fixed whitelists (they appear to be).

### Observations (not pilot risks)

- **O1 ·** TD-001 Live storage-core — out of pilot scope if pilot = offline audit.
- **O2 ·** Single Render instance (no HA) — acceptable for one pilot.
- **O3 ·** TD-002 / TD-003 (load-report framing, TOU endpoint) — deferred features.
- **O4 ·** Strong CI already present (`ci.yml`): pytest + coverage floor, Ruff,
  Bandit SAST, pip-audit CVE scan, arch-graph fitness, Docker build.

### The dominant theme

Four of the six top risks (H1, H2, M1, M2) are the **same class**: a cluster of
prototype-era endpoints (`/certificate`, `/ai-enhance`, `/audit/inspect`,
`/api/share`) that never received the auth + rate-limit treatment the core audit
routes did. This is a **coherent, bounded remediation**, not a systemic rewrite.

### Reprioritized deep-audit order (by pilot business impact, not chapter order)

1. **D2 Security** — FIRST. The highest-density pilot risks live here
   (H1/H2/H3 + M1/M2). This is the gate between "safe for a paying customer" and not.
2. **D3 Infrastructure + D11 Deployment** — H4 (backups/DR) + M3 (migrations):
   protecting a paying customer's data.
3. **D6 Business Logic + D7 Mathematical + D9 Financial** — *confirmatory* pass
   (already strongly evidenced: Muscat reproduces the manual, energy conservation
   holds, 205 tests green). Lighter, not first.
4. **D10 Executive UX** — M4 two-number trust gap + the business-language finish.
5. **D1 Architecture · D5 Performance · D8 Industrial** — strong or lower
   pilot-impact; later.
6. **D12 Investor DD** — final roll-up.

**Gate status: HOLD for owner approval + the 4 config confirmations before deep
audits begin.**

---

## Scorecard (fills in as each domain's deep read completes)

| # | Domain | Status | Score |
|---|---|---|---|
| 1 | Software Architecture | PRELIMINARY | (pending deep read) |
| 2 | Security | PRELIMINARY | (pending deep read) |
| 3 | Infrastructure | PENDING | — |
| 4 | Code Quality | PRELIMINARY | (pending deep read) |
| 5 | Performance | PENDING | — |
| 6 | Business Logic | PENDING | — |
| 7 | Mathematical Validation | PENDING | — |
| 8 | Industrial Engineering | PENDING | — |
| 9 | Financial Model | PENDING | — |
| 10 | Executive UX | PENDING | — |
| 11 | Deployment Readiness | PENDING | — |
| 12 | Investor Due Diligence (roll-up) | PENDING | — |
| — | **Pilot Readiness** | PENDING | — |
| — | **Enterprise Readiness** | PENDING | — |

---

## Preliminary domain notes (from the baseline pass — NOT final scores)

### D1 · Software Architecture — PRELIMINARY: strong
- **Evidence for:** `arch_graph --check` reports **0 layering violations, 0 peer
  cycles** — the `api → services → domain → repositories → core → models`
  dependency direction is machine-enforced, not aspirational. Monolith was
  refactored out of a single `main.py` into typed layers.
- **Watch:** `api/audit.py` at **841 LOC** is a coupling hotspot (orchestrates
  ingestion + classification + units + calc + validation + certificate). Deep
  read will assess whether it violates SRP or is acceptable orchestration.
- *Deep read pending: coupling/cohesion per module, SOLID at the service
  boundaries, dead code, duplicate logic.*

### D2 · Security — PRELIMINARY: strong, one thing to verify
- **Evidence for:** 0 hardcoded secrets, CORS env-allowlisted, JWT+bcrypt
  self-owned auth, rate limiting + security headers + API access log present
  (prior sprints), facility-scoped RBAC matrix, encrypted trial email at rest,
  hash-chained security audit log.
- **To verify (deep read):** the 2 SQL f-strings (`health.py:116`, `main.py:231`)
  interpolate a `table` variable — confirm the source is a fixed internal
  whitelist (almost certainly is), else it's an injection finding. AuthN/AuthZ
  enforcement on every mutating route. Secret handling in prod (Render env).

### D4 · Code Quality — PRELIMINARY: solid
- **Evidence for:** **75.5% line coverage** with a **fully green 205-case
  suite**; **0 TODO/FIXME** debt markers; golden/identity tests freeze the
  knowledge packs, report baseline, crypto signature, and route inventory.
- **Findings (minor):** 4 silent `except: pass` (logging setup, format +
  timestamp parse fallbacks, optional QR) — all have a primary path, but the 2
  ingestion swallows could mask parse degradation; recommend logging at debug.
  Coverage at 75.5% is good-not-great — deep read will identify which *critical*
  paths (engine, economics, validation) are under-covered vs boilerplate.

---

## The 12 audits — plan & evidence sources

1. **Software Architecture** — arch_graph, per-module coupling/cohesion, SOLID,
   DDD boundaries, dependency direction, dead code, duplicate logic.
2. **Security** — authN/authZ on every route, RBAC matrix, JWT lifetime/secret,
   injection (SQL/template), SSRF in connectors, rate limits, secrets, audit trail.
3. **Infrastructure** — Docker, Render config, Postgres, migrations strategy,
   backup/DR, health checks, monitoring/logging, scalability limits.
4. **Code Quality** — coverage by *critical path*, lint/static analysis, typing,
   complexity of hotspots (`audit.py`), test taxonomy (unit/integration/golden).
5. **Performance** — audit latency vs data size, MILP solve time, N+1 queries,
   frontend bundle/Lighthouse, cold-start.
6. **Business Logic** — the four archetypes, classification correctness, edge
   cases (empty/negative/NaN/unit chaos), the four "laws".
7. **Mathematical Validation** — engine formulas vs Reference Manual, energy
   conservation (Σopt=Σact), DQ/EDE/ELR identities, currency/units, determinism.
8. **Industrial Engineering** — physics realism (EAF/BESS/solar), flexibility
   factor semantics, kWh↔MW, TOU bands vs a real tariff.
9. **Financial Model** — EDV/ceiling/gap/annualization defensibility, No-Fab
   guard, currency provenance, the "5-minute CFO defense" test.
10. **Executive UX** — every screen answers a registered executive question,
    business-language pass, error states, mobile.
11. **Deployment Readiness** — CI, rollback, env parity, zero-downtime, the
    deploy/verify loop, secrets rotation.
12. **Investor Due Diligence** — roll-up: moat, code-as-asset, key-person risk,
    what a Siemens-grade acquirer would flag.

**Sequence:** 1 → 4 → 7 → 6 → 8 → 9 (the technical/mathematical core first,
since the whole value prop rests on it), then 2 → 3 → 11 (production surface),
then 5 → 10 (performance + experience), then 12 (roll-up). TOU-as-primary-engine
is scheduled as an *outcome* of D7/D8/D9, not as a standalone feature.

## Remediation Log (Production-Readiness mode — fix → deploy → verify on prod → evidence)

### FIX #1 — `security(prod-readiness #1)` · commit `f280960` · DEPLOYED & VERIFIED 2026-07-23
Closes Gate-Review **H2** and **M1** (the unauthenticated endpoint surface, part 1).
- **Change:** `POST /api/v1/ai-enhance` → now `require_trial_or_user` + `10/min`
  (was unauth + unthrottled calling the paid Anthropic API). `POST /api/v1/audit/inspect`
  → `20/min` (kept unauth by design — harmless preview + a regression test depends on it).
  `audit.py` only; no engine/logic change.
- **Evidence — local:** full suite **205 passed**, `arch_graph --check` **violations=0**.
- **Evidence — prod (`f280960` live, `/version`+`/health/db` = 200):**
  - **H2:** `curl -X POST /api/v1/ai-enhance` (no token) → **HTTP 401**
    `{"code":"trial_token_missing"}` — rejected *before* reaching the paid API. ✅
  - **M1:** single prod `/audit/inspect` → **HTTP 200** (works); deterministic local
    hammer → calls 1-20 `200`, calls 21-24 **`429`** (limiter fires at 20/min). ✅
- **Residual (deferred to later fixes in this cluster):** `POST /api/v1/certificate`
  (H1, unauth cert-mint) and `POST /api/share` (M2, in-memory) still open — next.

### FIX #2 — `security(prod-readiness #2)` · commit `0e40643` · DEPLOYED & VERIFIED 2026-07-23
Closes Gate-Review **H1** (unauthenticated certificate minting).
- **Proof it was dead code:** frontend only GETs (`App.jsx:3096`); no internal caller;
  no test POSTs to it. The endpoint ran client-supplied numbers through
  `_register_certificate`, which Ed25519-**signs** + **persists** a `CertificateRecord`
  that the public `/certificate/verify/{id}` reports as `VERIFIED`.
- **Change:** deleted `POST /api/v1/certificate` + its dead `AuditResponse` import +
  removed from the frozen route inventory. Legit `GET /api/v1/certificate` stays —
  auth-gated + token-scoped to the caller's own latest audit (no manual numbers path).
- **Evidence — local:** full suite **205 passed**; `arch_graph` **violations=0**.
- **Evidence — prod (`0e40643` live):**
  - `POST /api/v1/certificate` → **HTTP 405 Method Not Allowed** (minter removed). ✅
  - `GET /api/v1/certificate` no-token → **401**; bogus-token → **401** (token-scoped). ✅
  - No regression: `/certificate/verify/{id}` 404-for-unknown, `/metrics/registry` 200,
    `/health/db` 200, `/version` 200. ✅

### PARITY VERIFICATION (owner items 3-6) — 2026-07-23, prod `0e40643`
Verification only (no code change). Objective evidence:
- **Item 3 · Live/code parity — ✅.** prod `/version` git_commit == `origin/main`
  (local HEAD ahead only by this doc). Frontend is rebuilt from source in the
  Docker multi-stage image, so it cannot drift; confirmed the prod bundle
  (`/assets/index-DSCreY_K.js`) contains the latest `Maximum Economic Opportunity`
  labels (×2). **Prod = the dev branch.**
- **Item 4 · Assets / Facilities / Knowledge Packs — ✅ with a scope finding.**
  15 packs are bundled in the image (`Dockerfile` `COPY backend/`) and LOAD in
  prod: a live `/audit/inspect` of steel data resolved `consumption_kwh→actual_charge`,
  `timestamp→hour`, and auto-corrected `530950 kW → MW`. **HONEST FINDING: Steel is
  the ONLY authored industry pack.** Recognition packs = steel, steel_operational,
  nameplate_electrical (generic), tou_band_billing (generic), legacy_signal_aliases
  (generic); patterns = battery/solar/EAF (for Live). **No Cement / Water / Mining /
  Food recognition packs exist.** The universal engine WOULD audit such data as a
  generic LOAD, but without industry-specific recognition. → For the Muscat **Steel**
  pilot this is exactly right; a non-steel client needs pack authoring first (that is
  a *feature* via the Knowledge-Engineering workflow — out of the current
  no-new-features scope). Decision surfaced to owner.
- **Item 5 · Real-Time paths — ✅.** All live endpoints wired + properly gated in
  prod: `GET /live/state` 401, `POST /live/ingest` 401, `GET /reconciliations` 401
  (unauth), `GET /reconciliations/verify` 200 (public by design).
- **Item 6 · Muscat Steel e2e — ✅ (engine parity) / authed full-run pending owner.**
  Prod recognizes the real Muscat signal (inspect proof above). Engine is frozen +
  deterministic at `0e40643`, the commit where `test_muscat_reference` (94,597 /
  DQ 0.91 / ALP 378,389) passes in the 205-green suite → prod produces the same
  numbers. A full authed report-run on prod needs a token (would create a funnel
  lead) — offered to owner as: he runs it in the live UI, or authorizes a throwaway
  trial token.

### FIX #3 — `security(prod-readiness #3)` · commit `c64f457` · DEPLOYED & VERIFIED 2026-07-23
Closes Gate-Review **H3** (auth secret fail-open).
- **Root cause (corrected from initial Gate note):** a missing `PREDAIOT_AUTH_SECRET`
  did not sign with `""` — it fell back to `sha256("predaiot-dev-" + abspath(__file__))`.
  On the fixed container image that path is constant → the fallback secret is publicly
  **derivable** → forgeable JWTs if the env var ever went missing.
- **Change:** `security.py` now resolves the secret via `_resolve_auth_secret(environ)`
  which **fails closed** — if no explicit secret AND a Postgres `DATABASE_URL` is set, it
  raises at startup instead of using the derivable fallback. Dev/test keeps the fallback.
  Gated on PRESENCE only (never length) so a set-but-short secret can never crash a deploy.
- **Evidence — local:** 3 new deterministic tests (prod-without-secret raises;
  dev-without-secret falls back; explicit secret authoritative). Full suite **208 passed**;
  `arch_graph` **violations=0**.
- **Evidence — prod (`c64f457` live):** app boots healthy WITH the guard —
  `/health/db` `auth_secret_configured: true`, `status: connected`, HTTP 200; `/version`
  200. Guard doesn't trip (secret is set) → zero regression. ✅

---

## Status snapshot (2026-07-23)

**Pilot target = Steel (owner-confirmed).** The Steel-only pack reality is acceptable for
the pilot; non-steel would need Knowledge-Pack authoring (a feature, deferred).

| Gate item | State |
|---|---|
| H1 unauth cert-mint | ✅ FIXED (Fix #2, `0e40643`) |
| H2 unauth paid-LLM | ✅ FIXED (Fix #1, `f280960`) |
| H3 auth-secret fail-open | ✅ FIXED (Fix #3, `c64f457`) |
| H4 DB backup/DR | ✅ CLEARED (owner-confirmed backups ON) |
| M1 unauth inspect throttle | ✅ FIXED (Fix #1) |
| Parity (items 3/5) + Live/RT | ✅ VERIFIED |
| Item 6 Muscat live full-run | ⏳ owner runs in UI; I verify the number |
| M2 `/api/share` in-memory | ⬜ queued |
| M3 hybrid migrations | ⬜ queued |
| M4 two-number (Daily/TOU) UX | ⬜ queued (product) |
| M5 critical-path coverage | ⬜ queued (measure engine/economics/validation) |
| L1 silent excepts · L2 audit.py size · L3 SQL f-strings | ⬜ low |
