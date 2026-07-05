# -*- coding: utf-8 -*-
"""
Reference exporter for cross-engine validation.

Runs the PRODUCTION Python engine (backend/main.py, imported read-only) on a
reference BESS series and dumps both the exact inputs and the engine's
outputs to reference.json, so the Node.js core can replay the identical
inputs and be compared row by row.

Input priority:
  1. The real Ibri2 SCADA export, if present on this machine
  2. A deterministic synthetic 288-step 5-minute day (seeded), otherwise

Usage:  python validation/export_reference.py     (from node-core/)
"""
import json
import math
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "backend"))

import pandas as pd  # noqa: E402

import main  # noqa: E402  — backend/main.py, imported without modification

IBRI2 = Path(r"C:\Users\user\Downloads\files (1)\Ibri2_SCADA_EMS_July2024.csv")
OUT = Path(__file__).resolve().parent / "reference.json"


def series_from_ibri2():
    """Replicates audit_from_file's cleaning pipeline on the real export."""
    contents = IBRI2.read_bytes()
    df = main._parse_file_bytes(contents, IBRI2.name)
    col_map = main._resolve_columns_verbose(list(df.columns))["resolved"]
    df = df.rename(columns={v: k for k, v in col_map.items() if v in df.columns})
    for col, default in {"hour": None, "actual_discharge": 0.0, "actual_charge": 0.0,
                         "soc": None, "grid_demand": None, "curtailment_mw": 0.0,
                         "operator_override": False, "forecast_price": None}.items():
        if col not in df.columns:
            df[col] = default
    df, _ = main._detect_excel_serial_timestamps(df)
    df, _ = main._parse_timestamps(df)
    df, _ = main._order_and_dedupe_timestamps(df)
    df, _ = main._coerce_numeric_columns(df)
    df, _ = main._detect_and_apply_units(df)
    df, res_notes = main._detect_and_resample(df)
    res_sec = res_notes.get("detected_resolution_sec")
    dt_hours = (res_sec / 3600.0) if res_sec else 1.0

    asset_kwargs = {}
    for key in main.ASSET_META_ALIASES:
        if key in df.columns:
            nn = df[key].dropna()
            if len(nn):
                v = nn.iloc[0]
                asset_kwargs[key] = v.strip() if isinstance(v, str) else v
    if "soc_init" not in asset_kwargs and "soc" in df.columns:
        s = pd.to_numeric(df["soc"], errors="coerce").dropna()
        if len(s):
            v = float(s.iloc[0])
            v = v / 100.0 if v > 1.5 else v
            asset_kwargs["soc_init"] = min(0.95, max(0.1, v))
    asset = main.AssetSpecs(**asset_kwargs)

    if main.pd.api.types.is_datetime64_any_dtype(df["hour"]):
        df["hour"] = range(len(df))
    sub = df[["hour", "price", "actual_discharge", "actual_charge", "soc",
              "grid_demand", "curtailment_mw", "operator_override", "forecast_price"]]
    ts = sub.astype(object).where(pd.notna(sub), None).to_dict("records")
    return asset, ts, dt_hours, "Ibri2_SCADA_EMS_July2024.csv"


def series_synthetic():
    """Deterministic 288-step 5-minute day (no randomness — reproducible)."""
    ts = []
    for i in range(288):
        price = 10.0 + 6.0 * math.sin((i - 84) * math.pi / 144) + 0.8 * math.sin(i / 5.0)
        dis = 25.0 if 216 <= i <= 228 else 0.0
        ch = 35.0 if 24 <= i <= 40 else 0.0
        ts.append({"hour": i, "price": round(price, 4), "actual_discharge": dis,
                   "actual_charge": ch, "soc": None, "grid_demand": None,
                   "curtailment_mw": 0.0, "operator_override": False,
                   "forecast_price": None})
    asset = main.AssetSpecs(asset_type="BESS", asset_name="Synthetic Ref",
                            p_max=50, e_max=100, soc_init=0.5)
    return asset, ts, 1.0 / 12.0, "synthetic-288x5min"


def run():
    if IBRI2.exists():
        asset, ts, dt_hours, source = series_from_ibri2()
    else:
        asset, ts, dt_hours, source = series_synthetic()

    result = main.process_calculation(asset, ts, save_to_db=False,
                                      dt_hours=dt_hours, currency="OMR")

    rows = [{
        "step": i,
        "price": r.price,
        "optimal_action": r.optimal_action,
        "actual_action": r.actual_action,
        "edv_optimal_step": r.edv_optimal_step,
        "edv_actual_step": r.edv_actual_step,
        "gap_step": r.gap_step,
    } for i, r in enumerate(result.decision_log)]

    payload = {
        "source": source,
        "inputs": {
            "asset": {"p_max": asset.p_max, "e_max": asset.e_max,
                      "soc_init": asset.soc_init, "eta_ch": asset.eta_ch,
                      "eta_dis": asset.eta_dis, "deg_cost": asset.deg_cost},
            "dt_hours": dt_hours,
            "series": [{"price": float(t["price"] or 0),
                        "actual_discharge": float(t["actual_discharge"] or 0),
                        "actual_charge": float(t["actual_charge"] or 0)} for t in ts],
        },
        "python": {
            "edv_optimal_total": result.edv_optimal_total,
            "edv_actual_total": result.edv_actual_total,
            "total_gap": result.total_gap_usd,
            "dq_score": result.dq_score,
            "dq_score_raw": result.dq_score_raw,
            "rows": rows,
        },
    }
    OUT.write_text(json.dumps(payload), encoding="utf-8")
    print(f"reference written: {OUT}  source={source}  steps={len(rows)}  "
          f"gap={result.total_gap_usd}  dq={result.dq_score}")


if __name__ == "__main__":
    run()
