# -*- coding: utf-8 -*-
"""Ingestion primitives — shared leaf helpers (canonical column-name
normalisation, data-quality-note accumulation) reused across the ingestion
submodules.

Public API: _normalise_col, _dq.
Dependencies: stdlib/pandas only. Depends on no other ingestion submodule
(the package leaf). Extracted VERBATIM from main.py.
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

def _dq(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}
