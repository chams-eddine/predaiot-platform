import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pulp
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# ==========================================
# 1. إعداد قاعدة البيانات (متوافق مع السحابة)
# ==========================================
basedir = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URL = "sqlite:///" + os.path.join(basedir, "predaiot_audit.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
# 2. هياكل البيانات
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
    hour: int
    price: float
    optimal_action: float
    actual_action: float
    edv_optimal_step: float