# ADR 0006 — Critical Integrity Debt: non-atomic audit persistence

**Status:** Accepted (debt acknowledged; fix scheduled)

## Context
`_persist_audit_record` (app/api/audit.py) persists the Audit aggregate —
AuditRecord, EconomicState, materialized Decision rows — with **three separate
commits** (lines 84, 102, 120). VERIFIED from code, 2026-07-20. The caller wraps
the whole call in `except Exception` (audit.py:497→500) and the HTTP request
returns 200 regardless, so a failure between commits (connection drop, constraint
violation, process kill) leaves an audit **without** its Economic State and/or
Decisions — silently.

This predates the repository layer (verbatim-preserved through every extraction);
the repository review surfaced and classified it.

## Decision
Classified **Critical Integrity Debt** (debt log D16). The audit-persistence unit
must become ONE transaction: single commit covering all three writes, with
`_security_log` emitted after the commit. This is a deliberate, tested behaviour
change (failure windows removed), scheduled — not a silent refactor.

**Target milestone:** step 7 completion (before the phase deploy), implemented in
`audit_repo` per the ratified aggregate map.
**Verification method:** a fault-injection test that raises between writes and
asserts NO partial rows persist (all-or-nothing), plus the standard battery.

## Consequences
- Until fixed: partial audits are possible in production; reads that join
  audit→economic-state must tolerate missing children (they currently do, which
  is why the defect stayed invisible).
- After the fix: crash-consistency for the flagship persistence path; a DD
  committee reads this ADR as evidence the team finds and schedules its own
  integrity defects.

## Alternatives
- Keep three commits + compensating cleanup job (rejected: complexity without
  atomicity).
- Outbox pattern (rejected for now: infra-gate — no queue exists or is justified).
