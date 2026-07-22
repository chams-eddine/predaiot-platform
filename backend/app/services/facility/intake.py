# -*- coding: utf-8 -*-
"""File Intake & Classification (understand-first upload).

PREDAIOT understands the facility BEFORE deciding whether an economic audit is
possible. An upload is one of two kinds:

  • operational  — a time-series with price + power/consumption → the frozen
    economic engine runs (full audit, unchanged).
  • engineering  — a Facility Definition / nameplate export (Equipment, Rated MW,
    Transformer MVA, Voltage Primary …) with NO operational measurements. It is
    NOT an error: run the Facility Understanding Engine ONLY and return the
    recognized facility (topology, equipment, capabilities) + guidance asking for
    operational data.

Nothing here touches the economic engine or fabricates economic numbers. Nameplate
columns are mapped to Level-1 facts via knowledge (merged_nameplate_aliases), so a
new industry's nameplate is recognized by adding pack data, not code.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.versions import PARSER_VERSION
from app.knowledge.registry import merged_nameplate_aliases
from app.schemas import AssetSpecs
from app.services.facility import understand
from app.services.ingestion.columns import ASSET_META_ALIASES, _normalise_col

# Canonical SIGNAL fields (operational). Used both to classify and to pass any
# resolved operational columns through to the FUE on an engineering file.
_SIGNAL_FIELDS = ("price", "actual_discharge", "actual_charge", "soc",
                  "grid_demand", "curtailment_mw", "forecast_price")


def classify(col_map: Dict[str, str]) -> str:
    """operational iff the file carries price AND a power/consumption column; else
    engineering. Deterministic, industry-agnostic — the same rule the audit
    endpoint used to gate on, now a routing decision instead of a hard failure."""
    has_output = ("actual_discharge" in col_map) or ("actual_charge" in col_map)
    return "operational" if ("price" in col_map and has_output) else "engineering"


def _num(v: Any) -> Any:
    """Best-effort numeric coercion for a nameplate value ('30', '30 MVA',
    '33,000' → floats). Non-numeric values (e.g. an equipment name) pass through."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"[-+]?\d*\.?\d+", str(v).strip().replace(",", ""))
    return float(m.group()) if m else v


def extract_nameplate_facts(df: "pd.DataFrame") -> Tuple[Dict[str, Any], List[str]]:
    """Resolve nameplate columns → Level-1 facts via knowledge. First non-null value
    per column (real exports fill nameplate on row 1 only). Returns (facts, consumed
    original column names) so the caller can exclude them from 'ungrounded'."""
    aliases = merged_nameplate_aliases()                 # fact -> [normalised headers]
    norm_to_col: Dict[str, Any] = {}
    for col in df.columns:
        norm_to_col.setdefault(_normalise_col(str(col)), col)
    facts: Dict[str, Any] = {}
    consumed: List[str] = []
    for fact, alias_list in aliases.items():
        for a in alias_list:
            col = norm_to_col.get(a)
            if col is None:
                continue
            series = df[col].dropna()
            if len(series):
                facts[fact] = _num(series.iloc[0])
                consumed.append(col)
            break
    return facts, consumed


def _asset_specs_from_columns(df: "pd.DataFrame") -> Tuple[AssetSpecs, List[str], Dict[str, Any]]:
    """AssetSpecs from any asset-meta columns present (first non-null), mirroring the
    audit endpoint. Returns (specs, consumed columns, raw kwargs actually supplied)."""
    kwargs: Dict[str, Any] = {}
    consumed: List[str] = []
    norm_to_col: Dict[str, Any] = {}
    for col in df.columns:
        norm_to_col.setdefault(_normalise_col(str(col)), col)
    for key, alias_list in ASSET_META_ALIASES.items():
        for a in alias_list:
            col = norm_to_col.get(a)
            if col is None:
                continue
            non_null = df[col].dropna()
            if len(non_null):
                val = non_null.iloc[0]
                kwargs[key] = val.strip() if isinstance(val, str) else val
                consumed.append(col)
            break
    try:
        return AssetSpecs(**kwargs), consumed, kwargs
    except Exception:
        return AssetSpecs(), consumed, {}


def understand_engineering_file(
    df: "pd.DataFrame",
    col_map: Dict[str, str],
    raw_columns: List[str],
    input_sha256: str,
    filename: Optional[str],
    file_size_bytes: int = 0,
    rows_parsed: int = 0,
    columns_parsed: int = 0,
    currency: str = "USD",
) -> Dict[str, Any]:
    """Run the FUE ONLY over a nameplate/engineering file and assemble the
    'facility_understood' response. No economic engine, no fabricated numbers."""
    asset, meta_cols, meta_kwargs = _asset_specs_from_columns(df)
    nameplate_facts, np_cols = extract_nameplate_facts(df)

    # any operational signals that DID resolve still inform the FUE
    signal_map = {k: v for k, v in col_map.items() if k in _SIGNAL_FIELDS}

    grounded = set(col_map.values()) | set(meta_cols) | set(np_cols)
    unknowns = [c for c in raw_columns if c not in grounded]

    stem = re.sub(r"\.[^.]+$", "", filename or "") or "facility"
    # A name the file actually supplied (not the AssetSpecs default) wins;
    # otherwise the recognized facility label, else the filename stem.
    explicit_name = meta_kwargs.get("asset_name")
    facility_id = explicit_name or stem

    profile = understand(
        signal_map=signal_map, specs=asset.dict(), time_series=[],
        metadata=nameplate_facts, extra_columns=unknowns,
        currency=currency, facility_id=facility_id,
    )
    pdict = profile.to_dict()

    recognized = (pdict["facility_type"]["value"] != "Unknown"
                  or any(e["identity"]["value"] != "Unknown" for e in pdict["equipment"]))
    facility_label = pdict["facility_type"]["value"]
    asset_name = (explicit_name
                  or (facility_label if facility_label != "Unknown" else None)
                  or stem)

    return {
        "mode": "facility_understanding",
        "facility_profile": pdict,
        "asset_name": asset_name,
        "facility_type": facility_label,          # convenience mirror
        "recognized": recognized,
        "guidance": {
            "operational_data_required": True,
            "headline": ("Facility identified." if recognized
                         else "File received — facility not yet recognized."),
            "message": ("To perform an economic audit, upload operational "
                        "measurements (price + power + timestamps)."),
            "required": ["price", "power (actual_discharge / actual_charge)", "timestamp"],
        },
        "audit_manifest": {
            "manifest_version": "1.0",
            "input_sha256": input_sha256,
            "original_filename": filename,
            "file_size_bytes": file_size_bytes,
            "rows_parsed": rows_parsed,
            "columns_parsed": columns_parsed,
            "uploaded_at_utc": datetime.utcnow().isoformat() + "Z",
            "parser_version": PARSER_VERSION,
            "mode": "facility_understanding",
        },
    }
