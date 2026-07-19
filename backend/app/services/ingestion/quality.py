# -*- coding: utf-8 -*-
"""Data-quality assessment — sensor-quality flags, DQ counts, DQI components, and
forecast reliability computed from the cleaned frame/manifest.

Public API: _build_sensor_quality_flags, _collect_data_quality_counts,
_dqi_components_from_manifest, _forecast_reliability_from_snapshot.
Dependencies: ingestion._primitives (_normalise_col). Extracted VERBATIM.
"""
import io  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import re  # noqa: F401
from io import BytesIO, StringIO  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

import eda_metrics  # noqa: F401

from app.core.constants import (  # noqa: F401
    _STANDARD_INTERVALS, _COMMS_STATUS_ALIASES, _COMMS_OK_VALUES,
)

from app.services.ingestion._primitives import _dq, _normalise_col  # noqa: F401


def _build_sensor_quality_flags(df: pd.DataFrame, dt_hours: float,
                                p_max: float, e_max: float) -> list:
    """
    Read-only plausibility checks on the (renamed) frame. Nothing here mutates
    data — these flags exist so the operator knows which windows to distrust.
    """
    flags = []
    n_rows = len(df)

    # 1. Comms dropouts (TIMEOUT / LOST / OFFLINE windows → stale sensor values)
    comms_col = next(
        (c for c in df.columns if _normalise_col(str(c)) in _COMMS_STATUS_ALIASES), None)
    if comms_col is not None and n_rows:
        vals = df[comms_col].astype(str).str.strip().str.lower()
        bad = vals[~vals.isin(_COMMS_OK_VALUES) & (vals != "nan")]
        if len(bad):
            top = ", ".join(f"{v.upper()}×{c}" for v, c in bad.value_counts().head(3).items())
            flags.append(_dq("warning", "comms_dropouts",
                             f"{len(bad)} of {n_rows} steps report a degraded telemetry link "
                             f"({top}). Sensor values in those windows may be stale; they are "
                             "included in the audit but step-level attributions there should "
                             "be treated with caution."))

    # 2. SoC physics: a p_max MW converter on an e_max MWh pack can move at most
    #    p_max·dt/e_max of SoC per step. Bigger jumps = batch-updated SoC sensor.
    if "soc" in df.columns and e_max and e_max > 0:
        soc = pd.to_numeric(df["soc"], errors="coerce").dropna()
        if len(soc) >= 3:
            soc_pct = soc * 100.0 if float(soc.abs().max()) <= 1.5 else soc
            max_step_pct = (p_max * dt_hours / e_max) * 100.0
            viol = int((soc_pct.diff().abs() > max_step_pct * 1.5).sum())
            if viol:
                flags.append(_dq("warning", "soc_physics_violation",
                                 f"{viol} SoC step change(s) exceed what a {p_max:g} MW converter on a "
                                 f"{e_max:g} MWh pack can physically move in one step (max "
                                 f"{max_step_pct:.1f}%/step). The SCADA SoC register is likely "
                                 "batch-updated; the audit relies on the power columns, SoC is advisory."))

    # 3. Frozen price feed: identical price for ≥ 2 hours straight suggests a
    #    stuck market-data link, not a real market.
    if "price" in df.columns and n_rows:
        pr = pd.to_numeric(df["price"], errors="coerce")
        run_ids = (pr != pr.shift()).cumsum()
        longest = int(run_ids.value_counts().max()) if pr.notna().any() else 0
        freeze_threshold = max(3, int(round(2.0 / max(dt_hours, 1e-9))))
        if longest >= freeze_threshold:
            flags.append(_dq("warning", "price_feed_frozen",
                             f"The price column repeats the same value for {longest} consecutive "
                             "steps (≥ 2 hours) — the market feed may have been frozen in that window."))
        n_neg = int((pr < 0).sum())
        if n_neg:
            flags.append(_dq("info", "negative_prices",
                             f"{n_neg} step(s) have negative prices — legitimate in some markets; "
                             "the audit treats them as real."))

    return flags

def _collect_data_quality_counts(snap: pd.DataFrame, p_max: float, e_max: float,
                                 dt_hours: float, has_forecast_col: bool,
                                 col_map: dict) -> dict:
    """
    READ-ONLY, DETERMINISTIC extraction of the integer evidence the Data
    Quality Index is derived from. Operates on a snapshot of the renamed
    frame taken AFTER timestamp parsing but BEFORE the mutating pipeline
    (dedupe / coercion / resample), so the counts describe the dataset the
    customer actually supplied. Nothing here mutates `snap`.

    Asset-agnostic: SoC / telemetry / forecast counts are None when the
    corresponding column is absent — those DQI dimensions then become N/A.

    Returns the Data Quality Manifest (raw counts + metadata). Every DQI
    number is reproducible from these integers via eda_metrics.
    """
    n_rows = int(len(snap))
    mf = {
        "manifest_version": "1.0",
        "n_rows_raw": n_rows,
        # timestamps
        "has_timestamps": False, "n_expected_steps": None, "n_present_steps": None,
        "n_missing_steps": None, "n_unparseable_timestamps": 0,
        "n_duplicate_timestamps": 0, "n_out_of_order_timestamps": 0,
        "detected_interval_sec": None, "timezone_assumed": None, "span_hours": None,
        # price (required)
        "n_price_missing_interpolated": 0, "n_negative_price_steps": 0,
        # sensor (asset-specific → may be None)
        "n_soc_present": None, "n_soc_physics_violations": None,
        # telemetry (may be None)
        "n_telemetry_rows": None, "n_telemetry_degraded": None,
        # forecast (may be None)
        "n_forecast_present": None,
    }

    # ── Timestamps ──────────────────────────────────────────────────────────
    hour = snap["hour"] if "hour" in snap.columns else None
    if hour is not None and pd.api.types.is_datetime64_any_dtype(hour):
        mf["has_timestamps"] = True
        n_unparseable = int(hour.isna().sum())
        valid = hour.dropna()
        mf["n_unparseable_timestamps"] = n_unparseable
        mf["n_present_steps"] = int(len(valid))
        if len(valid) >= 2:
            deltas = valid.diff().dt.total_seconds().dropna()
            mf["n_out_of_order_timestamps"] = int((deltas < 0).sum())
            mf["n_duplicate_timestamps"] = int(valid.duplicated().sum())
            pos = deltas[deltas > 0]
            interval = float(pos.median()) if len(pos) else None
            mf["detected_interval_sec"] = round(interval, 3) if interval else None
            span = float((valid.max() - valid.min()).total_seconds())
            mf["span_hours"] = round(span / 3600.0, 4)
            if interval and interval > 0:
                mf["n_expected_steps"] = int(round(span / interval)) + 1
                mf["n_missing_steps"] = max(0, mf["n_expected_steps"] - mf["n_present_steps"])
        try:
            tz = valid.dt.tz
            mf["timezone_assumed"] = str(tz) if tz is not None else "naive/UTC"
        except Exception:
            mf["timezone_assumed"] = None

    # ── Price (required column) ─────────────────────────────────────────────
    if "price" in snap.columns:
        num = pd.to_numeric(snap["price"].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
                            errors="coerce")
        mf["n_price_missing_interpolated"] = int(num.isna().sum())
        mf["n_negative_price_steps"] = int((num < 0).sum())

    # ── Sensor validity (SoC physics — only when a SoC column was supplied) ──
    if "soc" in col_map and "soc" in snap.columns and e_max and e_max > 0:
        soc = pd.to_numeric(snap["soc"], errors="coerce").dropna()
        if len(soc) >= 3:
            soc_pct = soc * 100.0 if float(soc.abs().max()) <= 1.5 else soc
            max_step_pct = (p_max * dt_hours / e_max) * 100.0
            mf["n_soc_present"] = int(len(soc))
            mf["n_soc_physics_violations"] = int((soc_pct.diff().abs() > max_step_pct * 1.5).sum())

    # ── Telemetry health (only when a comms-status column was supplied) ──────
    comms_col = next((c for c in snap.columns
                      if _normalise_col(str(c)) in _COMMS_STATUS_ALIASES), None)
    if comms_col is not None and n_rows:
        vals = snap[comms_col].astype(str).str.strip().str.lower()
        mf["n_telemetry_rows"] = n_rows
        mf["n_telemetry_degraded"] = int((~vals.isin(_COMMS_OK_VALUES) & (vals != "nan")).sum())

    # ── Forecast availability (only when a forecast column was supplied) ─────
    if has_forecast_col and "forecast_price" in snap.columns:
        mf["n_forecast_present"] = int(pd.to_numeric(snap["forecast_price"], errors="coerce").notna().sum())

    return mf

def _dqi_components_from_manifest(mf: dict) -> dict:
    """Deterministically map manifest counts → the six DQI components (N/A-aware)."""
    n = mf.get("n_rows_raw")
    has_ts = mf.get("has_timestamps")
    return {
        "completeness": eda_metrics.completeness(
            mf.get("n_present_steps"), mf.get("n_expected_steps")),
        "timestamp_integrity": eda_metrics.timestamp_integrity(
            (n if has_ts else None), mf.get("n_unparseable_timestamps", 0),
            mf.get("n_duplicate_timestamps", 0)),
        "sensor_validity": eda_metrics.sensor_validity(
            mf.get("n_soc_present"), mf.get("n_soc_physics_violations") or 0),
        "telemetry_health": eda_metrics.telemetry_health(
            mf.get("n_telemetry_rows"), mf.get("n_telemetry_degraded") or 0),
        "price_integrity": eda_metrics.price_integrity(
            n, mf.get("n_price_missing_interpolated", 0)),
        "forecast_availability": eda_metrics.forecast_availability(
            (n if mf.get("n_forecast_present") is not None else None),
            mf.get("n_forecast_present")),
    }

def _forecast_reliability_from_snapshot(snap: pd.DataFrame, has_forecast_col: bool) -> Optional[dict]:
    """MAPE of a supplied forecast vs realized price → Forecast Reliability (report-only)."""
    if not has_forecast_col or "forecast_price" not in snap.columns or "price" not in snap.columns:
        return None
    f = pd.to_numeric(snap["forecast_price"], errors="coerce")
    p = pd.to_numeric(snap["price"].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce")
    mask = f.notna() & p.notna()
    if int(mask.sum()) < 2:
        return None
    denom = p[mask].abs().clip(lower=1e-9)
    mape = float(((f[mask] - p[mask]).abs() / denom).mean())
    return eda_metrics.forecast_reliability(mape)
