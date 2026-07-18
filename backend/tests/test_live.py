# -*- coding: utf-8 -*-
"""Live-stream characterization: counter exactness, malformed-frame recovery,
and network-drop resume."""
import math


def _frame(i):
    price = 40 + 45 * math.sin(i / 12)
    return {"market_price": round(price, 2), "actual_discharge": 20.0 if price > 55 else 0.0,
            "soc": 0.5, "p_max": 50, "e_max": 100}


def test_burst_counter_exact(client):
    with client.websocket_connect("/ws/live") as ws:
        last = None
        for i in range(120):
            ws.send_json(_frame(i)); last = ws.receive_json()
        assert last["step"] == 120
        assert math.isfinite(last["cumulative_gap"])


def test_malformed_frame_recovers(client):
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(_frame(0)); ws.receive_json()      # step 1
        ws.send_text("{ not json ]")
        assert "error" in ws.receive_json()             # ignored, no increment
        ws.send_json(_frame(1))
        assert ws.receive_json()["step"] == 2           # session continues


def test_resume_after_drop(client):
    with client.websocket_connect("/ws/live") as ws:
        last = None
        for i in range(50):
            ws.send_json(_frame(i)); last = ws.receive_json()
        saved = {"cumulative_opt": last["cumulative_opt"],
                 "cumulative_act": last["cumulative_act"], "step": last["step"]}
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({**_frame(50), "resume": saved})
        first = ws.receive_json()
        assert first["step"] == 51
        assert first["cumulative_opt"] >= saved["cumulative_opt"]


def test_rest_step_fallback(client):
    r = client.post("/api/v1/live/step", json=_frame(5))
    assert r.status_code == 200 and "recommendation" in r.json()
