# SPEC-MI · Motion→Data Traceability Map (evidence-gated)

> **Law (MI-0):** no visual element exists without a real backend value. Every
> animation below is annotated with the EXACT field it binds to, verified against
> the live payload (`public/demo_report.json`, probed 2026-07-20). Where the data
> does NOT exist, we do **not** fabricate — we either repurpose the visual onto
> real fields or ship a documented placeholder listing the required backend work.

| MI | Component | Binds to (verified real) | Not-backed → decision |
|----|-----------|--------------------------|------------------------|
| MI-2 | `DecisionEngine` | `decision_log[].gap_step` (288 rows) — dot color = leak(>0)/optimal(≤0); verdict counts are real sums | — |
| MI-3 | `RecoveryCounter` | `opportunities[].period_gain` (exact positive-gap partition) | — |
| MI-4 | `EnergyFlowNetwork` | `risk_level` (leak verdict) + `total_gap_usd` (caption) | **PV node, GRID import/export split, LOAD series: NOT in payload.** Kept ABSTRACT (GRID·BESS·LOAD as topology, not metered flows). A literal metered PV→BESS→LOAD map needs new fields → not built, not faked. |
| MI-5 | `EconomicHealthOrb` | `data_quality_index.value`, `audit_confidence.value`, `eda_metrics.economic_decision_efficiency` (3 real rings) | **Physical asset health (battery SoH, PCS, thermal): DOES NOT EXIST** — PREDAIOT audits *economic decision* quality, not hardware. Refused to fabricate a "health orb" of invented physical scores; repurposed onto the three real economic-health metrics. A true asset-health orb requires a telemetry/BMS ingest pipeline (documented as future backend work). |
| MI-6 | `PredictiveTimeline` | `decision_log[].edv_actual_step` vs `edv_optimal_step` → two real cumulative curves (Past→Present) | **"Future"/forecast projection line: NOT backed** (recorded-period-only, No-Fabrication rule; `forecast_price` is a historical day-ahead input, not a forward projection). Future segment shown as an explicit "not projected — audit is evidence-only" marker, never a drawn line. |
| MI-7 | `LeakageRadar` | `root_causes[].category` + `.loss_usd` + `.contribution_pct` (3 real causes) | — |
| MI-8 | `MissionStatusBanner` | `audit_manifest.audit_engine_version` (2.1.0), `decision_log.length`, `audit_manifest.solver`, `total_gap_usd`+`currency`, `risk_level`, `audit_confidence.grade`, `data_quality_index.grade` | ED25519 badge: `signature_status` lives on the **/certificate** response, not the audit payload → the badge renders the real cert status when a certificate is loaded, else a neutral "SIGNABLE" state. Never hardcoded. |

## Required backend fields for the currently-not-backed visuals (future work, not now)
- **Metered energy topology (MI-4 full):** per-interval `grid_import_mw`, `pv_generation_mw`, `load_mw`, `bess_charge/discharge_mw` as distinct series.
- **Physical asset health (MI-5 physical):** `battery_soh_pct`, `pcs_health_pct`, `thermal_margin_pct` from a BMS/EMS telemetry ingest.
- **Forward forecast (MI-6 future):** an explicit projected-optimal series with confidence bands, kept OUT of the audit today by the No-Fabrication rule — would be a separate "forecast" product surface, clearly labelled non-audited.

_This document is the contract: a reviewer can trace any moving pixel to a field here._
