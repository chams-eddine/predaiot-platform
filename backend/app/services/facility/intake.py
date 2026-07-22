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
from dataclasses import dataclass, field
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
    endpoint used to gate on, now a routing decision instead of a hard failure.
    NB: price/power are KNOWLEDGE-resolved canonical signals (dozens of aliases),
    not literal column names. See assess_readiness() for the evidence view."""
    has_output = ("actual_discharge" in col_map) or ("actual_charge" in col_map)
    return "operational" if ("price" in col_map and has_output) else "engineering"


def classify_archetype(col_map: Dict[str, str],
                       time_series: List[Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """Infer the physics ARCHETYPE from the resolved operational signals, so the
    engine runs the right track (Part 1: category classification BEFORE calculation).
    Returns (archetype|None, basis). None = ambiguous → don't override the default.

    A furnace/motor/pump only ever CONSUMES: charge signal present, discharge ~0,
    no SoC → `load`. This is the fix for the category error that ran the storage
    (battery) formula on a pure-consumption asset and produced negative captured value.
    A confidently-recognized explicit asset_type still wins (handled by the caller)."""
    def _sum(f: str) -> float:
        return sum(abs(float(ts.get(f) or 0)) for ts in time_series)
    has_soc = "soc" in col_map
    dis = _sum("actual_discharge")
    ch = _sum("actual_charge")
    has_curt = "curtailment_mw" in col_map
    if has_soc or (dis > 0 and ch > 0):
        return "storage", "SoC/bidirectional charge+discharge present"
    if ch > 0 and dis <= 0:
        return "load", "consumption-only (charge present, no discharge, no SoC)"
    if dis > 0 and has_curt:
        return "intermittent", "generation with curtailment signal, no consumption/SoC"
    return None, "ambiguous — no decisive signal; default retained"


@dataclass
class Readiness:
    """Operational-Readiness stage — the honest question is 'do we have enough to
    START the economic audit?', not 'is there a column named price?'. `economic_audit`
    is the hard gate (the frozen engine's required inputs); the confidences are the
    evidence view; `next_step` tells the caller exactly what to upload next."""
    economic_audit: bool                 # engine can run (price + power present)
    operational_confidence: float        # 0..1 evidence for an operational time-series
    understanding_confidence: float      # 0..1 how sure we are WHAT the facility is
    reason: str                          # ready | missing_operational_measurements | missing_price | missing_power_signal
    next_step: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"economic_audit": self.economic_audit,
                "operational_confidence": self.operational_confidence,
                "understanding_confidence": self.understanding_confidence,
                "reason": self.reason}


_OPERATIONAL_REQUIRED = ["price", "power (actual_discharge / actual_charge)", "timestamp"]


def assess_readiness(col_map: Dict[str, str], row_count: int = 0,
                     understanding_confidence: float = 0.0) -> Readiness:
    """Evidence-based readiness. Operational evidence = price + power signal (the
    engine's contract) + timestamp + continuity; each is a KNOWLEDGE-resolved
    canonical signal, so this generalizes to any industry without column-name
    coupling. The economic audit runs iff price AND power are present (unchanged
    gate → operational audits stay byte-identical)."""
    has_price = "price" in col_map
    has_power = ("actual_discharge" in col_map) or ("actual_charge" in col_map)
    has_time = "hour" in col_map
    op_conf = round(0.45 * has_price + 0.45 * has_power
                    + 0.05 * has_time + 0.05 * (row_count > 1), 2)
    economic_audit = bool(has_price and has_power)
    if economic_audit:
        reason, nxt = "ready", {}
    else:
        if not has_price and not has_power:
            reason, missing = "missing_operational_measurements", _OPERATIONAL_REQUIRED
        elif not has_power:
            reason, missing = "missing_power_signal", ["power (actual_discharge / actual_charge)"]
        else:
            reason, missing = "missing_price", ["price"]
        nxt = {"upload": "operational_timeseries", "required": missing}
    return Readiness(economic_audit=economic_audit, operational_confidence=op_conf,
                     understanding_confidence=round(understanding_confidence or 0.0, 2),
                     reason=reason, next_step=nxt)


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

    # Operational-Readiness stage: understood, but can we audit? (evidence view)
    readiness = assess_readiness(col_map, row_count=rows_parsed or len(df),
                                 understanding_confidence=pdict["understanding_confidence"])

    # Human copy is DERIVED from the machine-readable reason (single source), so the
    # frontend can render from `readiness` + `next_step` alone (no extra logic).
    _msg = {
        "missing_operational_measurements":
            "To perform an economic audit, upload operational measurements (price + power + timestamps).",
        "missing_power_signal":
            "Add a power / consumption signal (with prices and timestamps) to run the economic audit.",
        "missing_price":
            "Add a market-price column (with power and timestamps) to run the economic audit.",
    }.get(readiness.reason, "Upload operational measurements to run the economic audit.")

    return {
        "mode": "facility_understanding",
        "facility_profile": pdict,
        "asset_name": asset_name,
        "facility_type": facility_label,          # convenience mirror
        "recognized": recognized,
        "readiness": readiness.to_dict(),
        "next_step": readiness.next_step,
        "guidance": {
            "operational_data_required": True,
            "headline": ("Facility identified." if recognized
                         else "File received — facility not yet recognized."),
            "message": _msg,
            "required": readiness.next_step.get("required", _OPERATIONAL_REQUIRED),
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
