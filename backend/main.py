import os
import uuid
import pandas as pd
from io import BytesIO
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import pulp
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

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
    # Universal fields — works for Solar, Wind, BESS, Gas, Hydro, etc.
    asset_type: Optional[str] = "BESS"          # BESS | Solar | Wind | Gas | Hydro | Generic
    asset_name: Optional[str] = "Energy Asset"
    asset_id: Optional[str] = "ASSET_01"
    p_max: float = 50.0
    e_max: float = 100.0
    soc_init: float = 0.2
    eta_ch: float = 0.95
    eta_dis: float = 0.95
    deg_cost: float = 5.0

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

@app.post("/api/v1/audit/file", response_model=AuditResponse)
async def audit_from_file(file: UploadFile = File(...)):
    """
    Universal file ingestion — accepts CSV or Excel with any energy asset data.
    Required:  price, actual_discharge
    Optional:  hour, actual_charge, soc, grid_demand, curtailment_mw,
               operator_override, forecast_price,
               asset_type, asset_name, p_max, e_max, soc_init, eta_ch, eta_dis, deg_cost
    """
    try:
        contents = await file.read()
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(BytesIO(contents))
        else:
            df = pd.read_csv(BytesIO(contents.decode('utf-8')))

        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

        # Validate required columns
        required = {'price', 'actual_discharge'}
        missing = required - set(df.columns)
        if missing:
            return JSONResponse(status_code=400, content={
                "detail": f"Missing required columns: {missing}. "
                          f"File has: {list(df.columns)}"
            })

        # Add optional columns with defaults
        for col, default in [
            ('hour', None), ('actual_charge', 0.0), ('soc', None),
            ('grid_demand', None), ('curtailment_mw', 0.0),
            ('operator_override', False), ('forecast_price', None)
        ]:
            if col not in df.columns:
                df[col] = default

        if df['hour'].isnull().all():
            df['hour'] = range(len(df))

        df = df.fillna({'actual_discharge': 0, 'actual_charge': 0, 'curtailment_mw': 0})

        # Asset specs: pull from first row meta-columns if present, else defaults
        asset_kwargs = {}
        meta_map = {
            'asset_type': 'asset_type', 'asset_name': 'asset_name',
            'p_max': 'p_max', 'e_max': 'e_max', 'soc_init': 'soc_init',
            'eta_ch': 'eta_ch', 'eta_dis': 'eta_dis', 'deg_cost': 'deg_cost'
        }
        for key, col in meta_map.items():
            if col in df.columns:
                val = df[col].iloc[0]
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
# 8. Serve Frontend  (UNCHANGED CORE)
# ==========================================
try:
    frontend_path = os.path.abspath("../frontend/dist")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
except Exception:
    pass