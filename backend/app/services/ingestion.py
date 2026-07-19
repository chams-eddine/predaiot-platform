# -*- coding: utf-8 -*-
"""Ingestion + data-quality service — turns a raw uploaded file into a clean,
quality-assessed DataFrame + data-quality flags/indices (column resolution,
unit + timestamp detection, resample, numeric coercion, sensor-quality flags,
DQI/forecast-reliability). Extracted VERBATIM from main.py (refactor step 3,
service 5 part 1). NO business rules, NO economic math. Dependency rule: only
core + eda_metrics + stdlib/pandas.

NOTE (ARCHITECTURE_DEBT): this module is ~2x the 400-line budget; the boundary
review after Part 1 splits it into ingestion/parsing + ingestion/quality.
"""
import io  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import re  # noqa: F401
from io import BytesIO, StringIO  # noqa: F401  (used unqualified by the file parsers)
from datetime import datetime, timedelta  # noqa: F401
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

import eda_metrics  # noqa: F401

from app.core.constants import (  # noqa: F401
    _STANDARD_INTERVALS, _COMMS_STATUS_ALIASES, _COMMS_OK_VALUES,
)

_CURRENCY_HINTS = [
    ("omr", "OMR"), ("aed", "AED"), ("sar", "SAR"), ("kwd", "KWD"),
    ("qar", "QAR"), ("bhd", "BHD"), ("eur", "EUR"), ("gbp", "GBP"),
    ("usd", "USD"),
]


COLUMN_ALIASES = {
    # ── price — market / spot price ─────────────────────────────────────────────
    "price": [
        # English — common
        "price", "spot_price", "market_price", "energy_price", "lmp",
        "price_usd", "price_$/mwh", "price_($/mwh)", "price_mwh",
        "clearing_price", "settlement_price", "pool_price", "da_price",
        "rt_price", "wholesale_price", "electricity_price", "tariff",
        "rate", "cost_per_mwh", "mwh_price", "$/mwh", "usd/mwh",
        "omr/mwh", "omr_mwh", "price_omr", "aed/mwh", "sar/mwh",
        # Extended market aliases
        "half_hourly_price", "hhp", "imbalance_price", "balancing_price",
        "nodal_price", "zonal_price", "hub_price", "index_price",
        "pjm_lmp", "ercot_spp", "caiso_lmp", "miso_lmp",
        "epex_price", "n2ex_price", "elspot_price", "belpex_price",
        "omel_price", "gme_price", "aps_price", "negative_price",
        # Oil & Gas
        "gas_price", "gas_price_mmbtu", "fuel_cost", "henry_hub",
        "nbp_price", "ttf_price", "co2_price", "carbon_price",
        # Hydrogen
        "h2_price", "hydrogen_price", "green_h2_price",
        # Arabic aliases (أسماء عربية)
        "السعر", "سعر_الكهرباء", "السعر_الفوري", "سعر_السوق",
        "التعريفة", "سعر_المقاصة", "تكلفة_الطاقة",
    ],

    # ── actual_discharge — actual generation / output / production ──────────────
    "actual_discharge": [
        # English — common
        "actual_discharge", "discharge", "actual_power", "power_output",
        "generation", "actual_generation", "gen_mw", "output_mw",
        "dispatch_mw", "actual_dispatch", "p_actual", "p_out",
        "power_mw", "energy_out", "production", "actual_production",
        "mw_out", "discharge_mw", "bess_discharge", "bess_discharge_mw",
        "battery_discharge", "battery_discharge_mw", "storage_discharge_mw",
        "pcs_discharge_mw", "solar_output",
        "wind_output", "p_gen", "pgen", "p_dis", "pdis",
        "net_generation", "real_power", "active_power",
        "gross_generation", "net_output",
        # Solar
        "solar_generation", "pv_output", "solar_power", "irradiance_mw",
        "dc_power", "ac_power", "inverter_output",
        # Wind
        "wind_generation", "turbine_output", "wind_power",
        "rotor_power", "nacelle_power", "hub_power",
        # Hydro / Pumped hydro
        "hydro_generation", "turbine_generation", "hydro_output",
        "penstock_flow_mw", "dam_output",
        # Gas / thermal
        "gas_generation", "thermal_output", "combined_cycle_output",
        "gt_output", "st_output", "peaker_output", "ocgt_output",
        # Nuclear
        "nuclear_output", "reactor_power", "reactor_output",
        # Hydrogen electrolyzer
        "electrolyzer_power", "electrolyzer_output", "h2_production_power",
        "electrolyzer_mw",
        # Desalination
        "desalination_power", "desal_mw", "ro_power", "msf_power",
        "med_power",
        # Oil & Gas compression / injection
        "compressor_power", "injection_power", "pump_power",
        # Arabic aliases
        "التوليد", "الإنتاج", "القدرة_الفعلية", "الطاقة_المنتجة",
        "الصرف_الفعلي", "الخرج", "الطاقة_الكهربائية",
        "توليد_الطاقة", "إنتاج_الطاقة",
    ],

    # ── hour — timestep / interval index ────────────────────────────────────────
    "hour": [
        "hour", "interval", "timestep", "time_step", "step",
        "period", "slot", "index", "idx", "t", "timestamp",
        "datetime", "time", "date_time", "hour_index",
        "half_hour", "quarter_hour", "five_min", "minute",
        "الوقت", "الساعة", "الفترة", "الفاصل_الزمني",
    ],

    # ── actual_charge — charging power (BESS / pumped hydro / electrolyzer) ─────
    "actual_charge": [
        "actual_charge", "charge", "charge_mw", "p_charge", "pcharge",
        "charging_power", "bess_charge", "bess_charge_mw",
        "battery_charge", "battery_charge_mw", "storage_charge_mw",
        "charge_power", "p_ch",
        "pumping_power", "pump_power_mw", "h2_load", "electrolyzer_load",
        "الشحن", "طاقة_الشحن",
    ],

    # ── soc — state of charge / reservoir level ──────────────────────────────────
    "soc": [
        "soc", "state_of_charge", "battery_soc", "soc_pct",
        "soc_%", "energy_level", "stored_energy_pct",
        # Hydro reservoir
        "reservoir_level", "water_level_m", "water_level_pct",
        "reservoir_pct", "head_m",
        # Hydrogen tank
        "tank_pressure", "h2_level", "h2_storage_pct",
        # Arabic
        "حالة_الشحن", "مستوى_الطاقة", "مستوى_الخزان",
    ],

    # ── curtailment ───────────────────────────────────────────────────────────────
    "curtailment_mw": [
        "curtailment_mw", "curtailment", "curtailed_mw", "curtailed",
        "clipped_mw", "clipping", "spilled_mw", "spillage",
        "wind_curtailment", "solar_curtailment", "forced_outage_mw",
        "التقليص", "التخفيض_القسري",
    ],

    # ── operator override ────────────────────────────────────────────────────────
    "operator_override": [
        "operator_override", "override", "manual_override",
        "human_override", "manual_dispatch", "operator_intervention",
        "تدخل_المشغل", "التجاوز_اليدوي",
    ],

    # ── forecast price ───────────────────────────────────────────────────────────
    "forecast_price": [
        "forecast_price", "predicted_price", "price_forecast",
        "da_forecast", "price_prediction", "forecast", "f_price",
        "price_forecast_da", "day_ahead_forecast",
        "السعر_المتوقع", "توقع_السعر",
    ],

    # ── grid demand ───────────────────────────────────────────────────────────────
    "grid_demand": [
        "grid_demand", "demand", "load", "system_load",
        "grid_load", "net_load", "demand_level",
        "الطلب", "حمل_الشبكة", "حمل_النظام",
    ],

    # ── asset-specific extras ─────────────────────────────────────────────────────
    # Gas / thermal efficiency
    "fuel_consumption": [
        "fuel_consumption", "fuel_rate", "heat_rate", "gas_consumption",
        "fuel_flow_mmbtu", "gas_flow_mcf",
    ],
    # Hydrogen production volume
    "h2_production_kg": [
        "h2_production_kg", "hydrogen_production", "h2_flow_rate",
        "h2_volume_nm3", "electrolyzer_kg_h",
    ],
    # Desalination
    "water_production_m3": [
        "water_production_m3", "permeate_flow", "product_water",
        "desal_output_m3h", "water_m3",
    ],
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

def _normalise_col(name: str) -> str:
    """
    Lowercase and strip punctuation for alias matching.
    Currency symbols, brackets, units-in-parens all get stripped so that
    "Spot Price ($/MWh)" → "spot_price_mwh" and lines up with the "spot_price"
    or "price" aliases (fuzzy tier fills in the rest).
    """
    n = (name or "").lower().strip()
    # Drop stuff that adds no semantic value for matching
    for ch in "()[]{}$€£¥%,;:'\"":
        n = n.replace(ch, "")
    # Whitespace + dashes + slashes normalise to underscore
    for ch in " -/\\":
        n = n.replace(ch, "_")
    # Collapse repeats
    while "__" in n:
        n = n.replace("__", "_")
    return n.strip("_")

_FUZZY_THRESHOLD = 80  # rapidfuzz token_sort_ratio out of 100

def _resolve_columns_verbose(df_cols: list) -> dict:
    """
    Two-tier column resolution.

    Tier 1 — exact alias match against the manually-curated COLUMN_ALIASES /
    ASSET_META_ALIASES tables. Fast, deterministic, unchanged behaviour.

    Tier 2 — fuzzy match (rapidfuzz.token_sort_ratio ≥ 80) for any internal
    field the exact tier didn't resolve. Handles the "close enough" cases:
    "Discharge_MW_avg" → actual_discharge, "PriceUSDperMWh" → price, etc.
    Silently falls back to exact-only if rapidfuzz isn't installed.

    Returns {resolved, match_type, fuzzy_scores} for diagnostics.
    """
    normalised = {c: _normalise_col(c) for c in df_cols}
    all_aliases = {**COLUMN_ALIASES, **ASSET_META_ALIASES}

    resolved = {}
    match_type = {}         # internal → "exact" | "fuzzy"
    fuzzy_scores = {}       # internal → {matched_alias, score, from_col}

    # Tier 1: exact alias match. Iterate the ALIAS LIST in order — each list is
    # curated most-specific-first, so with hybrid files that expose several
    # plausible columns (e.g. a Solar+BESS export with both `solar_output` and
    # `bess_discharge_mw`) the storage-specific name wins deterministically
    # instead of "whichever column happened to come first in the file". A
    # column can only be claimed once across internals.
    norm_to_orig: dict = {}
    for original, norm in normalised.items():
        norm_to_orig.setdefault(norm, original)  # first file occurrence wins ties
    claimed = set()
    for internal, aliases in all_aliases.items():
        for alias in aliases:
            original = norm_to_orig.get(alias)
            if original is not None and original not in claimed:
                resolved[internal] = original
                match_type[internal] = "exact"
                claimed.add(original)
                break

    # Tier 2: fuzzy match for the remainder
    try:
        from rapidfuzz import fuzz, process as fz_process
    except ImportError:
        fuzz = None
        fz_process = None

    if fuzz is not None:
        used_cols = set(resolved.values())
        candidates = [(orig, norm) for orig, norm in normalised.items() if orig not in used_cols]
        for internal, aliases in all_aliases.items():
            if internal in resolved:
                continue
            best_col, best_score, best_alias = None, 0, None
            for orig, norm in candidates:
                match = fz_process.extractOne(norm, aliases, scorer=fuzz.token_sort_ratio)
                if match is None:
                    continue
                alias, score = match[0], match[1]
                if score > best_score:
                    best_col, best_score, best_alias = orig, score, alias
            if best_score >= _FUZZY_THRESHOLD and best_col is not None:
                resolved[internal] = best_col
                match_type[internal] = "fuzzy"
                fuzzy_scores[internal] = {
                    "matched_alias": best_alias,
                    "score": round(float(best_score), 1),
                    "from_col": best_col,
                }
                candidates = [(o, n) for o, n in candidates if o != best_col]

    return {"resolved": resolved, "match_type": match_type, "fuzzy_scores": fuzzy_scores}

def _resolve_columns(df_cols: list) -> dict:
    """Back-compat wrapper — same shape as before (internal_name → actual_col_name)."""
    return _resolve_columns_verbose(df_cols)["resolved"]

def _detect_and_apply_units(df: pd.DataFrame) -> tuple:
    """
    Heuristic unit correction per Coverage Tasks 1.5.

    Power kW → MW: max(actual_discharge) > 500 → treat as kW, divide by 1000.
    Price $/kWh → $/MWh: max(price) < 1.0 → treat as $/kWh, multiply by 1000.

    Returns (df_corrected, corrections_list). Corrections is a plain string list
    to surface in the inspect response so the operator can confirm or override.
    """
    corrections = []

    for col, label in (("actual_discharge", "actual_discharge"),
                       ("actual_charge",    "actual_charge")):
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            m = series.abs().max()
            if pd.notna(m) and m > 500:
                df[col] = series / 1000.0
                corrections.append(f"{label} looked like kW (max {m:.0f}); converted to MW.")

    if "price" in df.columns:
        series = pd.to_numeric(df["price"], errors="coerce")
        m = series.abs().max()
        # Only auto-scale up when max is clearly sub-dollar. > $1 could still be a
        # fair $/MWh price in emerging markets, so don't touch it.
        if pd.notna(m) and 0 < m < 1.0:
            df["price"] = series * 1000.0
            corrections.append(f"price looked like $/kWh (max {m:.3f}); converted to $/MWh.")

    return df, corrections

def _detect_excel_serial_timestamps(df: pd.DataFrame) -> tuple:
    """
    Excel-saved CSVs often serialise timestamps as float days-since-1899-12-30.
    Detection: the timestamp column is entirely numeric and falls in the plausible
    Excel-date range (40000..60000 covers 2009 through 2064). If so, convert to
    real datetime — the resolution detector downstream can then work on it.
    """
    corrections = []
    if "hour" not in df.columns:
        return df, corrections
    series = pd.to_numeric(df["hour"], errors="coerce")
    if series.notna().all() and 40000 < float(series.min()) and float(series.max()) < 60000:
        df["hour"] = pd.to_datetime(series, unit="D", origin="1899-12-30")
        corrections.append("hour column looked like Excel serial timestamps; parsed as datetime.")
    return df, corrections

_TIMESTAMP_FORMAT_ATTEMPTS = [
    # (label, pandas args to try in `pd.to_datetime(series, **kw)`)
    ("ISO 8601",                    dict(utc=True)),
    ("DD/MM/YYYY (Gulf default)",   dict(dayfirst=True)),
    ("MM/DD/YYYY (US)",             dict(dayfirst=False)),
]

def _parse_timestamps(df: pd.DataFrame) -> tuple:
    """
    Best-effort timestamp parsing for the "hour" column.

    Tries a fixed matrix of formats: ISO 8601 (Z, offset, space), Unix epoch
    (seconds vs milliseconds), then DD/MM (Gulf convention) and MM/DD (US) for
    ambiguous slash-separated dates. Assumes Gulf Standard Time (UTC+4) for
    timezone-naive inputs since that's the sales target (Coverage Tasks 1.4).

    Returns (df, notes). `notes` is a dict with `format_detected` (str or None)
    and, if a datetime column was produced, `first_ts` / `last_ts` ISO strings.
    """
    notes = {"format_detected": None, "first_ts": None, "last_ts": None}
    if "hour" not in df.columns:
        return df, notes

    col = df["hour"]

    # Already datetime? Nothing to do.
    if pd.api.types.is_datetime64_any_dtype(col):
        notes["format_detected"] = "already datetime"
        _fill_ts_bounds(col, notes)
        return df, notes

    # Try Unix epoch first (small integers won't collide with slash dates).
    numeric = pd.to_numeric(col, errors="coerce")
    if numeric.notna().all():
        m = float(numeric.abs().max())
        # Excel-serial range gets handled by _detect_excel_serial_timestamps; skip that here.
        if 40000 < m < 60000:
            pass  # Excel-serial branch owns this
        elif 1e12 < m < 1e14:
            df["hour"] = pd.to_datetime(numeric, unit="ms", utc=True)
            notes["format_detected"] = "Unix epoch (ms)"
            _fill_ts_bounds(df["hour"], notes)
            return df, notes
        elif 1e9 < m < 1e11:
            df["hour"] = pd.to_datetime(numeric, unit="s", utc=True)
            notes["format_detected"] = "Unix epoch (s)"
            _fill_ts_bounds(df["hour"], notes)
            return df, notes

    # String-shaped: run through the format matrix. Accept `object` (legacy
    # pandas) and `str` (pandas 2.1+) alike — the numeric path above handled
    # anything else that could plausibly be a timestamp.
    if not pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_datetime64_any_dtype(col):
        s = col.astype(str)
        for label, kw in _TIMESTAMP_FORMAT_ATTEMPTS:
            try:
                parsed = pd.to_datetime(s, errors="coerce", **kw)
            except (ValueError, TypeError):
                continue
            # Accept a format only if it parses (mostly) everything cleanly.
            if parsed.notna().mean() >= 0.98:
                suffix = ""
                # Timezone-naive → assume Gulf Standard Time (UTC+4). Per brief
                # 1.4: sales target is Oman/GCC, so the local wall-clock reading
                # is what the operator meant when they omitted the tz.
                if parsed.dt.tz is None:
                    parsed = parsed.dt.tz_localize("Asia/Muscat", nonexistent="shift_forward", ambiguous="NaT")
                    suffix = " (Gulf tz assumed)"
                df["hour"] = parsed
                notes["format_detected"] = label + suffix
                _fill_ts_bounds(parsed, notes)
                return df, notes

    return df, notes

def _fill_ts_bounds(series, notes: dict) -> None:
    try:
        notes["first_ts"] = pd.Timestamp(series.iloc[0]).isoformat()
        notes["last_ts"]  = pd.Timestamp(series.iloc[-1]).isoformat()
    except Exception:
        pass

def _detect_and_resample(df: pd.DataFrame) -> tuple:
    """
    If the "hour" column is a real datetime, compute the median inter-step delta,
    snap it to the nearest standard interval, and resample:
      - forward-fill  operational fields (actual_discharge, actual_charge,
        soc, curtailment_mw, operator_override) — these persist between reads
      - linear-interp continuous fields (price, forecast_price) — these vary smoothly

    Skips resampling (with a warning) if more than 20% of the expected steps
    would be missing — better to audit what the operator actually gave us than
    fabricate 20% of the data. Also converts "hour" to an ordered int index at
    the end so process_calculation sees the shape it expects.

    Returns (df, notes). Notes shape:
      { detected_resolution_sec, expected_steps, actual_steps,
        resampled, missing_pct, warning (if any) }
    """
    notes = {
        "detected_resolution_sec": None,
        "detected_resolution_label": None,
        "expected_steps": None,
        "actual_steps": int(len(df)),
        "resampled": False,
        "missing_pct": None,
        "warning": None,
    }
    if "hour" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["hour"]):
        return df, notes

    ts = df["hour"]
    if len(ts) < 3:
        return df, notes

    deltas = ts.diff().dt.total_seconds().dropna()
    median_delta = float(deltas.median())
    if median_delta <= 0:
        return df, notes

    # Snap to the nearest standard interval by log-distance
    import math
    snapped = min(_STANDARD_INTERVALS, key=lambda x: abs(math.log(x) - math.log(median_delta)))
    notes["detected_resolution_sec"] = snapped
    notes["detected_resolution_label"] = {
        60: "1-minute", 300: "5-minute", 900: "15-minute",
        1800: "30-minute", 3600: "60-minute",
    }[snapped]

    span_sec = (ts.iloc[-1] - ts.iloc[0]).total_seconds()
    expected = int(span_sec / snapped) + 1
    notes["expected_steps"] = expected
    missing_pct = max(0.0, (expected - len(df)) / max(1, expected) * 100)
    notes["missing_pct"] = round(missing_pct, 2)

    if missing_pct >= 20.0:
        notes["warning"] = (
            f"Data has {missing_pct:.1f}% missing steps at the detected {notes['detected_resolution_label']} "
            "resolution. Skipping resample — audit uses steps as-provided."
        )
        return df, notes

    # Resample. Set the datetime as index, apply per-column policy, reset.
    df = df.set_index("hour").sort_index()
    op_cols  = [c for c in ("actual_discharge", "actual_charge", "soc",
                            "curtailment_mw", "operator_override") if c in df.columns]
    con_cols = [c for c in ("price", "forecast_price") if c in df.columns]
    rule = f"{snapped}s"

    # Anchor bins to the asset's FIRST reading (origin="start"), not to the
    # pandas default (epoch/midnight). Real SCADA exports rarely begin on a
    # clean boundary (e.g. 01:09); default anchoring would open with an empty
    # leading bin whose all-NaN row crashes the downstream engine. origin="start"
    # is an identity for data that already begins on a boundary, so audited
    # results are unchanged for well-aligned files.
    parts = []
    if op_cols:
        parts.append(df[op_cols].resample(rule, origin="start").ffill())
    if con_cols:
        # numeric only — linear interp
        parts.append(df[con_cols].apply(pd.to_numeric, errors="coerce").resample(rule, origin="start").mean().interpolate("linear"))
    # Pass-through anything else (grid_demand etc.) with ffill
    other = [c for c in df.columns if c not in op_cols + con_cols]
    if other:
        parts.append(df[other].resample(rule, origin="start").ffill())

    df = pd.concat(parts, axis=1).reset_index()
    notes["resampled"] = True
    notes["actual_steps"] = int(len(df))
    return df, notes

def _dq(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}

def _order_and_dedupe_timestamps(df: pd.DataFrame) -> tuple:
    """
    Sort out-of-order rows, drop unparseable timestamps, drop duplicate
    timestamps (keep first). Only acts when "hour" is a real datetime.
    """
    flags = []
    if "hour" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["hour"]):
        return df, flags

    n_nat = int(df["hour"].isna().sum())
    if n_nat:
        df = df[df["hour"].notna()].copy()
        flags.append(_dq("warning", "timestamps_dropped",
                         f"{n_nat} row(s) had unreadable timestamps and were removed from the audit."))
    if len(df) and not df["hour"].is_monotonic_increasing:
        df = df.sort_values("hour").reset_index(drop=True)
        flags.append(_dq("info", "timestamps_sorted",
                         "Rows were not in chronological order — sorted by timestamp."))
    n_dup = int(df["hour"].duplicated().sum())
    if n_dup:
        df = df[~df["hour"].duplicated(keep="first")].reset_index(drop=True)
        flags.append(_dq("warning", "duplicate_timestamps",
                         f"{n_dup} duplicate timestamp row(s) removed (kept the first occurrence)."))
    return df, flags

def _coerce_numeric_columns(df: pd.DataFrame) -> tuple:
    """
    Numeric coercion with honest gap handling. Prices are load-bearing for
    every EDV figure, so missing prices are linearly interpolated from
    neighbours (with a flag) instead of silently becoming $0 — a fake $0
    price fabricates arbitrage that never existed. Power columns default
    missing → 0 MW and negatives are clipped (charge/discharge arrive in
    separate columns; a negative there is a sign-convention artefact).
    """
    flags = []
    for col in ("price", "actual_discharge", "actual_charge", "curtailment_mw"):
        if col not in df.columns:
            continue
        num = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce",
        )
        n_bad = int(num.isna().sum())
        if col == "price":
            if n_bad and n_bad < len(num):
                num = num.interpolate("linear", limit_direction="both")
                flags.append(_dq("warning", "price_gaps_interpolated",
                                 f"{n_bad} missing/non-numeric price value(s) were linearly "
                                 "interpolated from neighbouring steps."))
            df[col] = num.fillna(0.0)
        else:
            if n_bad and n_bad < len(num):
                flags.append(_dq("info", f"{col}_gaps_zeroed",
                                 f"{n_bad} missing {col} value(s) treated as 0 MW."))
            df[col] = num.fillna(0.0)
            n_neg = int((df[col] < 0).sum())
            if n_neg:
                df[col] = df[col].clip(lower=0.0)
                flags.append(_dq("info", f"{col}_negatives_clipped",
                                 f"{n_neg} negative {col} value(s) clipped to 0 MW "
                                 "(charge and discharge are separate columns)."))

    # Secondary numeric telemetry that still reaches DecisionRecord (context
    # fields, not load-bearing for EDV). A stray non-numeric cell here — e.g.
    # an Excel "#REF!" left in a historian export — must NOT 500 the audit;
    # strip junk to a missing value (NaN) so the row still validates. Blank
    # cells already arrive as NaN, so this only touches genuinely corrupt cells
    # and is an identity for clean files.
    for col in ("forecast_price", "soc", "grid_demand"):
        if col not in df.columns:
            continue
        raw = df[col]
        num = pd.to_numeric(
            raw.astype(str).str.replace(r"[^\d.\-eE]", "", regex=True).replace("", None),
            errors="coerce",
        )
        # count cells that were non-blank yet unparseable (true corruption)
        was_blank = raw.isna() | (raw.astype(str).str.strip() == "")
        n_corrupt = int((num.isna() & ~was_blank).sum())
        if n_corrupt:
            flags.append(_dq("warning", f"{col}_corrupt_values_dropped",
                             f"{n_corrupt} non-numeric {col} value(s) could not be parsed "
                             "and were treated as missing."))
        df[col] = num
    return df, flags

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

def _detect_currency(raw_columns: list) -> Optional[str]:
    joined = " " + " ".join(_normalise_col(str(c)) for c in raw_columns) + " "
    for hint, code in _CURRENCY_HINTS:
        if f"_{hint}" in joined or f"{hint}_" in joined or f" {hint} " in joined:
            return code
    return None

def _looks_numeric(v: str) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False

def _fix_banner_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    Real Excel/CSV exports often carry a title banner above the real header
    ("PREDAIOT — Site Export | July 2024" merged across the sheet). pandas
    then reads the banner as the header and every column becomes "Unnamed: N".
    Detect that shape, find the first row that actually looks like a header
    (mostly non-numeric strings across most columns), and re-head the frame.

    Adds a "banner_header_skipped" flag via df.attrs["ingest_flags"] so the
    correction is visible to the operator.
    """
    n_cols = len(df.columns)
    if n_cols == 0 or len(df) == 0:
        return df
    unnamed = sum(1 for c in df.columns
                  if str(c).startswith("Unnamed:") or not str(c).strip())
    if unnamed < max(2, n_cols // 2):
        return df

    for i in range(min(10, len(df))):
        row = df.iloc[i]
        vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if len(vals) < max(2, int(n_cols * 0.6)):
            continue  # banner / blank spacer row
        numericish = sum(1 for v in vals if _looks_numeric(v))
        if numericish > len(vals) * 0.3:
            continue  # data row, not a header
        # Group-band rows ("IDENTIFICATION IDENTIFICATION MARKET MARKET …")
        # repeat a handful of labels; a real header row is nearly all unique.
        if len(set(vals)) < len(vals) * 0.8:
            continue
        new_cols = [str(v).strip() if pd.notna(v) and str(v).strip() else f"col_{j}"
                    for j, v in enumerate(row)]
        out = df.iloc[i + 1:].reset_index(drop=True)
        out.columns = new_cols
        # Restore numeric dtypes the banner header forced to object.
        # Positional access — survives any residual duplicate names.
        for j in range(out.shape[1]):
            num = pd.to_numeric(out.iloc[:, j], errors="coerce")
            if num.notna().mean() >= 0.9:
                out.isetitem(j, num)
        out.attrs["ingest_flags"] = [_dq(
            "info", "banner_header_skipped",
            f"The file starts with {i + 1} title/banner row(s) above the real column "
            "header — skipped automatically.")]
        return out
    return df

def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    """Universal parser + banner-header recovery. See _parse_file_bytes_raw."""
    df = _parse_file_bytes_raw(contents, filename)
    return _fix_banner_header(df)

def _parse_file_bytes_raw(contents: bytes, filename: str) -> pd.DataFrame:
    """
    Universal file parser — handles CSV/TSV/Excel with automatic encoding detection.

    Encoding resolution order:
      1. BOM bytes  →  UTF-16 / UTF-8-BOM
      2. charset_normalizer (pip install charset-normalizer) auto-detect
      3. chardet fallback
      4. Exhaustive encoding list (Western, Arabic, Cyrillic, CJK …)
      5. Force-decode with replacement characters (never raises)
    """
    fname = (filename or "").lower()

    # ── Excel ──────────────────────────────────────────────────────────────────
    if fname.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(BytesIO(contents))

    # ── JSON ───────────────────────────────────────────────────────────────────
    # Accepts:
    #   1) Flat array of records:      [{"time": ..., "price": ...}, ...]
    #   2) Wrapper with a data array:  {"data": [...]}
    #      or {"timeseries": [...]}, {"time_series": [...]}, {"records": [...]},
    #      {"rows": [...]}, {"items": [...]}
    #   3) Column-oriented dict:       {"time": [...], "price": [...]}
    if fname.endswith(".json"):
        try:
            payload = json.loads(contents.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e.msg} at line {e.lineno}") from e
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            for key in ("data", "timeseries", "time_series", "records", "rows", "items", "values"):
                inner = payload.get(key)
                if isinstance(inner, list):
                    return pd.DataFrame(inner)
            # Column-oriented — every value is a list of the same length
            list_cols = {k: v for k, v in payload.items() if isinstance(v, list)}
            if list_cols and len({len(v) for v in list_cols.values()}) == 1:
                return pd.DataFrame(list_cols)
        raise ValueError(
            "JSON must be an array of records, a wrapper like {\"data\": [...]}, "
            "or a column-oriented dict of same-length arrays."
        )

    # ── XML ────────────────────────────────────────────────────────────────────
    # Common in EMS / SCADA historian exports (OSIsoft PI XML, various DCS).
    # pandas.read_xml handles the standard "list of rows" shape without much
    # coaxing. Lazy import so the app boots without lxml installed.
    if fname.endswith(".xml"):
        try:
            # pandas' read_xml uses lxml under the hood; give a clear error if
            # the operator hasn't installed it (this file path is opt-in).
            return pd.read_xml(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "XML upload requires the 'lxml' package. Install with "
                "`pip install lxml` (already declared in requirements.txt)."
            )
        except Exception as e:
            raise ValueError(
                f"Could not parse XML: {e}. Common shape: a root element with "
                "repeated child rows, each row containing scalar fields."
            ) from e

    # ── Parquet ────────────────────────────────────────────────────────────────
    # Data-lake exports. Lazy import — pyarrow is ~50MB, opt-in per deployment.
    if fname.endswith(".parquet"):
        try:
            return pd.read_parquet(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "Parquet upload requires the 'pyarrow' package (~50MB). Install "
                "with `pip install pyarrow` if your deploy environment can afford it."
            )
        except Exception as e:
            raise ValueError(f"Could not parse Parquet: {e}") from e

    # Separator heuristic
    sep = "\t" if fname.endswith(".tsv") else ","

    # ── Encoding resolution, scored by USEFULNESS ──────────────────────────────
    # "Decoded without an exception" is NOT the same as "decoded correctly":
    # cp1256 Arabic bytes decode 'successfully' as Shift-JIS mojibake and the
    # column names become garbage. So every candidate parse is scored by how
    # many internal fields its columns actually resolve to, and the best
    # candidate wins. A score >= 2 (price + an output/consumption column)
    # short-circuits — that parse is definitely the right alphabet.
    def _alias_score(df_cand) -> int:
        try:
            return len(_resolve_columns_verbose([str(c) for c in df_cand.columns])["resolved"])
        except Exception:
            return 0

    ordered = []
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        ordered.append("utf-16")
    if contents[:3] == b"\xef\xbb\xbf":
        ordered.append("utf-8-sig")
    try:
        from charset_normalizer import from_bytes
        guess = from_bytes(contents[:20000]).best()
        if guess and guess.encoding:
            ordered.append(str(guess.encoding))
    except ImportError:
        pass
    try:
        import chardet
        g = chardet.detect(contents[:20000]).get("encoding")
        if g:
            ordered.append(g)
    except ImportError:
        pass
    ordered += [
        # Unicode
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32",
        # Arabic (كل ملفات Excel المحلية تستخدم هذا) — before Western so Gulf
        # exports don't get eaten by latin-1 (which never raises)
        "cp1256", "iso-8859-6",
        # Western European
        "latin-1", "cp1252", "iso-8859-15",
        # Central / Eastern European
        "cp1250", "iso-8859-2",
        # Cyrillic
        "cp1251", "iso-8859-5", "koi8-r",
        # CJK
        "gbk", "gb2312", "gb18030", "big5", "shift_jis", "euc-jp", "euc-kr",
        # Misc
        "ascii", "cp437",
    ]

    best_df, best_score, tried = None, -1, set()
    for enc in ordered:
        key = enc.lower()
        if key in tried:
            continue
        tried.add(key)
        try:
            df_cand = pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception:
            continue
        if len(df_cand.columns) == 0:
            continue
        score = _alias_score(df_cand)
        if score > best_score:
            best_df, best_score = df_cand, score
        if score >= 2:
            return df_cand
    if best_df is not None:
        return best_df

    # ── Nuclear fallback: force-decode with Unicode replacement chars ───────────
    try:
        text_content = contents.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(text_content), sep=sep)
        # Strip replacement chars from column names
        df.columns = [str(c).replace("\ufffd", "").strip() for c in df.columns]
        return df
    except Exception:
        pass

    raise ValueError(
        "Could not parse this file. "
        "Please try: (1) save as CSV UTF-8 in Excel → Save As → CSV UTF-8 (comma delimited), "
        "or (2) export as .xlsx. "
        "Your file's encoding was not recognizable after 20+ attempts."
    )
