# node-core ↔ backend/main.py — Validation Report

**Date:** 2026-07-05T17:40:09.462Z
**Input source:** `Ibri2_SCADA_EMS_July2024.csv` (288 steps, dt = 0.083333 h)
**MILP path:** node-core → milp-service (verbatim `_run_optimizer_storage` copy) → CBC (timeLimit 45s)
**Python path:** `backend/main.py process_calculation` (unmodified, imported read-only)
**Node solve+pipeline time:** 1.9s · MILP status: Optimal

## Row-by-row match (tolerance ±0.01 on optimal_action, edv_optimal_step, edv_actual_step, gap_step)

| Metric | Value |
|---|---|
| Steps compared | 288 |
| Exact-match rows | 288 |
| **Match rate** | **100.00%** (acceptance threshold: ≥ 85%) |

## Totals delta (Node − Python)

| Field | Python | Node | Δ |
|---|---|---|---|
| edv_optimal_total | 140.41 | 140.41 | 0 |
| edv_actual_total | -48.21 | -48.21 | 0 |
| total_gap | 188.62 | 188.62 | 0 |
| dq_score | 0 | 0 | 0 |

## Divergence analysis

No rows diverged beyond tolerance. Both stacks call the same verbatim CBC model, so per-step dispatch is identical.

## Verdict

✅ PASS — node-core reproduces the production engine within acceptance criteria.

## Integrity guarantee

`backend/main.py` was imported read-only for the reference run and was not
modified by this task (verify: `git diff --stat backend/main.py` → empty).
