# -*- coding: utf-8 -*-
"""Pydantic request/response schemas — extracted VERBATIM from main.py
(refactor step 3, schemas-first). No behaviour/validation change: plain
models with literal defaults. Bottom of the graph (pydantic + typing only).
"""
from typing import Optional, List, Dict, Any  # noqa: F401
from pydantic import BaseModel


class AssetSpecs(BaseModel):
    # Universal fields — works for all energy assets
    asset_type: Optional[str] = "Generic"
    # Supported: BESS | Solar | Wind | Gas | Hydro | Hydrogen | Desalination
    #            Nuclear | OilGas | CHP | Geothermal | Tidal | Generic
    asset_name: Optional[str] = "Energy Asset"
    asset_id:   Optional[str] = "ASSET_01"
    location:   Optional[str] = None
    market:     Optional[str] = None
    p_max:      float = 50.0
    e_max:      float = 100.0
    soc_init:   float = 0.2
    eta_ch:     float = 0.95
    eta_dis:    float = 0.95
    deg_cost:   float = 5.0
    # Cert "ISSUED TO" fields (Coverage Tasks Fix B). Optional — default falls
    # back to "Confidential — Available on Request" in _build_certificate.
    client_name:    Optional[str] = None
    client_company: Optional[str] = None

class TimeStepData(BaseModel):
    hour: int
    price: float
    actual_discharge: float = 0.0
    # Optional enrichment columns accepted from uploaded files
    actual_charge: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[float] = None
    curtailment_mw: Optional[float] = 0.0
    operator_override: Optional[bool] = False
    forecast_price: Optional[float] = None

class AuditRequest(BaseModel):
    asset: AssetSpecs
    time_series: List[TimeStepData]
    # Step duration in hours (0.0833… = 5-minute SCADA data). Defaults to the
    # legacy hourly assumption so existing callers get identical numbers.
    dt_hours: Optional[float] = 1.0

class DecisionRecord(BaseModel):
    hour: Optional[int] = None
    day: Optional[str] = None
    price: Optional[float] = None
    optimal_action: Optional[float] = None
    actual_action: Optional[float] = None
    edv_optimal_step: Optional[float] = None
    edv_actual_step: Optional[float] = None
    gap_step: Optional[float] = None
    daily_gap: Optional[float] = None
    # Extended decision intelligence fields
    decision_type: Optional[str] = None         # Missed Arbitrage | Correct | Over-Discharge | Idle
    operator_override: Optional[bool] = False
    curtailment_mw: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[float] = None
    forecast_price: Optional[float] = None
    confidence: Optional[float] = None

class RootCauseItem(BaseModel):
    category: str
    contribution_pct: float
    loss_usd: float

class OpportunityItem(BaseModel):
    # No-Fabrication rule (docs/REMOVED_HEURISTICS.md): every numeric field is
    # either derived from ledger rows with a stated formula, or None. The
    # withdrawn fields are retained as keys for API compatibility only.
    name: str
    description: str
    # Derived economics — Σ gap_step over the ledger rows matching this
    # opportunity's classification filter. None on advisory items.
    period_gain: Optional[float] = None
    annual_gain_usd: Optional[float] = None      # period_gain × (8760/span_h), linear extrapolation
    share_of_positive_gap_pct: Optional[float] = None  # period_gain / Σ positive gap_step × 100
    intervals_observed: Optional[int] = None
    evidence: Optional[str] = None
    derivation: Optional[str] = None             # exact ledger filter + formula
    # Qualitative advisory labels (recommendations expressed as text, not
    # dressed as measurements)
    difficulty: Optional[str] = None
    investment_type: Optional[str] = None
    owner: Optional[str] = None
    operational_risk: Optional[str] = None
    # Experimental flag: conceptually valuable, not derivable from this audit
    experimental: bool = False
    experimental_note: Optional[str] = None
    # WITHDRAWN (previously fabricated) — always None
    priority_stars: Optional[int] = None
    priority_score: Optional[int] = None
    confidence_pct: Optional[float] = None
    payback_days: Optional[int] = None
    efficiency_gain_pct: Optional[float] = None

class HeatMapCell(BaseModel):
    hour: int
    label: str               # HH:MM
    status: str              # optimal | acceptable | poor | critical
    gap_usd: float
    price: float
    action_taken: str

class EDAMetrics(BaseModel):
    # Section 6 — Economic Decision Quality Metrics.
    # Only ratios derivable from ledger rows are populated. Withdrawn
    # composite/invented-scale fields are retained as None for API
    # compatibility (docs/REMOVED_HEURISTICS.md).
    economic_decision_efficiency: float     # EDE = EDV_act / EDV_opt × 100 (Ch 4.2 domain rules)
    economic_leakage_ratio: float           # ELR = 100 − EDE
    dispatch_accuracy: float                # steps classified Correct / total × 100
    forecast_utilization_index: float       # steps with forecast present / total × 100
    override_rate_pct: Optional[float] = None      # override-flagged steps / total × 100
    curtailed_energy_mwh: Optional[float] = None   # Σ curtailment_mw × Δt
    # WITHDRAWN (previously fabricated) — always None
    decision_delay_index: Optional[float] = None
    curtailment_recovery_ratio: Optional[float] = None
    revenue_stacking_index: Optional[int] = None
    economic_intelligence_score: Optional[float] = None
    battery_opportunity_capture: Optional[float] = None

class FinancialLeakage(BaseModel):
    period_24h: float
    period_7d: Optional[float] = None
    period_30d: Optional[float] = None
    projection_12m: float
    top_sources: List[dict]                 # [{name, usd, pct}]

class AuditResponse(BaseModel):
    # Core (UNCHANGED field names)
    edv_optimal_total: float
    edv_actual_total: float
    dq_score: float
    # Unclamped DQ ratio. > 1.0 signals model/data disagreement (bad column
    # mapping or asset specs) — ingestion turns that into a data-quality flag.
    dq_score_raw: Optional[float] = None
    total_gap_usd: float
    # Currency the uploaded data is denominated in (detected from column
    # names, e.g. "solar_revenue_omr" → OMR). PDF + certificate render this
    # instead of assuming dollars. "USD" = legacy default.
    currency: Optional[str] = "USD"
    # Offline audits benchmark against ETL — the perfect-foresight hindsight
    # optimum (Reference Manual Ch 6.1) — so dq_score is formally the ECF.
    benchmark: Optional[str] = "ETL (perfect-foresight hindsight, Ref. Manual Ch 6.1)"
    # Ch 8.2 split: {forecast_gap, execution_gap, recommended_value, method}.
    # Present only for storage audits whose file carries a forecast column.
    gap_attribution: Optional[Dict[str, Any]] = None
    # Presentation hierarchy (Scientific Hardening item 2). The perfect-
    # foresight optimum is a BENCHMARK, not an achievable target:
    #   theoretical_ceiling_gap   — alias of total_gap_usd under its honest
    #                               name: gap vs the Theoretical Economic
    #                               Ceiling (Upper Bound Benchmark).
    #   recoverable_execution_gap — gap_attribution.execution_gap: value
    #                               achievable using information available at
    #                               decision time. None when no forecast
    #                               column exists — never fabricated.
    #   headline_gap_basis        — which figure the UI should headline.
    theoretical_ceiling_gap: Optional[float] = None
    recoverable_execution_gap: Optional[float] = None
    headline_gap_basis: Optional[str] = "ceiling"  # "execution" | "ceiling"
    # C2 — chain of custody: input hash, provenance, and software versions.
    # Populated by the file-audit endpoint; None for raw JSON audits.
    audit_manifest: Optional[Dict[str, Any]] = None
    # W1–W4 — versioned quality metrics (asset-agnostic; N/A-aware).
    # data_quality_index: {value, grade, interpretation, components{...}}
    # audit_confidence:   {value|None, grade|INDETERMINATE, factors{...}}
    # forecast_reliability: report-only, Experimental; None when no forecast.
    # data_quality_manifest: raw integer evidence DQI is derived from.
    data_quality_index: Optional[Dict[str, Any]] = None
    audit_confidence: Optional[Dict[str, Any]] = None
    forecast_reliability: Optional[Dict[str, Any]] = None
    data_quality_manifest: Optional[Dict[str, Any]] = None
    # Phase 4 S6 — the Facility Understanding Engine's evidence-backed profile
    # (what the platform recognized BEFORE auditing: equipment, capabilities,
    # facility hypothesis, each with confidence + evidence). Advisory / presentation
    # only — the engine input is unchanged; None for legacy JSON audits.
    facility_profile: Optional[Dict[str, Any]] = None
    decision_log: List[DecisionRecord]
    # Extended EDA sections
    asset_name: Optional[str] = "Energy Asset"
    asset_type: Optional[str] = "Generic"
    # Physics-archetype routing (Part 1): which frozen engine track ran and why.
    # asset_class ∈ storage|intermittent|dispatchable|load. For a consumption asset
    # this is "load" — audited in cost-of-timing space, not the storage formula.
    asset_class: Optional[str] = None
    classification_basis: Optional[str] = None
    # Part 4 validation gates: {passed, errors, warnings, currency_source}. Hard
    # gate failures withhold the result; soft gates surface as warnings.
    validation: Optional[Dict[str, Any]] = None
    audit_period_label: Optional[str] = "24 Hours"
    risk_level: Optional[str] = "Moderate"          # Low | Moderate | Severe
    eda_metrics: Optional[EDAMetrics] = None
    root_causes: Optional[List[RootCauseItem]] = None
    opportunities: Optional[List[OpportunityItem]] = None
    heat_map: Optional[List[HeatMapCell]] = None
    financial_leakage: Optional[FinancialLeakage] = None
    ai_commentary: Optional[str] = None
    counterfactual_summary: Optional[str] = None
    # ISSUED TO block (Coverage Tasks Fix B) — echoed from AssetSpecs so the
    # certificate + PDF can render engagement-letter-style header without a
    # second round-trip.
    asset_id: Optional[str] = None
    asset_location: Optional[str] = None
    client_name: Optional[str] = None
    client_company: Optional[str] = None

class HistoricalResponse(BaseModel):
    history_log: List[DecisionRecord]

class TrialStartRequest(BaseModel):
    email: str
    asset_name: Optional[str] = None
    source: Optional[str] = None  # e.g. "landing", "demo-link", "outreach"

class TrialStartResponse(BaseModel):
    token: str
    expires_at: str
    booking_url: str  # surfaced upfront so the frontend can build the expiry CTA without a second request

class TrialStatusResponse(BaseModel):
    email: str
    asset_name: Optional[str] = None
    expires_at: str
    audit_run_count: int
    is_expired: bool

class RegisterRequest(BaseModel):
    email: str
    password: str
    organization: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AssetCreateRequest(BaseModel):
    name: str
    asset_type: str = "storage"
    capacity_mw: Optional[float] = None
    currency: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None

class MemberCreateRequest(BaseModel):
    email: str
    role: str = "viewer"
    password: Optional[str] = None   # omitted -> generated, returned once

class MemberRoleRequest(BaseModel):
    role: str

class FacilityMemberRequest(BaseModel):
    # Identify the org member by email (preferred) or user_id; role is a
    # facility-scoped role (auditor/operator/executive/viewer).
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: str

class DecisionTransitionRequest(BaseModel):
    to_state: str
    note: Optional[str] = None

class OutcomeRequest(BaseModel):
    verification_audit_id: int
    note: Optional[str] = None

class GovernanceRequest(BaseModel):
    verdict: str
    note: Optional[str] = None

class LiveIngestRequest(BaseModel):
    stream_id: str
    source: str = "rest"
    currency: str = "USD"
    asset_id: Optional[int] = None
    events: List[Dict[str, Any]]           # raw readings (connector-normalized)

class ReconcileRequest(BaseModel):
    certified_audit_id: int
    note: Optional[str] = None
