#!/usr/bin/env python
"""
PREDAIOT pre-audit file validator.

Runs any SCADA/EMS export through the exact same ingestion pipeline the
platform uses — column resolution, banner-header recovery, timestamp cleanup,
unit detection, sensor-plausibility checks — WITHOUT spending CPU on the MILP,
and prints a pass/warn/fail verdict.

Usage:
    python tools/validate_predaiot_csv.py <file.csv|.xlsx|.json|.parquet|.xml>

Exit codes:
    0 = PASS   (audit will run; no warnings)
    1 = WARN   (audit will run; review the warnings before quoting results)
    2 = FAIL   (audit cannot run — required columns missing or file unreadable)

Requires the backend environment (run from the backend/ directory or with
backend/ on PYTHONPATH). Python 3.11+.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `import main` work whether invoked from backend/ or backend/tools/
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

GREEN, YELLOW, RED, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[0m"


def validate(path: str) -> int:
    import pandas as pd
    import main

    p = Path(path)
    if not p.exists():
        print(f"{RED}FAIL{RESET}  file not found: {path}")
        return 2

    contents = p.read_bytes()
    try:
        df = main._parse_file_bytes(contents, p.name)
    except Exception as e:
        print(f"{RED}FAIL{RESET}  could not parse file: {e}")
        return 2

    flags = list(df.attrs.get("ingest_flags", []))

    col_info = main._resolve_columns_verbose(list(df.columns))
    col_map = col_info["resolved"]

    print(f"file      : {p.name}")
    print(f"rows      : {len(df)}   columns: {len(df.columns)}")
    print(f"currency  : {main._detect_currency(list(df.columns)) or 'USD (no hint found)'}")
    print()
    print("column mapping (internal <- file column):")
    for k in sorted(col_map):
        tag = "fuzzy" if k in col_info["fuzzy_scores"] else "exact"
        print(f"  {k:20s} <- {col_map[k]}   [{tag}]")
    unresolved = [c for c in df.columns if c not in col_map.values()]
    if unresolved:
        print(f"  unmapped columns ({len(unresolved)}): {', '.join(str(c) for c in unresolved[:10])}"
              + (" …" if len(unresolved) > 10 else ""))
    print()

    # Hard requirements — same rule as POST /api/v1/audit/file
    missing = [r for r in ("price", "actual_discharge") if r not in col_map]
    if missing:
        print(f"{RED}FAIL{RESET}  required column(s) unresolvable: {missing}")
        print("       The audit endpoint would reject this file (HTTP 400).")
        return 2

    # Simulate the cleaning pipeline to collect every flag the audit would raise
    preview = df.rename(columns={v: k for k, v in col_map.items() if v in df.columns})
    preview, _ = main._detect_excel_serial_timestamps(preview)
    preview, ts_format = main._parse_timestamps(preview)
    preview, order_flags = main._order_and_dedupe_timestamps(preview)
    flags.extend(order_flags)
    preview, coerce_flags = main._coerce_numeric_columns(preview)
    flags.extend(coerce_flags)
    preview, unit_corrections = main._detect_and_apply_units(preview)
    preview, resolution_notes = main._detect_and_resample(preview)

    res_sec = resolution_notes.get("detected_resolution_sec")
    dt_hours = (res_sec / 3600.0) if res_sec else 1.0

    meta = {}
    for key in main.ASSET_META_ALIASES:
        if key in preview.columns:
            nn = preview[key].dropna()
            if len(nn):
                v = nn.iloc[0]
                meta[key] = v.strip() if isinstance(v, str) else v
    try:
        asset = main.AssetSpecs(**meta)
    except Exception:
        asset = main.AssetSpecs()
    flags.extend(main._build_sensor_quality_flags(preview, dt_hours, asset.p_max, asset.e_max))

    print(f"timestamps: {ts_format.get('format_detected') or 'none — 0..N-1 index fallback'}")
    if res_sec:
        print(f"resolution: {resolution_notes.get('detected_resolution_label')} "
              f"(dt = {dt_hours:.4f} h), missing steps: {resolution_notes.get('missing_pct')}%")
    if unit_corrections:
        for u in unit_corrections:
            print(f"units     : {u}")
    print(f"asset     : {asset.asset_type} '{asset.asset_name}' "
          f"p_max={asset.p_max} e_max={asset.e_max}")
    print()

    warnings = [f for f in flags if f["severity"] == "warning"]
    infos    = [f for f in flags if f["severity"] != "warning"]
    for f in warnings:
        print(f"{YELLOW}WARN{RESET}  [{f['code']}] {f['message']}")
    for f in infos:
        print(f"info  [{f['code']}] {f['message']}")
    print()

    if warnings:
        print(f"{YELLOW}RESULT: WARN{RESET} — the audit will run, but review the warnings "
              "above before quoting results externally.")
        return 1
    print(f"{GREEN}RESULT: PASS{RESET} — safe to run the audit and generate the PDF.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(validate(sys.argv[1]))
