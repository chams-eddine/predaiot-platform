# -*- coding: utf-8 -*-
"""Database engine & session configuration.

Extracted verbatim from main.py (refactor step 2A) — CORE LOGIC UNCHANGED,
connection made fault-tolerant upstream. No app/business imports, so this module
sits at the bottom of the dependency graph and can be imported anywhere.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./predaiot_audit.db")

# Render's managed Postgres sometimes gives "postgres://" — SQLAlchemy 2.x needs "postgresql://"
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Consultation booking CTA target (env-overridable) — surfaced by the trial gate.
CONSULTATION_BOOKING_URL = os.environ.get(
    "CONSULTATION_BOOKING_URL",
    "mailto:chams@preda-iot.com?subject=PREDAIOT%20Audit%20Consultation"
)
