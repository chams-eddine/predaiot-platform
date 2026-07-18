# -*- coding: utf-8 -*-
"""Pure presentation/formatting helpers. No I/O, no app state — safe to import
anywhere. Extracted verbatim from main.py (refactor step 1), behavior-preserving.
"""
from __future__ import annotations


def _fmt_money(x, cur: str = "USD", decimals: int = 2) -> str:
    """"1,234.56 USD" / "1,234.56 OMR" — code suffix, no currency symbol, so
    every PREDAIOT surface (UI, PDF, certificate) speaks one money language."""
    cur = (cur or "USD").upper()
    try:
        val = float(x or 0)
    except (TypeError, ValueError):
        val = 0.0
    return f"{val:,.{decimals}f} {cur}"


def _json_safe(obj):
    """Recursively replace NaN/±inf with None — strict JSON has no NaN."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    return obj
