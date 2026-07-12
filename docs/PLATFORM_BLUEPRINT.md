# PREDAIOT Platform Blueprint — Economic Decision Intelligence

Status: **GOVERNING SPECIFICATION** — ratified by the Founder on 2026-07-11.
This document is the architectural contract of PREDAIOT, not documentation.
No implementation may violate it. No shortcut may bypass the Audit Engine.
No feature may introduce an alternative source of economic truth.

**The Economic State laws.** Every new capability MUST do at least one of:

1. **Produce** an Economic State,
2. **Consume** an Economic State,
3. **Verify** an Economic State,
4. **Learn from** an Economic State.

`EconomicState` (§4a) is the canonical business object of PREDAIOT.
Everything else is supporting infrastructure. A proposed feature that does
none of the four is either commodity infrastructure (built at minimum
sufficient depth per §0) or out of scope.

**Conformance rule for every future PR/phase:** state which of the four laws
the change serves, or classify it as commodity infrastructure. A change that
can do neither is rejected.

**Amendment rule:** this specification changes only by explicit Founder
approval, recorded in this file's git history.

### Amendment 1 — Phase order resolved (Founder-approved 2026-07-12)

The prior §15 phase order (Live ingestion → Live intelligence → Decision
engine → Governance) contradicted the §0 moat filter (Decision Intelligence =
MOAT, first; Live ingestion = COMMODITY, deferred). The contradiction is
resolved in favour of §0. The **canonical build order** is now:

1. Economic Audit (L2) — *done, immutable*
2. Economic Memory (L3) — *done (Sprint 2)*
3. **Economic State (`EDA-ES-1.0`)** — the canonical business object, built
   **first after Economic Memory**, materialised from stored audits (batch).
4. **Decision Intelligence (`EDA-DEC-1.0`)** — *consumes* Economic State.
5. **Economic Governance (`EDA-GOV-1.0`)** — *verifies* Decision Intelligence.
6. **Live Streaming** — an **update source for Economic State**, NOT an
   independent capability. Live windows produce/refresh Economic States
   through the *same* EDA-ES-1.0 definition; they never introduce a parallel
   truth. (OPC-UA/MQTT/edge remain COMMODITY, built thin, pulled in only when
   a live-feed pilot requires them.)

Rule of consumption (the resolved dependency chain):

    Economic Audit → Economic State → Decision Intelligence → Governance
                          ↑
                   Live Streaming (update source only)

Identity invariant (never violated by any phase):

    Certified Economic Audit  →  Decision Intelligence  →  Live Economic Governance

The Audit Engine (Layer 2) is the source of truth and is IMMUTABLE in semantics:
DQI, AEI/Audit Confidence, EDA methodology, certificates, evidence chain,
Ed25519 verification, and the no-fabrication rule are never weakened by any
layer above them. Real-time features EXTEND the audit; they never bypass it.

---

## 0. Design filter (governs every decision below)

Every component is classified before it is built:

> **"Does this increase PREDAIOT's Economic Decision Intelligence, or is it
> only generic enterprise software?"**

- **COMMODITY** → simplest robust implementation, preferably managed/bought,
  minimum code, zero invention. Auth, RBAC plumbing, Postgres, queues, MQTT,
  OPC-UA client libs, monitoring, backups, CI. These are table stakes; they
  can lose a deal but can never win one.
- **MOAT** → maximum engineering effort, versioned like the EDA metrics,
  reproducible, evidence-backed. The five pillars: **Economic Audit ·
  Economic State · Decision Intelligence · Evidence Chain · Economic
  Governance.**

Classification of the blueprint:

| Component | Class | Consequence |
|---|---|---|
| Auth / SSO / MFA | COMMODITY | managed IdP; zero bespoke auth code |
| RBAC | COMMODITY | one role column + one FastAPI dependency; no policy engine |
| Postgres / Alembic / backups | COMMODITY | managed Render PG + PITR + pg_dump |
| Ingest queue | COMMODITY | Postgres-as-queue; upgrade only at measured load |
| MQTT / OPC-UA / Modbus | COMMODITY | standard libraries; agent is thin |
| Monitoring / CI | COMMODITY | Sentry + uptime probe + GH Actions; Prometheus deferred |
| On-prem bundle | COMMODITY | deferred until a signed contract requires it |
| L2 Audit Engine | **MOAT** | immutable; parity-gated; already theorem-grade |
| **Economic State object** | **MOAT** | first-class versioned artifact `EDA-ES-1.0` (§4a) |
| **Decision Intelligence** | **MOAT** | versioned methodology `EDA-DEC-1.0`; every card reproducible from the ledger |
| **Evidence Chain** | **MOAT** | extended upward: decisions & outcomes hash-linked to audit evidence (§5a) |
| **Economic Governance** | **MOAT** | recovered-value ledger + versioned governance metrics `EDA-GOV-1.0` |

Effort budget: ≥70% of engineering time on MOAT rows once Phase 1's commodity
floor exists. Phase 1 is deliberately commodity-heavy (it is the floor the
moat stands on) and is executed at minimum sufficient depth.

### 4a. Economic State — first-class MOAT artifact (was implicit; now specified)

`EconomicState` (versioned `EDA-ES-1.0`) is the canonical, money-denominated
state of an asset at a point/window in time — the single object L4 computes,
L5 consumes, and L6 aggregates:

```
EconomicState {
  asset_id, window_start, window_end, version: "EDA-ES-1.0",
  leakage_rate,          // currency/h, from windowed gap ledger
  recoverable_value,     // currency, execution-gap basis
  dqi, aei,              // windowed, same eda_metrics equations
  economic_health,       // derived ratio, published formula — no invented score
  provisional: bool,     // true until covered by a certified L2 audit
  evidence_sha256        // hash of the window manifest it derives from
}
```
Rules: reproducible from its window manifest exactly like DQI reproduces from
the Data Quality Manifest; N/A propagates (unknown stays unknown); a state
whose DQ gate fails is INSUFFICIENT EVIDENCE, not a number. This object — not
telemetry — is what every screen renders.

### 5a. Evidence Chain — extended upward (MOAT upgrade)

Today the chain covers dataset → audit → certificate. It is extended to the
full loop so accountability is cryptographically verifiable end-to-end:

```
dataset_sha256 → audit payload hash → certificate (Ed25519)
             └→ decision.evidence_sha256   (hash of ledger steps + derivation)
                  └→ outcome.evidence_sha256 (hash linking verifying audit)
```
Every decision card and every governance outcome carries a content hash
anchored in audit evidence. Competitors can copy a dashboard; they cannot copy
a verifiable decision-accountability chain without rebuilding the whole stack.

## 1. System architecture — six layers mapped to concrete components

```
┌─────────────────────────────────────────────────────────────────────────┐
│ L6 GOVERNANCE   Decision workflow · accountability · recovered-value    │
│                 ledger · portfolio/fleet views · executive command      │
├─────────────────────────────────────────────────────────────────────────┤
│ L5 DECISION     Decision cards (EVENT/CAUSE/IMPACT/ACTION/RECOVERY/     │
│    ENGINE       EVIDENCE/CONFIDENCE) — derived ONLY from L2 outputs     │
│                 (root-cause buckets, gap ledger, DQI/AEI)               │
├─────────────────────────────────────────────────────────────────────────┤
│ L4 LIVE ECON    Rolling micro-audits over streaming windows → live      │
│    INTELLIGENCE leakage rate, recoverable value, economic health.       │
│                 Telemetry is NEVER the primary display — money is.      │
├─────────────────────────────────────────────────────────────────────────┤
│ L3 KNOWLEDGE    Persistent asset memory: audit history, decision        │
│                 history, recurring leakage patterns, seasonality,       │
│                 asset profile. Postgres. The platform remembers.        │
├─────────────────────────────────────────────────────────────────────────┤
│ L2 AUDIT ENGINE backend/main.py audit core + eda_metrics.py + PuLP/CBC  │
│    (IMMUTABLE)  MILP + certificates + manifest + verify portal +        │
│                 milp-service/ + node-core/ parity implementations       │
├─────────────────────────────────────────────────────────────────────────┤
│ L1 DATA         File ingestion (CSV/XLSX/JSON/XML/Parquet — exists),    │
│                 MQTT bridge (exists), Edge Connector agent (OPC-UA/     │
│                 Modbus, store-and-forward), REST push API.              │
│                 PREDAIOT sits ABOVE SCADA; it never replaces it.        │
└─────────────────────────────────────────────────────────────────────────┘
```

Component inventory (current → target):

| Component | Today | Target |
|---|---|---|
| API service | FastAPI monolith `backend/main.py` | Same service, split into routers/modules (audit, ingest, decisions, governance, admin) — modular monolith, NOT microservices |
| Audit core | in main.py + eda_metrics.py | extracted `audit_core/` package, imported unchanged; smoke parity gate on every extraction commit |
| MILP | in-process PuLP/CBC (+ milp-service copy) | same; milp-service reserved for horizontal scale-out |
| DB | SQLite (ephemeral!) | **Render Postgres (persistent) — Phase 1, day 1** |
| Frontend | React SPA served by FastAPI | same + auth screens + portfolio views |
| Landing | Next.js static (separate service) | unchanged |
| Edge | none | `edge-connector/` standalone Python agent |
| Auth | trial tokens | managed IdP (Clerk or equivalent) + JWT; SAML/SSO via IdP |

## 2. Data flow

Batch (exists, primary):
```
file → /api/v1/audit/file → parse/clean (ingest notes) → dq_snapshot →
audit engine (MILP, gap ledger, attribution) → DQI/AEI + manifest →
AuditRecord (L3) → certificate (signed, registered) → PDF / dashboard / portal
```

Live (Phase 2–3):
```
SCADA/PLC → Edge Connector (OPC-UA/Modbus poll, local buffer)
          → TLS: MQTT or HTTPS batch push → ingest queue (Postgres table, v1)
          → window assembler (15-min rolling) → L4 micro-audit (same L2 math,
            windowed) → live economic state + events → L5 decision cards
          → WebSocket to dashboard (S13 extension — additive only)
```
Rule: a live window that fails DQ gates yields "INSUFFICIENT EVIDENCE — no
economic claim", never a fabricated number. Live numbers are labelled
"provisional until certified audit" — certification remains batch L2.

## 3. Database schema (Postgres, Phase 1 core)

```sql
-- Identity & tenancy
organizations(id PK, name, slug UNIQ, plan, created_at)
users(id PK, org_id FK, idp_subject UNIQ, email_encrypted, role, created_at)
  -- role ∈ {owner, admin, asset_manager, operator, finance, viewer}
api_keys(id PK, org_id FK, key_hash, scopes[], expires_at, revoked)

-- Asset registry (L3)
assets(id PK, org_id FK, name, asset_type, capacity_mw, currency,
       specs jsonb, created_at)

-- Audit history (L3) — the memory
datasets(id PK, org_id FK, asset_id FK, sha256 UNIQ, filename, rows,
         span_start, span_end, uploaded_by FK, created_at)
audits(id PK, org_id FK, asset_id FK, dataset_id FK,
       engine_version, methodology_version,
       result jsonb,             -- full AuditResponse (result of record)
       dqi numeric, dqi_grade, aei numeric, aei_grade,
       gap_total numeric, gap_recoverable numeric, currency, created_at)
certificate_registry(...existing columns..., org_id FK NULL)  -- keep; add org

-- Decision engine + governance (L5/L6)
decisions(id PK, org_id FK, asset_id FK, audit_id FK,
          methodology_version,            -- EDA-DEC-1.0
          root_cause_bucket, event_summary, cause_summary,
          impact_value numeric, impact_period, recommended_action,
          expected_recovery numeric,      -- historical avoided-loss basis ONLY
          evidence jsonb,                 -- step refs + derivation string
          evidence_sha256,                -- chain link to audit ledger (§5a)
          dqi_at_issue numeric, aei_at_issue numeric,
          status, -- proposed|accepted|rejected|delayed|superseded
          status_by FK, status_at, status_note, created_at)
decision_outcomes(id PK, decision_id FK, verified_audit_id FK,
          realized_recovery numeric, verification_note,
          evidence_sha256,                -- chain link to verifying audit (§5a)
          created_at)
  -- closed loop: Audit → Decision → Execution → Verification → Learning
economic_states(id PK, org_id FK, asset_id FK, window_id FK NULL,
          version,                        -- EDA-ES-1.0 (§4a)
          window_start, window_end, leakage_rate numeric,
          recoverable_value numeric, dqi numeric, aei numeric,
          economic_health numeric, provisional bool, evidence_sha256)

-- Live (Phase 2+)
ingest_streams(id PK, org_id FK, asset_id FK, protocol, config jsonb, status)
telemetry_windows(id PK, stream_id FK, window_start, window_end,
          payload jsonb, dq jsonb, processed bool)   -- partitioned by month
economic_events(id PK, org_id FK, asset_id FK, window_id FK, kind,
          impact_rate numeric, opened_at, closed_at, decision_id FK NULL)

-- Security & ops
security_audit_log(id PK, org_id FK NULL, actor, action, object, at,
          prev_hash, row_hash)            -- hash-chained (re-implement; was lost)
api_access_log(...existing...)
schema_migrations(version PK, applied_at)  -- Alembic
```
Row-level tenancy: every business table carries `org_id`; all queries filtered
by org from JWT claims; Postgres RLS enabled as defense-in-depth in Phase 2.

## 4. Streaming architecture (deliberately staged)

- v1 (Phase 2): **Postgres-as-queue** — `telemetry_windows` with SKIP LOCKED
  workers. Zero new infrastructure; correct at ≤ ~100 assets × 1-min data.
- v2 (scale trigger: >1k msgs/s sustained): Redis Streams or NATS; the window
  assembler interface is identical, so the swap is contained in one module.
- Kafka is explicitly NOT adopted until multi-region fleet scale demands it.
Windows are idempotent (window identity = stream_id + window_start); replays
are safe; late data re-opens a window within a 2-window grace, else flagged in
DQ manifest — never silently merged.

## 5. Edge architecture (`edge-connector/`)

Standalone Python agent (single binary via PyInstaller for Windows/Linux):
- Reads OPC-UA (asyncua) / Modbus TCP (pymodbus) / CSV drop-folder.
- Local SQLite ring buffer (72 h) — store-and-forward across outages
  (extends the existing offline-resilience requirement to the edge).
- Pushes signed batches (HMAC with per-stream key) over HTTPS or MQTT-TLS.
- Outbound-only; no inbound ports; config file + provisioning token.
- OT-network friendly: read-only on industrial protocols, DMZ deployable.

## 6. API contracts

- `/api/v1/*` frozen as-is (public verify + registry endpoints are permanent
  contracts — certificates in the field depend on them).
- New surface (additive): `/api/v1/orgs`, `/assets`, `/audits?asset_id=`,
  `/decisions` (+ `POST /decisions/{id}/status`), `/streams`, `/events`,
  `/reports/executive`.
- AuthN: `Authorization: Bearer <JWT>` (users) or `X-Api-Key` (integrations,
  scoped). Trial tokens remain only for the self-serve trial funnel.
- Versioning rule: breaking change ⇒ `/api/v2/...`; v1 verify portal never
  breaks. OpenAPI spec curated and published (auto-docs exist today).

## 7. Security model

- AuthN: managed IdP (Clerk/Auth0 class) → JWT (short-lived) + refresh;
  MFA at IdP; SAML/OIDC SSO for enterprise via IdP (no bespoke SSO code).
- AuthZ: RBAC matrix (roles above). Finance: money views/exports; Operator:
  decisions + ops views; Viewer: read-only; Admin/Owner: org + keys + users.
  Enforced server-side per router dependency, not in the frontend.
- Data: TLS in transit; Postgres encryption at rest (managed); PII (emails)
  app-layer encrypted (Fernet, key in env) — re-implements lost control;
  Ed25519 signing seed stays env-only (`PREDAIOT_CERT_SIGNING_KEY`), with
  documented key rotation + escrow procedure.
- Integrity: hash-chained `security_audit_log` (re-implement); certificate
  registry append-only (revocation flag, never deletion).
- Compliance path: SOC 2 Type I roadmap doc (task #50) → Type II after 6 mo
  of evidence; GDPR/Oman PDPL: data-processing register, deletion workflow.

## 8. Deployment topology

- Phase 1 (Render): web service (FastAPI+SPA) + **Postgres (persistent)** +
  landing (static). Same as today minus the ephemeral-DB defect.
- Phase 2+: + worker process (window assembler / micro-audits) + optional
  Redis. Edge agents on customer premises.
- Enterprise/on-prem option (OQ/PDO reality): docker-compose bundle of the
  same images — the modular monolith makes this cheap; document it, sell it.
- CI/CD: GitHub Actions — lint, unit, smoke_regression, frontend build →
  deploy hook → **post-deploy verification job** (hits /health + /metrics/
  registry + one seeded audit; alerts on mismatch). This closes the
  "production ran stale code for days" failure permanently.

## 9. Scalability strategy

Audit is CPU-bound (MILP ≤45 s cap): scale by worker fan-out (milp-service
already extracted for this). Live path is I/O-bound: window workers scale
horizontally on the queue. Postgres partitioning on telemetry_windows;
read replicas before sharding; org_id is the natural shard key if ever
needed. SLO targets: file audit p95 < 60 s; live window latency < 2× window;
dashboard TTFB < 1 s.

## 10. Disaster recovery & backup

- Postgres: Render PITR + nightly `pg_dump` to off-site object storage
  (B2/S3), 30-day retention, quarterly restore drill (documented).
- Signing key escrow: sealed offline copy; rotation procedure re-signs
  nothing (certificates carry their public key — old certs stay verifiable).
- RTO 4 h / RPO 24 h (Phase 1) → RPO 1 h with WAL archiving (Phase 3).
- The verify portal must survive DB loss: registry table included in the
  hourly backup tier from Phase 1 (it is the public trust anchor).

## 11. Multi-tenancy

Single DB, org_id row scoping + JWT claim filtering (Phase 1), Postgres RLS
(Phase 2), optional dedicated instance for sovereign customers (the on-prem
bundle covers this). No cross-org data path exists by construction: every
query passes through a tenancy dependency that injects org_id.

## 12. Monitoring & observability

- Errors: Sentry (backend + frontend).
- Uptime: external probe on /health + /api/v1/metrics/registry (catches the
  stale-deploy class).
- Metrics: /metrics (Prometheus format) — audit counts, durations, MILP
  status mix, queue depth, window lag.
- Structured JSON logs; request-id correlation; solver telemetry (_MILP_LAST)
  exported, not just cached.
- Alert routes: deploy-verify failure, error-rate spike, queue lag, cert
  signature failures.

## 13. Testing strategy

- Keep: smoke_regression, smoke_torture (40), smoke_pdf_ibri2, smoke_ws_resume
  — promoted into CI as the merge gate.
- Add: unit tests for eda_metrics (property-based: AC ≤ min(DQI,M), N/A
  exclusion, idempotency); tenancy isolation tests (org A cannot read org B —
  every new endpoint); decision-engine derivation tests (every card's numbers
  reproduce from the audit ledger); migration tests (empty → migrated schema).
- Parity gate: audit_core extraction must reproduce Ibri2 reference numbers
  (gap 188.62 OMR, DQI 98.7%, attribution 56.39+132.24) byte-for-byte.

## 14. Migration strategy (no big bang)

1. Introduce Alembic; baseline current schema.
2. Stand up Postgres; `DATABASE_URL` switch (SQLAlchemy already abstracts).
   SQLite remains the dev default. **No data migration needed — production
   data is ephemeral today (nothing to lose; that is the defect).**
3. Ship auth alongside trial tokens (dual-accept window); trial funnel stays.
4. Backfill: on first login, a trial user's token history (if still live)
   attaches to their new org.
5. Extract audit_core behind the parity gate; routers split next.
6. Verify portal URLs and certificate IDs remain stable throughout (public
   contract).

## 15. Phase gates (roadmap with exit criteria)

*(Superseded by Amendment 1 — canonical order below.)*

| Phase | Scope | Exit criteria |
|---|---|---|
| 1 Foundation | Postgres, Alembic, auth+orgs+RBAC, asset registry, audit history, security-log, deploy verification, S01 exec strip | ✅ done — login works; audits persist across deploys; org isolation passes; prod verified |
| 2 Economic Memory | audit history, replay, memory aggregates | ✅ done (Sprint 2) — org-scoped history + deterministic memory |
| 3 **Economic State (EDA-ES-1.0)** | canonical object materialised from each stored audit; versioned pure builder; `economic_states` table; endpoints; reproducible `economic_health` | every Economic State reproduces from its audit's published quantities; N/A propagates; org-scoped; on prod |
| 4 **Decision Intelligence (EDA-DEC-1.0)** | decision cards derived from Economic State + ledger; workflow (accept/reject/delay); evidence-chain hash | every card number traces to the ledger; no invented ROI; round-trips |
| 5 **Economic Governance (EDA-GOV-1.0)** | decision outcomes, recovered-value ledger; verifies Decision Intelligence | closed loop: decision → later audit verifies realised recovery |
| 6 **Live Streaming** (update source) | edge-connector (OPC-UA/Modbus), MQTT, windowed micro-audits that *refresh Economic States* via EDA-ES-1.0 | 72 h ingest, zero loss; live Economic States reproduce from windows, DQ-gated, provisional-labelled |

Constraint honored everywhere: S13 Live Monitor visuals — additive changes only.
Constraint honored everywhere: no self-serve payment (Sec 2.2) — enterprise
contracts are sales-led; billing integration deferred.
Constraint honored everywhere: L5/L6 never invent ROI — expected recovery is
always historical avoided-loss with evidence references, or absent.
