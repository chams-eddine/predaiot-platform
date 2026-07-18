# -*- coding: utf-8 -*-
"""Access-log middleware characterization: proves app/core/logging.py still
records one APIAccessLog row per /api/v1/* request after the extraction."""
import main
from app.models import APIAccessLog


def _count():
    db = main.SessionLocal()
    try:
        return db.query(APIAccessLog).count()
    finally:
        db.close()


def test_access_log_records_api_request(client):
    before = _count()
    r = client.post("/api/v1/trial/start", json={"email": "log-mw@preda-iot.com"})
    assert r.status_code == 200
    assert _count() > before, "access-log middleware did not record the request"


def test_security_headers_present(client):
    # the sibling middleware (kept in main.py) must still run
    h = {k.lower(): v for k, v in client.get("/health").headers.items()}
    assert h.get("x-frame-options") == "DENY"
    assert h.get("x-content-type-options") == "nosniff"
