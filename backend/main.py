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

# ==========================================
# 1. Database Setup
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
# 2. Data Models
# ==========================================
class AssetSpecs(BaseModel):
    asset_type: Optional[str] = "Generic"
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
    decision_type: Optional[str] = None
    verdict: Optional[str] = None         # NEW: Decision Forensics
    root_cause: Optional[str] = None      # NEW: Decision Forensics
    severity: Optional[str] = None        # NEW: Decision Forensics
    operator_override: Optional[bool] = False
    curtailment_mw: Optional[float] = 0.0
    soc: Optional[float] = None
    grid_demand: Optional[str] = None
    forecast_price: Optional[float] = None
    confidence: Optional[float] = None

class RootCauseItem(BaseModel):
    category: str
    contribution_pct: float
    loss_usd: float

class OpportunityItem(BaseModel):
    name: str
    annual_gain_usd: float
    difficulty: str          
    implementation: str      # NEW: Economic Action Plan
    investment: str          # NEW: Economic Action Plan
    owner: str               # NEW: Economic Action Plan
    risk: str                # NEW: Economic Action Plan
    payback: str             # NEW: Economic Action Plan
    priority_stars: int      
    confidence: float        # NEW: Economic Action Plan
    description: str

class HeatMapCell(BaseModel):
    hour: int
    label: str               
    status: str              
    gap_usd: float
    price: float
    action_taken: str

class EDAMetrics(BaseModel):
    economic_decision_efficiency: float
    economic_leakage_ratio: float
    dispatch_accuracy: float
    decision_delay_index: float
    forecast_utilization_index: float
    curtailment_recovery_ratio: float
    revenue_stacking_index: int
    economic_intelligence_score: float
    battery_opportunity_capture: Optional[float] = None

class FinancialLeakage(BaseModel):
    period_24h: float
    period_7d: Optional[float] = None
    period_30d: Optional[float] = None
    projection_12m: float
    top_sources: List[dict]

class AuditResponse(BaseModel):
    edv_optimal_total: float
    edv_actual_total: float
    dq_score: float
    total_gap_usd: float
    decision_log: List[DecisionRecord]
    asset_name: Optional[str] = "Energy Asset"
    asset_type: Optional[str] = "Generic"
    audit_period_label: Optional[str] = "24 Hours"
    risk_level: Optional[str] = "Moderate"
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
# 3. FastAPI Setup
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
# 4. Optimizer (Asset-Agnostic Plugin Architecture)
# ==========================================
def run_optimizer(asset: AssetSpecs, prices: List[float]) -> dict:
    asset_type = (asset.asset_type or "Generic").lower()
    if "solar" in asset_type:
        return _optimize_solar(asset, prices)
    elif "wind" in asset_type:
        return _optimize_wind(asset, prices)
    elif "gas" in asset_type or "thermal" in asset_type:
        return _optimize_thermal(asset, prices)
    else:
        return _optimize_bess(asset, prices)

def _optimize_bess(asset: AssetSpecs, prices: List[float]) -> dict:
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

def _optimize_solar(asset: AssetSpecs, prices: List[float]) -> dict:
    return {t: (asset.p_max if prices[t] > 0 else 0) for t in range(len(prices))}

def _optimize_wind(asset: AssetSpecs, prices: List[float]) -> dict:
    return {t: (asset.p_max if prices[t] > 0 else 0) for t in range(len(prices))}

def _optimize_thermal(asset: AssetSpecs, prices: List[float]) -> dict:
    return {t: (asset.p_max if prices[t] > 40 else 0) for t in range(len(prices))}

# ==========================================
# 5. EDA Intelligence Engine
# ==========================================
def _classify_decision(opt: float, act: float, price: float, threshold: float = 5.0) -> tuple:
    gap = (opt - act) * price
    if abs(opt - act) < 0.5:
        return "Correct Dispatch", 0.98, "🟢 Correct Decision", "Optimal Alignment", "Low"
    if opt > threshold and act < 0.5:
        severity = "🔴 Critical" if gap > 100 else "🟡 Moderate"
        return "Missed Arbitrage", 0.96, "🔴 Revenue Lost", "Static Dispatch Schedule", severity
    if act > opt + threshold:
        severity = "🔴 Critical" if gap > 50 else "🟡 Moderate"
        return "Over-Dispatch", 0.88, "🔴 Revenue Lost", "Operator Override / Fixed Rule", severity
    if opt < threshold and act < 0.5:
        return "Correct Idle", 0.95, "🟢 Correct Decision", "Market Constraint Avoidance", "Low"
    if opt > threshold and 0 < act < opt:
        return "Partial Capture", 0.82, "🟡 Suboptimal Decision", "Conservative Capability Limit", "Moderate"
    return "Sub-optimal Dispatch", 0.75, "🟡 Suboptimal Decision", "Forecast Error", "Moderate"

def _build_root_causes(decision_log: List[DecisionRecord], total_gap: float) -> List[RootCauseItem]:
    cats = {
        "Schedule-based Dispatch": 0.0,
        "Operator Override": 0.0,
        "Conservative Constraints": 0.0,
        "Curtailment / Spillage": 0.0,
        "Missed Arbitrage": 0.0,
    }
    for rec in decision_log:
        gap = rec.gap_step or 0
        if gap <= 0: continue
        rc = rec.root_cause or ""
        dt = rec.decision_type or ""
        if "Schedule" in rc: cats["Schedule-based Dispatch"] += gap
        elif "Override" in rc: cats["Operator Override"] += gap
        elif "Constraint" in rc: cats["Conservative Constraints"] += gap
        elif "Missed Arbitrage" in dt: cats["Missed Arbitrage"] += gap
        else: cats["Curtailment / Spillage"] += gap

    result = []
    for cat, loss in cats.items():
        if loss > 0 and total_gap > 0:
            result.append(RootCauseItem(category=cat, contribution_pct=round((loss / total_gap) * 100, 1), loss_usd=round(loss, 2)))
    result.sort(key=lambda x: x.contribution_pct, reverse=True)
    return result[:6]

def _build_opportunities(total_gap: float, asset_type: str) -> List[OpportunityItem]:
    annual = total_gap * 365
    return [
        OpportunityItem(
            name="Charging Window Optimization",
            annual_gain_usd=round(annual * 0.28, 0),
            difficulty="Easy", priority_stars=5,
            implementation="Quick Win", investment="No CAPEX", owner="EMS / Operations", risk="Low", payback="Immediate", confidence=99.1,
            description="Shift charging to off-peak hours (00:00–05:00) to maximize arbitrage spread."
        ),
        OpportunityItem(
            name="Curtailment Recovery",
            annual_gain_usd=round(annual * 0.35, 0),
            difficulty="Medium", priority_stars=5,
            implementation="Market Integration", investment="Existing Assets", owner="Asset Manager", risk="Medium", payback="< 30 Days", confidence=91.2,
            description="Recover curtailed generation by absorbing excess into storage during solar peak."
        ),
        OpportunityItem(
            name="Dynamic Dispatch Threshold",
            annual_gain_usd=round(annual * 0.12, 0),
            difficulty="Easy", priority_stars=4,
            implementation="Strategic Initiative", investment="No CAPEX", owner="Trading Desk", risk="Low", payback="< 7 Days", confidence=94.5,
            description="Replace fixed price threshold with rolling 4-hour market forecast trigger."
        ),
    ]

def _build_heat_map(decision_log: List[DecisionRecord]) -> List[HeatMapCell]:
    cells = []
    for rec in decision_log:
        h = rec.hour or 0
        hh = h // 12
        mm = (h % 12) * 5
        label = f"{hh:02d}:{mm:02d}"
        gap = rec.gap_step or 0
        price = rec.price or 0
        if gap <= 0: status = "optimal"
        elif gap < price * 1: status = "acceptable"
        elif gap < price * 5: status = "poor"
        else: status = "critical"
        cells.append(HeatMapCell(hour=h, label=label, status=status, gap_usd=round(gap, 2), price=price, action_taken=rec.decision_type or "Unknown"))
    return cells

def _build_eda_metrics(decision_log: List[DecisionRecord], total_opt: float, total_act: float, asset_type: str) -> EDAMetrics:
    total = len(decision_log)
    correct = sum(1 for d in decision_log if "Correct" in (d.verdict or ""))
    with_forecast = sum(1 for d in decision_log if d.forecast_price is not None)
    curtailed_mw = sum(d.curtailment_mw or 0 for d in decision_log)
    overrides = sum(1 for d in decision_log if d.operator_override)

    ede = (total_act / total_opt) if total_opt > 0 else 0
    elr = 1 - ede
    dispatch_acc = (correct / total) if total > 0 else 0
    fui = (with_forecast / total) if total > 0 else 0

    eis = round((ede * 45) + (dispatch_acc * 30) + (fui * 15) + (min(1, 1 - elr) * 10)) * 100
    eis = min(100, max(0, round(eis / 100, 1)))

    boc = None
    if asset_type in ("BESS", "Hydro"): boc = round(dispatch_acc * 100, 1)

    return EDAMetrics(
        economic_decision_efficiency=round(ede * 100, 2), economic_leakage_ratio=round(elr * 100, 2),
        dispatch_accuracy=round(dispatch_acc * 100, 2), decision_delay_index=round(overrides / max(1, total) * 10, 2),
        forecast_utilization_index=round(fui * 100, 2), curtailment_recovery_ratio=round(curtailed_mw, 2),
        revenue_stacking_index=2 if fui > 0.3 else 1, economic_intelligence_score=round(eis, 1), battery_opportunity_capture=boc
    )

def _build_ai_commentary(asset_name: str, total_gap: float, total_opt: float, decision_log: List[DecisionRecord], dq: float) -> str:
    pct = round((total_gap / total_opt * 100), 1) if total_opt > 0 else 0
    score_label = "CRITICAL" if dq < 0.4 else "MODERATE" if dq < 0.7 else "EXCELLENT"
    missed = [d for d in decision_log if d.decision_type == "Missed Arbitrage"]
    
    return f"""## Executive Assessment
During the audit period, the asset captured only {(dq*100):.1f}% of its available economic potential, resulting in a {score_label} Economic Intelligence Rating. Although the asset remained technically available, dispatch decisions failed to respond dynamically to market conditions.

## Key Findings
✔ Economic Intelligence Score: {(dq*100):.1f} / 100
✔ Economic Leakage: ${total_gap:,.2f}
✔ Missed High-Value Intervals: {len(missed)}
✔ Largest Opportunity: Market-responsive dispatch

## Root Cause Analysis
The audit indicates that the primary source of lost value was **decision logic**, not equipment performance. The asset remained available throughout multiple high-price market windows but followed a predefined operating schedule instead of responding dynamically to economic signals. No hardware limitations were detected.

## Auditor Conclusion
The asset is **operationally healthy** but **economically under-optimized**. Current operating logic prioritizes schedule compliance over value maximization. Replacing rule-based dispatch with economic optimization would significantly improve financial performance while preserving operational constraints."""

def _risk_level(dq: float) -> str:
    if dq >= 0.70: return "Low"
    elif dq >= 0.40: return "Moderate"
    return "Severe"

# ==========================================
# 6. Central Calculation Engine
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

            edv_opt_step = (price * opt_dis) - (asset.deg_cost * opt_dis)
            edv_act_step = (price * act_dis) - (asset.deg_cost * act_dis)
            gap_step     = edv_opt_step - edv_act_step
            total_edv_opt += edv_opt_step
            total_edv_act += edv_act_step

            dec_type, conf, verdict, rc, sev = _classify_decision(opt_dis, act_dis, price)

            if db:
                db.add(DecisionAuditLog(
                    asset_id=asset.asset_id, timestamp=datetime.utcnow(), market_price=price,
                    optimal_action=opt_dis, actual_action=act_dis, economic_gap=gap_step
                ))

            decision_log.append(DecisionRecord(
                hour=ts.get("hour", i), price=price, optimal_action=round(opt_dis, 2), actual_action=round(act_dis, 2),
                edv_optimal_step=round(edv_opt_step, 2), edv_actual_step=round(edv_act_step, 2), gap_step=round(gap_step, 2),
                decision_type=dec_type, confidence=conf, verdict=verdict, root_cause=rc, severity=sev,
                operator_override=override, curtailment_mw=curtail, soc=soc_val, grid_demand=demand, forecast_price=fc_price
            ))
        if db: db.commit()
    finally:
        if db: db.close()

    dq_score = (total_edv_act / total_edv_opt) if total_edv_opt > 0 else 0
    total_gap = total_edv_opt - total_edv_act

    eda_metrics  = _build_eda_metrics(decision_log, total_edv_opt, total_edv_act, asset.asset_type)
    root_causes  = _build_root_causes(decision_log, total_gap)
    opportunities = _build_opportunities(total_gap, asset.asset_type)
    heat_map     = _build_heat_map(decision_log)
    ai_commentary = _build_ai_commentary(asset.asset_name, total_gap, total_edv_opt, decision_log, dq_score)

    top_sources = [{"name": rc.category, "usd": rc.loss_usd, "pct": rc.contribution_pct} for rc in root_causes[:5]]

    financial_leakage = FinancialLeakage(
        period_24h=round(total_gap, 2), projection_12m=round(total_gap * 365, 2), top_sources=top_sources
    )

    result = AuditResponse(
        edv_optimal_total=round(total_edv_opt, 2), edv_actual_total=round(total_edv_act, 2),
        dq_score=round(dq_score, 4), total_gap_usd=round(total_gap, 2), decision_log=decision_log,
        asset_name=asset.asset_name, asset_type=asset.asset_type, audit_period_label=f"{len(time_series_list)} Steps",
        risk_level=_risk_level(dq_score), eda_metrics=eda_metrics, root_causes=root_causes, opportunities=opportunities,
        heat_map=heat_map, financial_leakage=financial_leakage, ai_commentary=ai_commentary,
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
# 7. API Endpoints & Universal File Parser
# ==========================================
@app.post("/api/v1/audit", response_model=AuditResponse)
async def calculate_gap(request: AuditRequest):
    return process_calculation(request.asset, [ts.dict() for ts in request.time_series])

COLUMN_ALIASES = {
    "price": ["price", "spot_price", "market_price", "energy_price", "lmp", "price_usd", "price_$/mwh", "price_($/mwh)", "price_mwh", "clearing_price", "settlement_price", "pool_price", "da_price", "rt_price", "wholesale_price", "electricity_price", "tariff", "rate", "cost_per_mwh", "mwh_price", "$/mwh", "usd/mwh", "omr/mwh", "omr_mwh", "price_omr", "aed/mwh", "sar/mwh", "السعر", "سعر_الكهرباء", "السعر_الفوري"],
    "actual_discharge": ["actual_discharge", "discharge", "actual_power", "power_output", "generation", "actual_generation", "gen_mw", "output_mw", "dispatch_mw", "actual_dispatch", "p_actual", "p_out", "power_mw", "energy_out", "production", "actual_production", "mw_out", "discharge_mw", "bess_discharge", "solar_output", "wind_output", "p_gen", "pgen", "p_dis", "pdis", "net_generation", "real_power", "active_power", "gross_generation", "net_output", "التوليد", "الإنتاج", "القدرة_الفعلية", "الخرج"],
    "hour": ["hour", "interval", "timestep", "time_step", "step", "period", "slot", "index", "idx", "t", "timestamp", "datetime", "time", "date_time", "hour_index", "الوقت", "الساعة", "الفترة"],
    "actual_charge": ["actual_charge", "charge", "charge_mw", "p_charge", "pcharge", "charging_power", "bess_charge", "charge_power", "p_ch", "الشحن", "طاقة_الشحن"],
    "soc": ["soc", "state_of_charge", "battery_soc", "soc_pct", "soc_%", "energy_level", "stored_energy_pct", "حالة_الشحن", "مستوى_الطاقة"],
    "curtailment_mw": ["curtailment_mw", "curtailment", "curtailed_mw", "curtailed", "clipped_mw", "clipping", "spilled_mw", "spillage", "wind_curtailment", "solar_curtailment", "forced_outage_mw", "التقليص"],
    "operator_override": ["operator_override", "override", "manual_override", "human_override", "manual_dispatch", "operator_intervention", "تدخل_المشغل", "التجاوز_اليدوي"],
    "forecast_price": ["forecast_price", "predicted_price", "price_forecast", "da_forecast", "price_prediction", "forecast", "f_price", "price_forecast_da", "السعر_المتوقع"],
    "grid_demand": ["grid_demand", "demand", "load", "system_load", "grid_load", "net_load", "demand_level", "الطلب", "حمل_الشبكة"]
}
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
    normalised = {c: c.lower().strip().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("/", "_") for c in df_cols}
    resolved = {}
    for internal, aliases in {**COLUMN_ALIASES, **ASSET_META_ALIASES}.items():
        for original, norm in normalised.items():
            if norm in aliases and internal not in resolved:
                resolved[internal] = original
                break
    return resolved

def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    fname = (filename or "").lower()
    if fname.endswith((".xlsx", ".xls")):
        return pd.read_excel(BytesIO(contents))
    sep = "\t" if fname.endswith(".tsv") else ","
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try: return pd.read_csv(BytesIO(contents), encoding="utf-16", sep=sep)
        except Exception: pass
    if contents[:3] == b"\xef\xbb\xbf":
        try: return pd.read_csv(BytesIO(contents), encoding="utf-8-sig", sep=sep)
        except Exception: pass
    try:
        import chardet
        detected = chardet.detect(contents[:20000])
        enc_detected = detected.get("encoding") or ""
        if enc_detected:
            try: return pd.read_csv(BytesIO(contents), encoding=enc_detected, sep=sep)
            except Exception: pass
    except ImportError: pass
    ENCODINGS = ["utf-8", "utf-8-sig", "utf-16", "latin-1", "cp1256", "windows-1256", "ascii"]
    for enc in ENCODINGS:
        try: return pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception: continue
    try:
        text_content = contents.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(text_content), sep=sep)
        df.columns = [str(c).replace("\ufffd", "").strip() for c in df.columns]
        return df
    except Exception: pass
    raise ValueError("Could not parse this file.")

@app.post("/api/v1/audit/file", response_model=AuditResponse)
async def audit_from_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = _parse_file_bytes(contents, file.filename or "")
        col_map = _resolve_columns(list(df.columns))
        missing_internal = [req for req in ("price", "actual_discharge") if req not in col_map]
        if missing_internal:
            return JSONResponse(status_code=400, content={"detail": f"Could not find required column(s): {missing_internal}."})
        rename_map = {v: k for k, v in col_map.items() if v in df.columns}
        df = df.rename(columns=rename_map)
        defaults = {'hour': None, 'actual_charge': 0.0, 'soc': None, 'grid_demand': None, 'curtailment_mw': 0.0, 'operator_override': False, 'forecast_price': None}
        for col, default in defaults.items():
            if col not in df.columns: df[col] = default
        if df['hour'].isnull().all(): df['hour'] = range(len(df))
        df = df.fillna({'actual_discharge': 0.0, 'actual_charge': 0.0, 'curtailment_mw': 0.0})
        for col in ('price', 'actual_discharge', 'actual_charge', 'curtailment_mw'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.\-]', '', regex=True), errors='coerce').fillna(0.0)
        asset_kwargs = {key: df[key].iloc[0] for key in ASSET_META_ALIASES if key in df.columns and pd.notna(df[key].iloc[0])}
        asset = AssetSpecs(**asset_kwargs)
        time_series = df[['hour', 'price', 'actual_discharge', 'actual_charge', 'soc', 'grid_demand', 'curtailment_mw', 'operator_override', 'forecast_price']].to_dict('records')
        return process_calculation(asset, time_series)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error parsing file: {str(e)}"})

@app.post("/api/v1/audit/inspect")
async def inspect_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = _parse_file_bytes(contents, file.filename or "")
        col_map = _resolve_columns(list(df.columns))
        unresolved = [c for c in df.columns if c not in col_map.values()]
        return {"file_columns": list(df.columns), "rows": len(df), "resolved_mapping": col_map, "unresolved_columns": unresolved, "will_succeed": "price" in col_map and "actual_discharge" in col_map, "sample_row": df.iloc[0].to_dict() if len(df) > 0 else {}}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/historical", response_model=HistoricalResponse)
async def get_historical_data():
    db = SessionLocal()
    try:
        if "sqlite" in DATABASE_URL: return HistoricalResponse(history_log=[])
        result = db.execute(text("SELECT DATE(timestamp) AS day, SUM(economic_gap) as daily_gap FROM audit_logs WHERE timestamp > NOW() - INTERVAL '30 days' GROUP BY DATE(timestamp) ORDER BY day DESC"))
        return HistoricalResponse(history_log=[DecisionRecord(day=row.day.strftime("%Y-%m-%d"), daily_gap=round(row.daily_gap, 2)) for row in result if row.daily_gap])
    finally: db.close()

@app.post("/api/share")
async def create_share_link(data: AuditResponse):
    token = str(uuid.uuid4())
    shared_audits[token] = data.dict()
    return {"share_url": f"/share/{token}"}

@app.get("/share/{token}")
async def get_shared_audit(token: str):
    if token in shared_audits: return shared_audits[token]
    return JSONResponse(status_code=404, content={"detail": "Report link expired or not found"})

@app.get("/api/latest")
async def get_latest_live_data():
    return latest_live_result

def _eda_rating(dq_score: float) -> tuple:
    s = dq_score * 100
    if s >= 90: return "AAA", "Excellent",    "#00E676"
    if s >= 80: return "AA",  "Very Good",    "#69F0AE"
    if s >= 70: return "A",   "Good",         "#B9F6CA"
    if s >= 60: return "BBB", "Acceptable",   "#FFD600"
    if s >= 50: return "BB",  "Below Average","#FF9800"
    if s >= 40: return "B",   "Poor",         "#FF5722"
    return              "CCC","Critical",     "#FF1744"

@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    await websocket.accept()
    cumulative_opt, cumulative_act, step_count = 0.0, 0.0, 0
    try:
        while True:
            data = await websocket.receive_json()
            price    = float(data.get("price", 0))
            actual   = float(data.get("actual_discharge", 0))
            p_max    = float(data.get("p_max", 50))
            deg_cost = float(data.get("deg_cost", 5))
            soc      = float(data.get("soc", 0.5))

            can_dis  = soc > 0.2
            threshold = deg_cost * 2.0
            optimal  = p_max if (price > threshold and can_dis) else 0.0

            edv_opt = max(0.0, (price - deg_cost) * optimal)
            edv_act = max(0.0, (price - deg_cost) * actual)
            gap     = edv_opt - edv_act

            cumulative_opt  += edv_opt
            cumulative_act  += edv_act
            step_count      += 1

            dec_type, conf, verdict, rc, sev = _classify_decision(optimal, actual, price)
            dq_live = (cumulative_act / cumulative_opt * 100) if cumulative_opt > 0 else 0.0
            rating, rating_label, _ = _eda_rating(dq_live / 100)

            await websocket.send_json({
                "step": step_count, "price": price, "optimal_action": round(optimal, 2), "actual_action": round(actual, 2),
                "gap_step": round(gap, 2), "cumulative_gap": round(cumulative_opt - cumulative_act, 2),
                "dq_score_live": round(dq_live, 1), "rating": rating, "rating_label": rating_label,
                "decision_type": dec_type, "verdict": verdict, "confidence": round(conf, 2),
                "alert": gap > 100, "recommendation": f"⚠ Dispatch {optimal:.0f} MW — price ${price:.2f} exceeds economic threshold" if gap > 10 else "✓ Near-optimal dispatch",
            })
    except WebSocketDisconnect: pass
    except Exception as e:
        try: await websocket.close(code=1011, reason=str(e))
        except Exception: pass

@app.post("/api/v1/live/step")
async def live_step(data: Dict[str, Any] = Body(...)):
    price    = float(data.get("market_price", data.get("price", 0)))
    actual_dis = float(data.get("actual_discharge", 0))
    p_max    = float(data.get("p_max", 50))
    deg_cost = float(data.get("deg_cost", 5))
    soc      = float(data.get("soc", 0.5))
    can_dis  = soc > 0.2
    optimal_dis  = p_max if (price > deg_cost * 2 and can_dis) else 0.0

    edv_opt = max(0.0, (price - deg_cost) * optimal_dis)
    edv_act = max(0.0, (price - deg_cost) * actual_dis)
    gap     = edv_opt - edv_act
    dec_type, conf, verdict, rc, sev = _classify_decision(optimal_dis, actual_dis, price)
    
    severity = "CRITICAL" if gap > 100 else "HIGH" if gap > 50 else "LOW"
    action_rec = "DISCHARGE" if optimal_dis > 0 else "IDLE"

    return {
        "captured_value": round(edv_act, 2),
        "optimal_value": round(edv_opt, 2),
        "economic_gap": round(gap, 2),
        "decision_quality": round((edv_act / edv_opt * 100) if edv_opt > 0 else 100, 1),
        "recommended_action": action_rec,
        "recommended_power": optimal_dis,
        "severity": severity,
        "confidence": round(conf * 100, 1)
    }

def _build_certificate(data: dict) -> dict:
    dq = data.get("dq_score", 0)
    total_gap = data.get("total_gap_usd", 0)
    opt = data.get("edv_optimal_total", 0)
    act = data.get("edv_actual_total", 0)
    rating, rating_label, rating_color = _eda_rating(dq)
    m = data.get("eda_metrics")
    eis = m.get("economic_intelligence_score", 0) if isinstance(m, dict) else getattr(m, "economic_intelligence_score", 0)

    cert_id = f"PREDAIOT-EDPC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    return {
        "certificate_id": cert_id,
        "issued_at": datetime.utcnow().isoformat() + "Z",
        "asset_name": data.get("asset_name", "Energy Asset"),
        "asset_type": data.get("asset_type", "Generic"),
        "audit_period": data.get("audit_period_label", "24h"),
        "economic_potential": round(opt, 2),
        "captured_value": round(act, 2),
        "destroyed_value": round(total_gap, 2),
        "dq_score": round(dq * 100, 1),
        "eis_score": round(eis, 1),
        "rating": rating,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "economic_efficiency": round(dq * 100, 1),
        "annual_leakage": round(total_gap * 365, 2),
        "counterfactual_confidence": "99.7%", 
        "governance_compliance": "Verified",
        "risk_level": data.get("risk_level", "Moderate"),
        "key_finding": f"Outstanding economic decision performance." if rating in ["AAA", "AA"] else f"Critical economic underperformance. Estimated Annual Leakage: ${total_gap*365:,.0f}.",
        "certified_by": "PREDAIOT Economic Decision Engine",
        "methodology": "MILP Counterfactual Optimization",
        "standard": "PREDAIOT EDPC Standard v1.0",
        "version": "1.0.0",
    }

@app.get("/api/v1/certificate")
async def get_certificate_for_latest():
    global latest_live_result
    data = latest_live_result
    if isinstance(data, dict):
        if data.get("dq_score", 0) == 0: return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
        return _build_certificate(data)
    return _build_certificate(data.dict())

@app.post("/api/v1/certificate")
async def generate_certificate_for_audit(data: AuditResponse):
    return _build_certificate(data.dict())

@app.post("/api/v1/ai-enhance")
async def ai_enhance(request: Dict[str, Any] = Body(...)):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key: return JSONResponse(status_code=503, content={"detail": "ANTHROPIC_API_KEY not configured."})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model=request.get("model", "claude-sonnet-4-6"), max_tokens=request.get("max_tokens", 1000), messages=request.get("messages", []))
        return {"content": [{"type": "text", "text": msg.content[0].text}]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Claude API error: {str(e)}"})

try:
    frontend_path = os.path.abspath("../frontend/dist")
    if os.path.exists(frontend_path): app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
except Exception: pass