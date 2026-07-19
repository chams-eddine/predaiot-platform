# -*- coding: utf-8 -*-
"""Value normalisation — unit auto-detection/correction, numeric coercion, and
display-currency detection from column-name hints.

Public API: _detect_and_apply_units, _coerce_numeric_columns, _detect_currency.
Dependencies: ingestion._primitives (_dq, _normalise_col). Extracted VERBATIM.
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


_CURRENCY_HINTS = [
    ("omr", "OMR"), ("aed", "AED"), ("sar", "SAR"), ("kwd", "KWD"),
    ("qar", "QAR"), ("bhd", "BHD"), ("eur", "EUR"), ("gbp", "GBP"),
    ("usd", "USD"),
]

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

def _detect_currency(raw_columns: list) -> Optional[str]:
    joined = " " + " ".join(_normalise_col(str(c)) for c in raw_columns) + " "
    for hint, code in _CURRENCY_HINTS:
        if f"_{hint}" in joined or f"{hint}_" in joined or f" {hint} " in joined:
            return code
    return None
