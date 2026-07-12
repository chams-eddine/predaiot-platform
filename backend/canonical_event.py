# -*- coding: utf-8 -*-
"""
Canonical Economic Event (EDA-EVENT-1.0) — the single normalization contract.

EVERY data source (OPC-UA, Modbus, MQTT, CSV, REST, future connectors) must
normalize into this schema BEFORE any processing. No processing logic may
depend on a connector-specific payload. Pure module: no I/O, no framework.

Canonical event fields:
  event_id       deterministic id (dedup key)
  stream_id      the source stream
  source         opcua | modbus | mqtt | csv | rest | sim
  timestamp      ISO-8601 UTC
  spot_price     market price (currency/MWh)
  actual_charge  MW charged  (default 0)
  actual_discharge MW discharged (default 0)
  soc_percent    state of charge %, optional
  forecast_price optional
  currency
"""
import hashlib
from typing import Any, Dict, List, Optional

CANONICAL_EVENT_VERSION = "EDA-EVENT-1.0"
SOURCE_TYPES = ("opcua", "modbus", "mqtt", "csv", "rest", "sim")


def _f(v, default=None):
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def normalize_event(raw: Dict[str, Any], stream_id: str, source: str,
                    currency: str = "USD") -> Dict[str, Any]:
    """
    Normalize ANY connector reading into a Canonical Economic Event.
    `raw` uses the canonical field names already (connectors map to them);
    unknown keys are ignored. event_id is derived deterministically so
    duplicate deliveries dedup to the same event.
    """
    ts = str(raw.get("timestamp") or "")
    spot = _f(raw.get("spot_price"))
    charge = _f(raw.get("actual_charge"), 0.0)
    discharge = _f(raw.get("actual_discharge"), 0.0)
    key = f"{stream_id}|{ts}|{spot}|{charge}|{discharge}"
    event_id = raw.get("event_id") or "EV-" + hashlib.sha256(key.encode()).hexdigest()[:20]
    return {
        "event_id": event_id,
        "version": CANONICAL_EVENT_VERSION,
        "stream_id": stream_id,
        "source": source if source in SOURCE_TYPES else "rest",
        "timestamp": ts,
        "spot_price": spot,
        "actual_charge": charge,
        "actual_discharge": discharge,
        "soc_percent": _f(raw.get("soc_percent")),
        "forecast_price": _f(raw.get("forecast_price")),
        "currency": currency,
    }


def event_is_valid(ev: Dict[str, Any]) -> bool:
    """A usable economic event needs a timestamp and a numeric price."""
    return bool(ev.get("timestamp")) and ev.get("spot_price") is not None


def to_time_step(ev: Dict[str, Any], hour_index: int) -> Dict[str, Any]:
    """
    Map a Canonical Economic Event to the EXISTING audit engine's time-step
    schema (TimeStepData). This is the ONLY bridge into Layer 2 — the live path
    reuses the certified engine, it does not re-implement any economics.
    """
    return {
        "hour": hour_index,
        "price": ev.get("spot_price") or 0.0,
        "actual_charge": ev.get("actual_charge") or 0.0,
        "actual_discharge": ev.get("actual_discharge") or 0.0,
        "soc": ev.get("soc_percent"),
        "forecast_price": ev.get("forecast_price"),
    }


def build_window(events: List[Dict[str, Any]], max_len: int = 48) -> List[Dict[str, Any]]:
    """
    Rolling window: dedup by event_id, order by timestamp (late-event safe),
    keep the most recent max_len events.
    """
    seen = {}
    for ev in events:
        seen[ev["event_id"]] = ev            # last write wins on dup id
    ordered = sorted(seen.values(), key=lambda e: (e.get("timestamp") or "", e["event_id"]))
    return ordered[-max_len:]


def window_manifest(window: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Window manifest + evidence hash over the ordered canonical events."""
    body = "|".join(f"{e['event_id']}:{e.get('timestamp')}:{e.get('spot_price')}:"
                    f"{e.get('actual_charge')}:{e.get('actual_discharge')}" for e in window)
    return {
        "n_events": len(window),
        "window_start": window[0].get("timestamp") if window else None,
        "window_end": window[-1].get("timestamp") if window else None,
        "evidence_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "version": CANONICAL_EVENT_VERSION,
    }
