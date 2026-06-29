import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import pulp
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# ==========================================
# 1. إعداد قاعدة البيانات (سحابية Aiven أو محلية للتجربة)
# ==========================================
# في السحابة (Render)، سيقرأ الرابط من متغيرات البيئة. محلياً يستخدم SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./predaiot_audit.db")

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # إعدادات خاصة لـ PostgreSQL/TimescaleDB في السحابة
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DecisionAuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow) # حاسم للتاريخ
    market_price = Column(Float)
    optimal_action = Column(Float)
    actual_action = Column(Float)
    economic_gap = Column(Float)

# إنشاء الجداول
Base.metadata.create_all(bind=engine)

# ==========================================
# 2. هياكل البيانات (Models)
# ==========================================
class AssetSpecs(BaseModel):
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

class AuditRequest(BaseModel):
    asset: AssetSpecs
    time_series: List[TimeStepData]

class DecisionRecord(BaseModel):
    hour: Optional[str] = None
    day: Optional[str] = None # مخصص لبيانات التاريخ
    price: Optional[float] = None
    optimal_action: Optional[float] = None
    actual_action: Optional[float] = None
    edv_optimal_step: Optional[float] = None
    edv_actual_step: Optional[float] = None
    gap_step: Optional[float] = None
    daily_gap: Optional[float] = None # إجمالي الفجوة اليومية

class AuditResponse(BaseModel):
    edv_optimal_total: float
    edv_actual_total: float
    dq_score: float
    total_gap_usd: float
    decision_log: List[DecisionRecord]

class HistoricalResponse(BaseModel):
    history_log: List[DecisionRecord]

# ==========================================
# 3. إعداد FastAPI
# ==========================================
app = FastAPI(title="PREDAIOT Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ذاكرة مؤقتة للبيانات الحية
latest_live_result = {
    "edv_optimal_total": 0, 
    "edv_actual_total": 0, 
    "dq_score": 0, 
    "total_gap_usd": 0, 
    "decision_log": []
}

# ==========================================
# 4. محرك التحسين (MILP)
# ==========================================
def run_optimizer(asset: AssetSpecs, prices: List[float]) -> dict:
    hours = range(len(prices))
    prob = pulp.LpProblem("PREDAIOT_MILP", pulp.LpMaximize)
    
    p_dis = pulp.LpVariable.dicts("Discharge", hours, lowBound=0, upBound=asset.p_max)
    p_ch = pulp.LpVariable.dicts("Charge", hours, lowBound=0, upBound=asset.p_max)
    soc = pulp.LpVariable.dicts("SOC", hours, lowBound=0.1, upBound=0.95)
    is_dis = pulp.LpVariable.dicts("IsDis", hours, cat='Binary')

    prob += pulp.lpSum([(prices[t] * p_dis[t]) - (prices[t] * p_ch[t]) - (asset.deg_cost * p_dis[t]) for t in hours])

    for t in hours:
        prob += p_dis[t] <= asset.p_max * is_dis[t]
        prob += p_ch[t] <= asset.p_max * (1 - is_dis[t])
        
        if t == 0:
            prob += soc[t] == asset.soc_init + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        else:
            prob += soc[t] == soc[t-1] + (p_ch[t] * asset.eta_ch - p_dis[t] / asset.eta_dis) / asset.e_max
        
        # قيد إلزامي: يجب أن تعود البطارية لنفس حالة الشحن في نهاية الـ 24 ساعة
        if t == max(hours):
            prob += soc[t] == asset.soc_init

    prob.solve()
    
    return {t: p_dis[t].varValue for t in hours}

# ==========================================
# 5. نقطة نهاية التدقيق (تخزين كل نقطة بيانات في التاريخ)
# ==========================================
@app.post("/api/v1/audit", response_model=AuditResponse)
async def calculate_gap(request: AuditRequest):
    global latest_live_result
    
    asset = request.asset
    prices = [ts.price for ts in request.time_series]
    optimal_actions = run_optimizer(asset, prices)
    
    total_edv_opt = 0
    total_edv_act = 0
    decision_log = []
    db = SessionLocal()
    
    for i, ts in enumerate(request.time_series):
        opt_dis = optimal_actions[i] if optimal_actions[i] else 0
        act_dis = ts.actual_discharge
        
        edv_opt_step = (ts.price * opt_dis) - (asset.deg_cost * opt_dis)
        edv_act_step = (ts.price * act_dis) - (asset.deg_cost * act_dis)
        gap_step = edv_opt_step - edv_act_step
        
        total_edv_opt += edv_opt_step
        total_edv_act += edv_act_step
        
        # حفظ كل نقطة في قاعدة البيانات بختم زمني حقيقي لتشكيل التاريخ
        log_entry = DecisionAuditLog(
            asset_id="BESS_01",
            timestamp=datetime.utcnow(), 
            market_price=ts.price,
            optimal_action=opt_dis,
            actual_action=act_dis,
            economic_gap=gap_step
        )
        db.add(log_entry)
        
        decision_log.append(DecisionRecord(
            hour=ts.hour, price=ts.price, optimal_action=round(opt_dis,2), 
            actual_action=round(act_dis,2), edv_optimal_step=round(edv_opt_step,2),
            edv_actual_step=round(edv_act_step,2), gap_step=round(gap_step,2)
        ))
        
    db.commit()
    db.close()
    
    dq_score = (total_edv_act / total_edv_opt) if total_edv_opt > 0 else 0
    
    # تحديث الذاكرة المؤقتة
    latest_live_result = AuditResponse(
        edv_optimal_total=round(total_edv_opt,2), 
        edv_actual_total=round(total_edv_act,2),
        dq_score=round(dq_score,4), 
        total_gap_usd=round(total_edv_opt - total_edv_act, 2),
        decision_log=decision_log
    )
    
    return latest_live_result

# ==========================================
# 6. نقطة نهاية التاريخ (جلب 30 يوم من قاعدة البيانات السحابية)
# ==========================================
@app.get("/api/historical", response_model=HistoricalResponse)
async def get_historical_data():
    db = SessionLocal()
    try:
        # إذا كنا نعمل محلياً بـ SQLite، لا نرجع بيانات تاريخية لتجنب الأخطاء
        if "sqlite" in DATABASE_URL:
            return HistoricalResponse(history_log=[])
            
        # استعلام PostgreSQL القياسي (يعمل بسرعة فائقة بدون إضافات)
        query = text("""
            SELECT 
                DATE(timestamp) AS day, 
                SUM(economic_gap) as daily_gap
            FROM audit_logs 
            WHERE timestamp > NOW() - INTERVAL '30 days'
            GROUP BY DATE(timestamp) 
            ORDER BY day DESC
        """)
        
        result = db.execute(query)
        
        history_log = []
        for row in result:
            if row.daily_gap:
                history_log.append(DecisionRecord(
                    day=row.day.strftime("%Y-%m-%d"),
                    daily_gap=round(row.daily_gap, 2)
                ))
                
        return HistoricalResponse(history_log=history_log)
    finally:
        db.close()

# ==========================================
# 7. نقطة نهاية البيانات الحية (لجسر الـ SCADA)
# ==========================================
@app.get("/api/latest")
async def get_latest_live_data():
    return latest_live_result

# ==========================================
# 8. دمج الواجهة الأمامية
# ==========================================
try:
    frontend_path = os.path.abspath("../frontend/dist")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
except Exception:
    pass