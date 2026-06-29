import os
import uuid
import json
import asyncio
import pandas as pd
from io import BytesIO, StringIO
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pulp
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from abc import ABC, abstractmethod

# ==========================================
# THE ASSET-AGNOSTIC INTERFACE
# ==========================================
class AssetPhysicsModel(ABC):
    """
    Abstract interface for any energy asset.
    To add Hydrogen or Desalination, create a class that inherits from this.
    """
    @abstractmethod
    def get_state_variables(self) -> dict:
        """Returns current state (e.g., SOC, Tank Level, Reservoir Head)"""
        pass

    @abstractmethod
    def calculate_step_cost(self, action: float, duration: float) -> float:
        """Calculates physical cost (degradation, fuel, membrane wear)"""
        pass

    @abstractmethod
    def update_state(self, action: float, duration: float):
        """Updates internal state based on action taken"""
        pass

# Example Implementation for BESS (Current Logic)
class BESSModel(AssetPhysicsModel):
    def __init__(self, specs: AssetSpecs):
        self.specs = specs
        self.current_soc = specs.soc_init

    def get_state_variables(self):
        return {"soc": self.current_soc}

    def calculate_step_cost(self, action: float, duration: float = 1.0) -> float:
        # Degradation cost logic
        return self.specs.deg_cost * abs(action)

    def update_state(self, action: float, duration: float = 1.0):
        # SOC update logic
        if action > 0: # Discharge
            self.current_soc -= (action / self.specs.eta_dis) / self.specs.e_max
        elif action < 0: # Charge
            self.current_soc += (abs(action) * self.specs.eta_ch) / self.specs.e_max
        self.current_soc = max(0.1, min(0.95, self.current_soc))

# Future: HydrogenModel(AssetPhysicsModel), DesalinationModel(AssetPhysicsModel)
# ==========================================
# 1. Database Setup  (UNCHANGED CORE)
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./predaiot_audit.db")
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DecisionAuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    market_price = Column(Float)
    optimal_action = Column(Float)
    actual_action = Column(Float)
    economic_gap = Column(Float)

Base.metadata.create_all(bind=engine)

# ==========================================
# 2. Data Models  (UNCHANGED CORE + NEW FIELDS)
# ==========================================
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

class TimeStepData(BaseModel):
    hour: int
    price: float
    actual_discharge: float = 0.0
    # Optional enrichment columns accepted from uploaded files
    actual_charge: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[str] = None
    curtailment_mw: Optional[float] = 0.0
    operator_override: Optional[bool] = False
    forecast_price: Optional[float] = None

class AuditRequest(BaseModel):
    asset: AssetSpecs
    time_series: List[TimeStepData]

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
    grid_demand: Optional[str] = None
    forecast_price: Optional[float] = None
    confidence: Optional[float] = None

# ==========================================
# NEW: Extended EDA Metrics Model
# ==========================================
class RootCauseItem(BaseModel):
    category: str
    contribution_pct: float
    loss_usd: float

class OpportunityItem(BaseModel):
    name: str
    annual_gain_usd: float
    difficulty: str          # Easy | Medium | Hard
    priority_stars: int      # 1–5
    description: str

class HeatMapCell(BaseModel):
    hour: int
    label: str               # HH:MM
    status: str              # optimal | acceptable | poor | critical
    gap_usd: float
    price: float
    action_taken: str

class EDAMetrics(BaseModel):
    # Section 6 — Economic Decision Quality Metrics
    economic_decision_efficiency: float     # EDE  = captured / potential
    economic_leakage_ratio: float           # ELR  = lost / potential
    dispatch_accuracy: float                # correct dispatches / total
    decision_delay_index: float             # avg timesteps late (0 if perfect)
    forecast_utilization_index: float       # % of steps with forecast provided
    curtailment_recovery_ratio: float       # curtailed MWh potentially rescued
    revenue_stacking_index: int             # number of distinct revenue services used
    economic_intelligence_score: float      # 0–100 composite
    battery_opportunity_capture: Optional[float] = None  # BESS only

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
    total_gap_usd: float
    decision_log: List[DecisionRecord]
    # Extended EDA sections
    asset_name: Optional[str] = "Energy Asset"
    asset_type: Optional[str] = "Generic"
    audit_period_label: Optional[str] = "24 Hours"
    risk_level: Optional[str] = "Moderate"          # Low | Moderate | Severe
    eda_metrics: Optional[EDAMetrics] = None
    root_causes: Optional[List[RootCauseItem]] = None
    opportunities: Optional[List[OpportunityItem]] = None
    heat_map: Optional[List[HeatMapCell]] = None
    financial_leakage: Optional[FinancialLeakage] = None
    ai_commentary: Optional[str] = None
    counterfactual_summary: Optional[str] = None

class HistoricalResponse(BaseModel):
    history_log: List[DecisionRecord]

# ==========================================
# 3. FastAPI Setup  (UNCHANGED CORE)
# ==========================================
app = FastAPI(title="PREDAIOT Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

latest_live_result = {
    "edv_optimal_total": 0, "edv_actual_total": 0,
    "dq_score": 0, "total_gap_usd": 0, "decision_log": []
}
shared_audits = {}

# ==========================================
# 4. Optimizer  (UNCHANGED CORE)
# ==========================================
def run_optimizer(asset: AssetSpecs, prices: List[float]) -> dict:
    hours = range(len(prices))
    prob = pulp.LpProblem("PREDAIOT_MILP", pulp.LpMaximize)
    p_dis = pulp.LpVariable.dicts("Discharge", hours, lowBound=0, upBound=asset.p_max)
    p_ch  = pulp.LpVariable.dicts("Charge",    hours, lowBound=0, upBound=asset.p_max)
    soc   = pulp.LpVariable.dicts("SOC",        hours, lowBound=0.1, upBound=0.95)
    is_dis = pulp.LpVariable.dicts("IsDis",     hours, cat='Binary')

    prob += pulp.lpSum([
        (prices[t] * p_dis[t]) - (prices[t] * p_ch[t]) - (asset.deg_cost * p_dis[t])
        for t in hours
    ])
    for t in hours:
        prob += p_dis[t] <= asset.p_max * is_dis[t]
        prob += p_ch[t]  <= asset.p_max * (1 - is_dis[t])
        if t == 0:
            prob += soc[t] == asset.soc_init + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        else:
            prob += soc[t] == soc[t-1] + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        if t == max(hours):
            prob += soc[t] == asset.soc_init
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return {t: (p_dis[t].varValue or 0.0) for t in hours}

# ==========================================
# 5. NEW: EDA Intelligence Engine
# ==========================================
def _classify_decision(opt: float, act: float, price: float, threshold: float = 5.0) -> tuple:
    """Returns (decision_type, confidence)"""
    gap = (opt - act) * price
    if abs(opt - act) < 0.5:
        return "Correct Dispatch", 0.96
    if opt > threshold and act < 0.5:
        return "Missed Arbitrage", min(0.99, 0.80 + (price / 200))
    if act > opt + threshold:
        return "Over-Dispatch", 0.85
    if opt < threshold and act < 0.5:
        return "Correct Idle", 0.92
    if opt > threshold and 0 < act < opt:
        return "Partial Capture", 0.78
    return "Sub-optimal Dispatch", 0.70

def _build_root_causes(decision_log: List[DecisionRecord], total_gap: float) -> List[RootCauseItem]:
    cats = {
        "Missed Arbitrage":     0.0,
        "Schedule-based Dispatch": 0.0,
        "Partial Capture":      0.0,
        "Over-Dispatch":        0.0,
        "Curtailment":          0.0,
        "SOC Constraint":       0.0,
    }
    for rec in decision_log:
        gap = rec.gap_step or 0
        if gap <= 0:
            continue
        dt = rec.decision_type or ""
        if "Missed Arbitrage" in dt:
            cats["Missed Arbitrage"] += gap
        elif "Partial" in dt:
            cats["Partial Capture"] += gap
        elif "Over" in dt:
            cats["Over-Dispatch"] += gap
        else:
            cats["Schedule-based Dispatch"] += gap
        if (rec.curtailment_mw or 0) > 0:
            cats["Curtailment"] += gap * 0.15

    result = []
    for cat, loss in cats.items():
        if loss > 0 and total_gap > 0:
            result.append(RootCauseItem(
                category=cat,
                contribution_pct=round((loss / total_gap) * 100, 1),
                loss_usd=round(loss, 2)
            ))
    result.sort(key=lambda x: x.contribution_pct, reverse=True)
    return result[:6]

def _build_opportunities(total_gap: float, asset_type: str) -> List[OpportunityItem]:
    annual = total_gap * 365
    ops = [
        OpportunityItem(
            name="Charging Window Optimization",
            annual_gain_usd=round(annual * 0.28, 0),
            difficulty="Easy", priority_stars=5,
            description="Shift charging to off-peak hours (00:00–05:00) to maximize arbitrage spread."
        ),
        OpportunityItem(
            name="Curtailment Recovery",
            annual_gain_usd=round(annual * 0.35, 0),
            difficulty="Medium", priority_stars=5,
            description="Recover curtailed generation by absorbing excess into storage during solar peak."
        ),
        OpportunityItem(
            name="Reserve Market Participation",
            annual_gain_usd=round(annual * 0.18, 0),
            difficulty="Hard", priority_stars=4,
            description="Stack ancillary services revenue on top of energy arbitrage."
        ),
        OpportunityItem(
            name="Dynamic Dispatch Threshold",
            annual_gain_usd=round(annual * 0.12, 0),
            difficulty="Easy", priority_stars=4,
            description="Replace fixed price threshold with rolling 4-hour market forecast trigger."
        ),
        OpportunityItem(
            name="Frequency Regulation Market",
            annual_gain_usd=round(annual * 0.07, 0),
            difficulty="Hard", priority_stars=3,
            description="Enroll available capacity in frequency regulation for continuous passive income."
        ),
    ]
    return ops

def _build_heat_map(decision_log: List[DecisionRecord]) -> List[HeatMapCell]:
    cells = []
    for rec in decision_log:
        h = rec.hour or 0
        hh = h // 12
        mm = (h % 12) * 5
        label = f"{hh:02d}:{mm:02d}"
        gap = rec.gap_step or 0
        opt = rec.optimal_action or 0
        act = rec.actual_action or 0
        price = rec.price or 0

        if gap <= 0:
            status = "optimal"
        elif gap < price * 1:
            status = "acceptable"
        elif gap < price * 5:
            status = "poor"
        else:
            status = "critical"

        cells.append(HeatMapCell(
            hour=h, label=label, status=status,
            gap_usd=round(gap, 2), price=price,
            action_taken=rec.decision_type or "Unknown"
        ))
    return cells

def _build_eda_metrics(
    decision_log: List[DecisionRecord],
    total_opt: float, total_act: float,
    asset_type: str
) -> EDAMetrics:
    total = len(decision_log)
    correct = sum(1 for d in decision_log if "Correct" in (d.decision_type or ""))
    with_forecast = sum(1 for d in decision_log if d.forecast_price is not None)
    curtailed_mw = sum(d.curtailment_mw or 0 for d in decision_log)
    overrides = sum(1 for d in decision_log if d.operator_override)

    ede = (total_act / total_opt) if total_opt > 0 else 0
    elr = 1 - ede
    dispatch_acc = (correct / total) if total > 0 else 0
    fui = (with_forecast / total) if total > 0 else 0

    # EIS: composite 0–100
    eis = round(
        (ede * 45) +           # capture efficiency 45pts
        (dispatch_acc * 30) +  # decision accuracy 30pts
        (fui * 15) +           # forecast utilization 15pts
        (min(1, 1 - elr) * 10) # leakage control 10pts
    ) * 100
    eis = min(100, max(0, round(eis / 100, 1)))  # normalize

    boc = None
    if asset_type in ("BESS", "Hydro"):
        boc = round(dispatch_acc * 100, 1)

    return EDAMetrics(
        economic_decision_efficiency=round(ede * 100, 2),
        economic_leakage_ratio=round(elr * 100, 2),
        dispatch_accuracy=round(dispatch_acc * 100, 2),
        decision_delay_index=round(overrides / max(1, total) * 10, 2),
        forecast_utilization_index=round(fui * 100, 2),
        curtailment_recovery_ratio=round(curtailed_mw, 2),
        revenue_stacking_index=2 if fui > 0.3 else 1,
        economic_intelligence_score=round(eis, 1),
        battery_opportunity_capture=boc
    )

def _build_ai_commentary(
    asset_name: str, total_gap: float, total_opt: float,
    decision_log: List[DecisionRecord], dq: float
) -> str:
    missed = [d for d in decision_log if d.decision_type == "Missed Arbitrage"]
    top3 = sorted(missed, key=lambda x: x.gap_step or 0, reverse=True)[:3]
    top_times = ", ".join([
        f"{(r.hour or 0)//12:02d}:{((r.hour or 0) % 12)*5:02d}"
        for r in top3
    ])
    pct = round((total_gap / total_opt * 100), 1) if total_opt > 0 else 0
    score_label = "critically underperforming" if dq < 0.4 else "underperforming" if dq < 0.7 else "near-optimal"

    lines = [
        f"During the audit period, {asset_name} was {score_label} with an Economic Intelligence Score of {round(dq*100,1)}/100.",
    ]
    if missed:
        lines.append(
            f"The asset remained idle during {len(missed)} high-price intervals despite available capacity."
            + (f" Peak missed windows occurred at {top_times}." if top_times else "")
        )
    lines.append(
        f"Total economic leakage amounted to ${total_gap:,.2f}, representing {pct}% of available market potential."
    )
    lines.append("The dominant loss driver was schedule-based dispatch rather than market-responsive optimization.")
    lines.append(f"Estimated recoverable value exceeds {max(0, round(pct * 0.68, 1))}% with operational changes alone.")
    lines.append("")
    lines.append("Recommendations:")
    lines.append("  1. Shift charging window to 00:00–05:00 off-peak hours.")
    lines.append("  2. Raise discharge trigger threshold to $45/MWh with dynamic floor.")
    lines.append("  3. Integrate 4-hour ahead price forecast into dispatch logic.")
    lines.append("  4. Enable automatic market-responsive dispatch; reduce operator override frequency.")
    lines.append("  5. Enroll available capacity in ancillary services to stack revenue streams.")
    return "\n".join(lines)

def _risk_level(dq: float) -> str:
    if dq >= 0.70:
        return "Low"
    elif dq >= 0.40:
        return "Moderate"
    return "Severe"

# ==========================================
# 6. Central Calculation Engine  (CORE UNCHANGED + EDA LAYER)
# ==========================================
def process_calculation(asset: AssetSpecs, time_series_list: list, save_to_db: bool = True):
    global latest_live_result
    prices = [ts["price"] for ts in time_series_list]
    optimal_actions = run_optimizer(asset, prices)
    total_edv_opt, total_edv_act = 0.0, 0.0
    decision_log = []
    db = SessionLocal() if save_to_db else None

    try:
        for i, ts in enumerate(time_series_list):
            opt_dis  = optimal_actions.get(i, 0.0)
            act_dis  = float(ts.get("actual_discharge", 0))
            price    = float(ts.get("price", 0))
            curtail  = float(ts.get("curtailment_mw", 0))
            override = bool(ts.get("operator_override", False))
            fc_price = ts.get("forecast_price", None)
            soc_val  = ts.get("soc", None)
            demand   = ts.get("grid_demand", None)

            # UNCHANGED core calc
            edv_opt_step = (price * opt_dis) - (asset.deg_cost * opt_dis)
            edv_act_step = (price * act_dis) - (asset.deg_cost * act_dis)
            gap_step     = edv_opt_step - edv_act_step
            total_edv_opt += edv_opt_step
            total_edv_act += edv_act_step

            dec_type, confidence = _classify_decision(opt_dis, act_dis, price)

            if db:
                db.add(DecisionAuditLog(
                    asset_id=asset.asset_id,
                    timestamp=datetime.utcnow(),
                    market_price=price,
                    optimal_action=opt_dis,
                    actual_action=act_dis,
                    economic_gap=gap_step
                ))

            decision_log.append(DecisionRecord(
                hour=ts.get("hour", i),
                price=price,
                optimal_action=round(opt_dis, 2),
                actual_action=round(act_dis, 2),
                edv_optimal_step=round(edv_opt_step, 2),
                edv_actual_step=round(edv_act_step, 2),
                gap_step=round(gap_step, 2),
                decision_type=dec_type,
                confidence=confidence,
                operator_override=override,
                curtailment_mw=curtail,
                soc=soc_val,
                grid_demand=demand,
                forecast_price=fc_price
            ))
        if db:
            db.commit()
    finally:
        if db:
            db.close()

    dq_score = (total_edv_act / total_edv_opt) if total_edv_opt > 0 else 0
    total_gap = total_edv_opt - total_edv_act

    # Build EDA intelligence layers
    eda_metrics  = _build_eda_metrics(decision_log, total_edv_opt, total_edv_act, asset.asset_type)
    root_causes  = _build_root_causes(decision_log, total_gap)
    opportunities = _build_opportunities(total_gap, asset.asset_type)
    heat_map     = _build_heat_map(decision_log)
    ai_commentary = _build_ai_commentary(asset.asset_name, total_gap, total_edv_opt, decision_log, dq_score)

    top_sources = []
    for rc in root_causes[:5]:
        top_sources.append({"name": rc.category, "usd": rc.loss_usd, "pct": rc.contribution_pct})

    financial_leakage = FinancialLeakage(
        period_24h=round(total_gap, 2),
        projection_12m=round(total_gap * 365, 2),
        top_sources=top_sources
    )

    result = AuditResponse(
        # UNCHANGED core fields
        edv_optimal_total=round(total_edv_opt, 2),
        edv_actual_total=round(total_edv_act, 2),
        dq_score=round(dq_score, 4),
        total_gap_usd=round(total_gap, 2),
        decision_log=decision_log,
        # Extended EDA
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        audit_period_label=f"{len(time_series_list)} Steps ({len(time_series_list)//12}h)",
        risk_level=_risk_level(dq_score),
        eda_metrics=eda_metrics,
        root_causes=root_causes,
        opportunities=opportunities,
        heat_map=heat_map,
        financial_leakage=financial_leakage,
        ai_commentary=ai_commentary,
        counterfactual_summary=(
            f"Under optimal dispatch, {asset.asset_name} would have captured "
            f"${total_edv_opt:,.2f} vs actual ${total_edv_act:,.2f}. "
            f"The counterfactual gap of ${total_gap:,.2f} represents decisions that "
            f"were physically feasible but economically sub-optimal."
        )
    )
    latest_live_result = result
    return result

# ==========================================
# 7. API Endpoints  (UNCHANGED CORE + universal file parser)
# ==========================================
@app.post("/api/v1/audit", response_model=AuditResponse)
async def calculate_gap(request: AuditRequest):
    return process_calculation(request.asset, [ts.dict() for ts in request.time_series])

# ==========================================
# COLUMN ALIAS MAP — fuzzy resolver
# Maps any real-world column name variant → internal name
# ==========================================
COLUMN_ALIASES = {
    # ── price — market / spot price ─────────────────────────────────────────────
    "price": [
        # English — common
        "price", "spot_price", "market_price", "energy_price", "lmp",
        "price_usd", "price_$/mwh", "price_($/mwh)", "price_mwh",
        "clearing_price", "settlement_price", "pool_price", "da_price",
        "rt_price", "wholesale_price", "electricity_price", "tariff",
        "rate", "cost_per_mwh", "mwh_price", "$/mwh", "usd/mwh",
        "omr/mwh", "omr_mwh", "price_omr", "aed/mwh", "sar/mwh",
        # Extended market aliases
        "half_hourly_price", "hhp", "imbalance_price", "balancing_price",
        "nodal_price", "zonal_price", "hub_price", "index_price",
        "pjm_lmp", "ercot_spp", "caiso_lmp", "miso_lmp",
        "epex_price", "n2ex_price", "elspot_price", "belpex_price",
        "omel_price", "gme_price", "aps_price", "negative_price",
        # Oil & Gas
        "gas_price", "gas_price_mmbtu", "fuel_cost", "henry_hub",
        "nbp_price", "ttf_price", "co2_price", "carbon_price",
        # Hydrogen
        "h2_price", "hydrogen_price", "green_h2_price",
        # Arabic aliases (أسماء عربية)
        "السعر", "سعر_الكهرباء", "السعر_الفوري", "سعر_السوق",
        "التعريفة", "سعر_المقاصة", "تكلفة_الطاقة",
    ],

    # ── actual_discharge — actual generation / output / production ──────────────
    "actual_discharge": [
        # English — common
        "actual_discharge", "discharge", "actual_power", "power_output",
        "generation", "actual_generation", "gen_mw", "output_mw",
        "dispatch_mw", "actual_dispatch", "p_actual", "p_out",
        "power_mw", "energy_out", "production", "actual_production",
        "mw_out", "discharge_mw", "bess_discharge", "solar_output",
        "wind_output", "p_gen", "pgen", "p_dis", "pdis",
        "net_generation", "real_power", "active_power",
        "gross_generation", "net_output",
        # Solar
        "solar_generation", "pv_output", "solar_power", "irradiance_mw",
        "dc_power", "ac_power", "inverter_output",
        # Wind
        "wind_generation", "turbine_output", "wind_power",
        "rotor_power", "nacelle_power", "hub_power",
        # Hydro / Pumped hydro
        "hydro_generation", "turbine_generation", "hydro_output",
        "penstock_flow_mw", "dam_output",
        # Gas / thermal
        "gas_generation", "thermal_output", "combined_cycle_output",
        "gt_output", "st_output", "peaker_output", "ocgt_output",
        # Nuclear
        "nuclear_output", "reactor_power", "reactor_output",
        # Hydrogen electrolyzer
        "electrolyzer_power", "electrolyzer_output", "h2_production_power",
        "electrolyzer_mw",
        # Desalination
        "desalination_power", "desal_mw", "ro_power", "msf_power",
        "med_power",
        # Oil & Gas compression / injection
        "compressor_power", "injection_power", "pump_power",
        # Arabic aliases
        "التوليد", "الإنتاج", "القدرة_الفعلية", "الطاقة_المنتجة",
        "الصرف_الفعلي", "الخرج", "الطاقة_الكهربائية",
        "توليد_الطاقة", "إنتاج_الطاقة",
    ],

    # ── hour — timestep / interval index ────────────────────────────────────────
    "hour": [
        "hour", "interval", "timestep", "time_step", "step",
        "period", "slot", "index", "idx", "t", "timestamp",
        "datetime", "time", "date_time", "hour_index",
        "half_hour", "quarter_hour", "five_min", "minute",
        "الوقت", "الساعة", "الفترة", "الفاصل_الزمني",
    ],

    # ── actual_charge — charging power (BESS / pumped hydro / electrolyzer) ─────
    "actual_charge": [
        "actual_charge", "charge", "charge_mw", "p_charge", "pcharge",
        "charging_power", "bess_charge", "charge_power", "p_ch",
        "pumping_power", "pump_power_mw", "h2_load", "electrolyzer_load",
        "الشحن", "طاقة_الشحن",
    ],

    # ── soc — state of charge / reservoir level ──────────────────────────────────
    "soc": [
        "soc", "state_of_charge", "battery_soc", "soc_pct",
        "soc_%", "energy_level", "stored_energy_pct",
        # Hydro reservoir
        "reservoir_level", "water_level_m", "water_level_pct",
        "reservoir_pct", "head_m",
        # Hydrogen tank
        "tank_pressure", "h2_level", "h2_storage_pct",
        # Arabic
        "حالة_الشحن", "مستوى_الطاقة", "مستوى_الخزان",
    ],

    # ── curtailment ───────────────────────────────────────────────────────────────
    "curtailment_mw": [
        "curtailment_mw", "curtailment", "curtailed_mw", "curtailed",
        "clipped_mw", "clipping", "spilled_mw", "spillage",
        "wind_curtailment", "solar_curtailment", "forced_outage_mw",
        "التقليص", "التخفيض_القسري",
    ],

    # ── operator override ────────────────────────────────────────────────────────
    "operator_override": [
        "operator_override", "override", "manual_override",
        "human_override", "manual_dispatch", "operator_intervention",
        "تدخل_المشغل", "التجاوز_اليدوي",
    ],

    # ── forecast price ───────────────────────────────────────────────────────────
    "forecast_price": [
        "forecast_price", "predicted_price", "price_forecast",
        "da_forecast", "price_prediction", "forecast", "f_price",
        "price_forecast_da", "day_ahead_forecast",
        "السعر_المتوقع", "توقع_السعر",
    ],

    # ── grid demand ───────────────────────────────────────────────────────────────
    "grid_demand": [
        "grid_demand", "demand", "load", "system_load",
        "grid_load", "net_load", "demand_level",
        "الطلب", "حمل_الشبكة", "حمل_النظام",
    ],

    # ── asset-specific extras ─────────────────────────────────────────────────────
    # Gas / thermal efficiency
    "fuel_consumption": [
        "fuel_consumption", "fuel_rate", "heat_rate", "gas_consumption",
        "fuel_flow_mmbtu", "gas_flow_mcf",
    ],
    # Hydrogen production volume
    "h2_production_kg": [
        "h2_production_kg", "hydrogen_production", "h2_flow_rate",
        "h2_volume_nm3", "electrolyzer_kg_h",
    ],
    # Desalination
    "water_production_m3": [
        "water_production_m3", "permeate_flow", "product_water",
        "desal_output_m3h", "water_m3",
    ],
}

# Asset spec meta-columns that can optionally appear as file columns
ASSET_META_ALIASES = {
    "asset_type": ["asset_type", "type", "asset_class"],
    "asset_name": ["asset_name", "name", "asset", "plant_name", "site_name"],
    "p_max": ["p_max", "max_power", "capacity_mw", "rated_power", "nameplate_mw"],
    "e_max": ["e_max", "energy_capacity", "battery_capacity_mwh", "storage_mwh"],
    "soc_init": ["soc_init", "initial_soc", "soc_initial"],
    "eta_ch": ["eta_ch", "charge_efficiency", "charging_efficiency"],
    "eta_dis": ["eta_dis", "discharge_efficiency", "discharging_efficiency"],
    "deg_cost": ["deg_cost", "degradation_cost", "wear_cost"],
}

def _resolve_columns(df_cols: list) -> dict:
    """
    Returns a mapping {internal_name: actual_col_name} for every alias match found.
    Normalises column names before matching.
    """
    normalised = {c: c.lower().strip().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("/", "_") for c in df_cols}
    resolved = {}
    for internal, aliases in {**COLUMN_ALIASES, **ASSET_META_ALIASES}.items():
        for original, norm in normalised.items():
            if norm in aliases and internal not in resolved:
                resolved[internal] = original
                break
    return resolved


def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    """
    Universal file parser — handles CSV/TSV/Excel with automatic encoding detection.

    Encoding resolution order:
      1. BOM bytes  →  UTF-16 / UTF-8-BOM
      2. charset_normalizer (pip install charset-normalizer) auto-detect
      3. chardet fallback
      4. Exhaustive encoding list (Western, Arabic, Cyrillic, CJK …)
      5. Force-decode with replacement characters (never raises)
    """
    fname = (filename or "").lower()

    # ── Excel ──────────────────────────────────────────────────────────────────
    if fname.endswith((".xlsx", ".xls")):
        return pd.read_excel(BytesIO(contents))

    # Separator heuristic
    sep = "\t" if fname.endswith(".tsv") else ","

    # ── BOM detection ──────────────────────────────────────────────────────────
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return pd.read_csv(BytesIO(contents), encoding="utf-16", sep=sep)
        except Exception:
            pass
    if contents[:3] == b"\xef\xbb\xbf":
        try:
            return pd.read_csv(BytesIO(contents), encoding="utf-8-sig", sep=sep)
        except Exception:
            pass

    # ── charset_normalizer auto-detect ─────────────────────────────────────────
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(contents[:20000]).best()
        if result and result.encoding:
            try:
                return pd.read_csv(BytesIO(contents), encoding=str(result.encoding), sep=sep)
            except Exception:
                pass
    except ImportError:
        pass

    # ── chardet fallback ───────────────────────────────────────────────────────
    try:
        import chardet
        detected = chardet.detect(contents[:20000])
        enc_detected = detected.get("encoding") or ""
        if enc_detected:
            try:
                return pd.read_csv(BytesIO(contents), encoding=enc_detected, sep=sep)
            except Exception:
                pass
    except ImportError:
        pass

    # ── Exhaustive encoding list ───────────────────────────────────────────────
    ENCODINGS = [
        # Unicode
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32",
        # Western European
        "latin-1", "cp1252", "iso-8859-15",
        # Arabic (كل ملفات Excel المحلية تستخدم هذا)
        "cp1256", "iso-8859-6", "windows-1256",
        # Central / Eastern European
        "cp1250", "iso-8859-2",
        # Cyrillic
        "cp1251", "iso-8859-5", "koi8-r",
        # CJK
        "gbk", "gb2312", "gb18030", "big5", "shift_jis", "euc-jp", "euc-kr",
        # Misc
        "ascii", "cp437",
    ]
    for enc in ENCODINGS:
        try:
            return pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception:
            continue

    # ── Nuclear fallback: force-decode with Unicode replacement chars ───────────
    try:
        text_content = contents.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(text_content), sep=sep)
        # Strip replacement chars from column names
        df.columns = [str(c).replace("\ufffd", "").strip() for c in df.columns]
        return df
    except Exception:
        pass

    raise ValueError(
        "Could not parse this file. "
        "Please try: (1) save as CSV UTF-8 in Excel → Save As → CSV UTF-8 (comma delimited), "
        "or (2) export as .xlsx. "
        "Your file's encoding was not recognizable after 20+ attempts."
    )


@app.post("/api/v1/audit/file", response_model=AuditResponse)
async def audit_from_file(file: UploadFile = File(...)):
    """
    Universal file ingestion — accepts CSV or Excel with ANY column naming convention.

    The engine auto-resolves column names via an alias map covering 80+ variants.

    The only hard requirement is ONE column that looks like a price and ONE that
    looks like a power output / discharge. Everything else is optional.

    Accepted file formats: .csv  .xlsx  .xls
    """
    try:
        contents = await file.read()
        df = _parse_file_bytes(contents, file.filename or "")

        # Resolve column aliases
        col_map = _resolve_columns(list(df.columns))

        # Check required fields resolved
        missing_internal = []
        for req in ("price", "actual_discharge"):
            if req not in col_map:
                missing_internal.append(req)

        if missing_internal:
            # Build a helpful error listing what the file actually has
            return JSONResponse(status_code=400, content={
                "detail": (
                    f"Could not find required column(s): {missing_internal}. "
                    f"Your file has columns: {list(df.columns)}. "
                    f"Use /api/v1/audit/inspect to see the full mapping attempt. "
                    f"Accepted price aliases include: spot_price, lmp, market_price, energy_price, omr_mwh … "
                    f"Accepted discharge aliases include: generation, actual_power, output_mw, p_actual, gen_mw …"
                )
            })

        # Rename resolved columns to internal names
        rename_map = {v: k for k, v in col_map.items() if v in df.columns}
        df = df.rename(columns=rename_map)

        # Add missing optional columns with defaults
        defaults = {
            'hour': None, 'actual_charge': 0.0, 'soc': None,
            'grid_demand': None, 'curtailment_mw': 0.0,
            'operator_override': False, 'forecast_price': None,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        # Fill hour index if missing or all-null
        if df['hour'].isnull().all():
            df['hour'] = range(len(df))

        df = df.fillna({'actual_discharge': 0.0, 'actual_charge': 0.0, 'curtailment_mw': 0.0})

        # Coerce numeric columns — tolerates strings like "12.5 MW" by stripping non-numeric chars
        for col in ('price', 'actual_discharge', 'actual_charge', 'curtailment_mw'):
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r'[^\d.\-]', '', regex=True),
                    errors='coerce'
                ).fillna(0.0)

        # Asset specs from meta-columns (first row), fallback to defaults
        asset_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in df.columns:
                val = df[key].iloc[0]
                if pd.notna(val):
                    asset_kwargs[key] = val

        asset = AssetSpecs(**asset_kwargs)

        time_series = df[[
            'hour', 'price', 'actual_discharge', 'actual_charge',
            'soc', 'grid_demand', 'curtailment_mw', 'operator_override', 'forecast_price'
        ]].to_dict('records')

        return process_calculation(asset, time_series)

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error parsing file: {str(e)}"})


@app.post("/api/v1/audit/inspect")
async def inspect_file(file: UploadFile = File(...)):
    """
    Debug endpoint — returns the column mapping the engine would apply to your file,
    without running the full audit. Use this to diagnose upload failures.
    """
    try:
        contents = await file.read()
        df = _parse_file_bytes(contents, file.filename or "")
        col_map = _resolve_columns(list(df.columns))
        unresolved = [c for c in df.columns if c not in col_map.values()]
        return {
            "file_columns": list(df.columns),
            "rows": len(df),
            "resolved_mapping": col_map,          # internal_name → your_col_name
            "unresolved_columns": unresolved,      # columns we couldn't map
            "will_succeed": "price" in col_map and "actual_discharge" in col_map,
            "sample_row": df.iloc[0].to_dict() if len(df) > 0 else {},
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/historical", response_model=HistoricalResponse)
async def get_historical_data():
    db = SessionLocal()
    try:
        if "sqlite" in DATABASE_URL:
            return HistoricalResponse(history_log=[])
        result = db.execute(text(
            "SELECT DATE(timestamp) AS day, SUM(economic_gap) as daily_gap "
            "FROM audit_logs WHERE timestamp > NOW() - INTERVAL '30 days' "
            "GROUP BY DATE(timestamp) ORDER BY day DESC"
        ))
        return HistoricalResponse(history_log=[
            DecisionRecord(day=row.day.strftime("%Y-%m-%d"), daily_gap=round(row.daily_gap, 2))
            for row in result if row.daily_gap
        ])
    finally:
        db.close()

@app.post("/api/share")
async def create_share_link(data: AuditResponse):
    token = str(uuid.uuid4())
    shared_audits[token] = data.dict()
    return {"share_url": f"/share/{token}"}

@app.get("/share/{token}")
async def get_shared_audit(token: str):
    if token in shared_audits:
        return shared_audits[token]
    return JSONResponse(status_code=404, content={"detail": "Report link expired or not found"})

@app.get("/api/latest")
async def get_latest_live_data():
    return latest_live_result

# ==========================================
# NEW: EDA Credit Rating
# ==========================================
def _eda_rating(dq_score: float) -> tuple:
    """Returns (rating, label, color_code) — like credit rating for energy assets."""
    s = dq_score * 100
    if s >= 90: return "AAA", "Excellent",    "#00E676"
    if s >= 80: return "AA",  "Very Good",    "#69F0AE"
    if s >= 70: return "A",   "Good",         "#B9F6CA"
    if s >= 60: return "BBB", "Acceptable",   "#FFD600"
    if s >= 50: return "BB",  "Below Average","#FF9800"
    if s >= 40: return "B",   "Poor",         "#FF5722"
    return              "CCC","Critical",     "#FF1744"


# ==========================================
# NEW: Real-Time WebSocket Stream
# ==========================================
@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    Economic Advisory Observer Mode (Level 2).
    Transforms raw SCADA data into actionable dispatch recommendations.
    """
    await websocket.accept()
    cumulative_opt = 0.0
    cumulative_act = 0.0
    step_count = 0

    try:
        while True:
            data = await websocket.receive_json()
            price    = float(data.get("price", 0))
            actual   = float(data.get("actual_discharge", 0))
            p_max    = float(data.get("p_max", 50))
            deg_cost = float(data.get("deg_cost", 5))
            soc      = float(data.get("soc", 0.5))

            # 1. Real-time Heuristic Optimal (Fast enough for WebSocket)
            can_dis  = soc > 0.2
            economic_threshold = deg_cost * 1.5 # Minimal margin
            optimal  = p_max if (price > economic_threshold and can_dis) else 0.0

            # 2. Core Calculations
            edv_opt = max(0.0, (price - deg_cost) * optimal)
            edv_act = max(0.0, (price - deg_cost) * actual)
            gap     = edv_opt - edv_act
            expected_gain = edv_opt - edv_act # Gain if we follow recommendation

            cumulative_opt  += edv_opt
            cumulative_act  += edv_act
            step_count      += 1

            # 3. Decision Classification
            dec_type, conf = _classify_decision(optimal, actual, price)
            
            # 4. Advisory Logic Generation (THE NEW PART)
            if gap > 10 and optimal > 0:
                recommendation = "DISCHARGE"
                rec_power = optimal
                severity = "HIGH" if gap > 100 else "MEDIUM"
                message = f"⚠ Dispatch {optimal:.0f} MW — price ${price:.2f} exceeds threshold. Capturing ${edv_opt:.0f} potential."
            elif optimal == 0 and actual > 0:
                recommendation = "STOP" # Or IDLE depending on asset
                rec_power = 0.0
                severity = "HIGH" if gap > 50 else "LOW"
                message = f"🔴 Market price ${price:.2f} is below degradation cost. Discharging is destroying value."
            else:
                recommendation = "HOLD"
                rec_power = actual
                severity = "LOW"
                message = "✓ Current dispatch is near-optimal or no opportunity exists."

            dq_live = (cumulative_act / cumulative_opt * 100) if cumulative_opt > 0 else 100.0
            rating, rating_label, _ = _eda_rating(dq_live / 100)

            # 5. THE ADVISORY PAYLOAD (Matches your requested JSON structure)
            await websocket.send_json({
                # Core Audit
                "step":             step_count,
                "gap_step":         round(gap, 2),
                "cumulative_gap":   round(cumulative_opt - cumulative_act, 2),
                "dq_score_live":    round(dq_live, 1),
                "rating":           rating,
                
                # --- ADVISORY LAYER (NEW) ---
                "recommendation":   recommendation,       # DISCHARGE | HOLD | STOP
                "recommended_power": round(rec_power, 2), # MW
                "expected_gain":    round(expected_gain, 2), # USD
                "confidence":       round(conf * 100, 1),   # %
                "severity":         severity,
                "message":          message,
                
                # Raw data context
                "price":            price,
                "actual_action":    round(actual, 2),
                "optimal_action":   round(optimal, 2)
            })
    except WebSocketDisconnect:
        pass


# ==========================================
# NEW: Single-Step Live Calculation (polling fallback)
# ==========================================
@app.post("/api/v1/live/step")
async def live_step(data: Dict[str, Any] = Body(...)):
    """
    Single real-time step calculation — polling alternative to WebSocket.
    Useful for SCADA systems that push one data point at a time.
    """
    price    = float(data.get("price", 0))
    actual   = float(data.get("actual_discharge", 0))
    p_max    = float(data.get("p_max", 50))
    deg_cost = float(data.get("deg_cost", 5))
    soc      = float(data.get("soc", 0.5))

    can_dis  = soc > 0.2
    optimal  = p_max if (price > deg_cost * 2 and can_dis) else 0.0

    edv_opt = max(0.0, (price - deg_cost) * optimal)
    edv_act = max(0.0, (price - deg_cost) * actual)
    gap     = edv_opt - edv_act
    dec_type, conf = _classify_decision(optimal, actual, price)

    return {
        "price":          price,
        "optimal_action": round(optimal, 2),
        "actual_action":  round(actual, 2),
        "gap_step":       round(gap, 2),
        "decision_type":  dec_type,
        "confidence":     round(conf, 2),
        "alert":          gap > 100,
        "recommendation": (
            f"Dispatch {optimal:.0f} MW — ${price:.2f}/MWh exceeds economic threshold"
            if gap > 10 else "Current dispatch near-optimal"
        ),
    }


# ==========================================
# NEW: Economic Decision Certificate
# ==========================================
def _build_certificate(data: dict) -> dict:
    dq         = data.get("dq_score", 0)
    total_gap  = data.get("total_gap_usd", 0)
    opt        = data.get("edv_optimal_total", 0)
    act        = data.get("edv_actual_total", 0)
    rating, rating_label, rating_color = _eda_rating(dq)
    
    # ... (Keep existing calculations for eis, cert_id, etc.) ...

    # --- NEW: Rating Summary Logic ---
    if rating in ["AAA", "AA"]:
        summary = (
            f"Outstanding economic decision performance. "
            f"The asset captured {round(dq*100,1)}% of available market value. "
            f"Dispatch decisions consistently matched the optimal counterfactual strategy."
        )
    elif rating in ["A", "BBB"]:
        summary = (
            f"Acceptable economic performance with minor leakage. "
            f"{round((1-dq)*100,1)}% of achievable value was lost, primarily during transitional periods. "
            f"Operational review recommended to capture remaining margin."
        )
    elif rating in ["BB", "B"]:
        summary = (
            f"Moderate to poor economic leakage detected. "
            f"Operator overrides or sub-optimal scheduling reduced revenue capture significantly. "
            f"Immediate optimization of dispatch logic required."
        )
    else: # CCC
        summary = (
            f"Critical Economic Underperformance. "
            f"The asset is operating at a severe economic loss relative to its potential. "
            f"Estimated annual leakage exceeds ${total_gap*365:,.0f}. "
            f"Immediate operational intervention is mandatory."
        )

    return {
        # ... (Existing fields) ...
        "rating":               rating,
        "rating_label":         rating_label,
        "rating_color":         rating_color,
        # --- NEW FIELD ---
        "rating_summary":       summary, 
        "methodology":          "PREDAIOT Economic Decision Audit™ Methodology (Patent Pending)",
        "standard":             "PREDAIOT EDA Standard v1.0",
    }

@app.get("/api/v1/certificate")
async def get_certificate_for_latest():
    """Returns an Economic Decision Certificate for the most recent audit."""
    global latest_live_result
    data = latest_live_result
    if isinstance(data, dict):
        if data.get("dq_score", 0) == 0:
            return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
        return _build_certificate(data)
    # AuditResponse pydantic object
    return _build_certificate(data.dict())


@app.post("/api/v1/certificate")
async def generate_certificate_for_audit(data: AuditResponse):
    """Generate a certificate for a provided audit result."""
    return _build_certificate(data.dict())


# ==========================================
# NEW: Claude AI Enhancement Proxy
# ==========================================
@app.post("/api/v1/ai-enhance")
async def ai_enhance(request: Dict[str, Any] = Body(...)):
    """
    Proxy endpoint for Claude AI enhanced commentary.
    Requires ANTHROPIC_API_KEY environment variable.

    Add to your Render / Railway env vars:
      ANTHROPIC_API_KEY = sk-ant-...
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(status_code=503, content={
            "detail": "ANTHROPIC_API_KEY not configured. Add it to your deployment environment variables."
        })
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=request.get("model", "claude-sonnet-4-6"),
            max_tokens=request.get("max_tokens", 1000),
            messages=request.get("messages", []),
        )
        return {"content": [{"type": "text", "text": msg.content[0].text}]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Claude API error: {str(e)}"})



# ==========================================
# 8. Serve Frontend  (UNCHANGED CORE)
# ==========================================
try:
    frontend_path = os.path.abspath("../frontend/dist")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
except Exception:
    pass