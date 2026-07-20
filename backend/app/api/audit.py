# -*- coding: utf-8 -*-
"""Audit API router — the core product surface: run an audit from JSON or an
uploaded file, inspect ingestion, render the PDF report + ledger CSV, and the
AI-enhance narrative passthrough. Extracted VERBATIM from main.py (Router
Extraction, step 6). _persist_audit_record moves here with its only callers;
it relocates to the repository layer in step 7.
Dependency direction: api -> services (audit/ingestion/report/trial) + domain-
tier leaves + core + models + schemas. No economic math here."""
import hashlib as _hashlib  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import uuid  # noqa: F401
from datetime import datetime  # noqa: F401
from io import StringIO  # noqa: F401
from typing import Any, Dict, Optional  # noqa: F401

import pandas as pd  # noqa: F401
from fastapi import (  # noqa: F401
    APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Request, UploadFile,
)
from fastapi.responses import JSONResponse, Response  # noqa: F401

import eda_metrics  # noqa: F401
import canonical_event  # noqa: F401
from app.core.config import SessionLocal  # noqa: F401
from app.core.constants import _MAX_UPLOAD_BYTES, _RATING_WITHDRAWN_LABEL  # noqa: F401
from app.core.dependencies import require_audit_runner, require_trial_or_user  # noqa: F401
from app.core.logging import _security_log  # noqa: F401
from app.core.ratelimit import limiter  # noqa: F401
from app.core.state import _latest_by_token  # noqa: F401
from app.core.versions import (  # noqa: F401
    ENGINE_VERSION, METHODOLOGY_VERSION, PARSER_VERSION, SOLVER_NAME, SOLVER_VERSION,
)
from app.models import AuditRecord, Decision, EconomicState, TrialLead, User  # noqa: F401
from app.schemas import AssetSpecs, AuditRequest, AuditResponse  # noqa: F401
from app.services.audit_service import process_calculation  # noqa: F401
from app.services.ingestion import (  # noqa: F401
    COLUMN_ALIASES, ASSET_META_ALIASES, _normalise_col, _FUZZY_THRESHOLD,
    _resolve_columns_verbose, _resolve_columns, _detect_and_apply_units,
    _detect_excel_serial_timestamps, _TIMESTAMP_FORMAT_ATTEMPTS, _parse_timestamps,
    _fill_ts_bounds, _detect_and_resample, _dq, _order_and_dedupe_timestamps,
    _coerce_numeric_columns, _build_sensor_quality_flags, _collect_data_quality_counts,
    _dqi_components_from_manifest, _forecast_reliability_from_snapshot, _detect_currency,
    _looks_numeric, _fix_banner_header, _parse_file_bytes, _parse_file_bytes_raw,
)
from app.services.optimization_service import _MILP_LAST, _dispatch_mode  # noqa: F401
from app.services.report_service import _build_audit_pdf  # noqa: F401
from app.services.trial_service import _bump_audit_count  # noqa: F401
from app.utils.formatting import _fmt_money, _json_safe  # noqa: F401

router = APIRouter()


def _persist_audit_record(lead: TrialLead, result: "AuditResponse",
                          input_sha256: str, filename: Optional[str]) -> None:
    """Store the audit's Economic State for the account's organization (L3)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == lead.user_id).first()
        if user is None:
            return
        d = result.dict()
        dqi = d.get("data_quality_index") or {}
        aei = d.get("audit_confidence") or {}
        attribution = d.get("gap_attribution") or {}
        rcs = d.get("root_causes") or []
        top_rc = max(rcs, key=lambda r: r.get("contribution_pct") or 0)["category"] if rcs else None
        manifest = d.get("audit_manifest") or {}
        rec = AuditRecord(
            org_id=user.org_id, user_id=user.id,
            asset_name=d.get("asset_name"), asset_type=d.get("asset_type"),
            input_sha256=input_sha256, filename=filename,
            engine_version=manifest.get("audit_engine_version"),
            methodology_version=manifest.get("methodology_version"),
            currency=d.get("currency"),
            gap_total=d.get("total_gap_usd"),
            gap_recoverable=attribution.get("execution_gap"),
            dqi=dqi.get("value"), dqi_grade=dqi.get("grade"),
            aei=aei.get("value"), aei_grade=aei.get("grade"),
            top_root_cause=top_rc,
            result_json=json.dumps(_json_safe(d), default=str),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        _security_log("audit.run", actor=user.email, org_id=user.org_id,
                      object_ref=f"audit:{rec.id}|sha:{input_sha256[:12]}")
        # EDA-ES-1.0: materialise the canonical Economic State from this audit.
        es = eda_metrics.build_economic_state(d)
        db.add(EconomicState(
            org_id=user.org_id, audit_id=rec.id, asset_id=rec.asset_id,
            version=es["version"], currency=es["currency"],
            window_start=es["window_start"], window_end=es["window_end"],
            span_hours=es["span_hours"], captured_value=es["captured_value"],
            economic_potential=es["economic_potential"], leakage_rate=es["leakage_rate"],
            recoverable_value=es["recoverable_value"], dqi=es["dqi"],
            audit_confidence=es["audit_confidence"], economic_health=es["economic_health"],
            economic_health_grade=es["economic_health_grade"],
            provisional=es["provisional"], evidence_sha256=es["evidence_sha256"],
            state_json=json.dumps(es, default=str),
        ))
        db.commit()
        # EDA-DEC-1.0: materialise decisions (economic commitments) from the
        # Economic State + audit ledger. Deterministic; consumes, never mutates.
        for dec in eda_metrics.build_decisions(d, es, audit_id=rec.id):
            evi = dec["expected_value_impact"]
            db.add(Decision(
                org_id=user.org_id, audit_id=rec.id, asset_id=rec.asset_id,
                decision_id=dec["decision_id"], version=dec["version"],
                decision_type=dec["decision_type"], root_cause_id=dec["root_cause_id"],
                economic_state_version=dec["economic_state_version"],
                expected_value=evi["value_at_stake"], currency=evi["currency"],
                decision_mode=dec["decision_mode"],
                governance_owner_role=dec["governance_owner"]["role"],
                governance_owner_user_id=dec["governance_owner"]["assigned_user_id"],
                decision_evidence_sha256=dec["evidence_reference"]["decision_evidence_sha256"],
                status=dec["status"],
                decision_json=json.dumps(dec, default=str),
            ))
        db.commit()
    finally:
        db.close()

@router.post("/api/v1/audit", response_model=AuditResponse)
@limiter.limit("10/minute")
async def calculate_gap(
    request: Request,   # noqa: ARG001 — used by rate limiter
    audit_req: AuditRequest,
    background: BackgroundTasks,
    lead: TrialLead = Depends(require_audit_runner),
):
    result = process_calculation(audit_req.asset, [ts.dict() for ts in audit_req.time_series],
                                 dt_hours=audit_req.dt_hours or 1.0)
    _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
    background.add_task(_bump_audit_count, lead.token)
    return result

# ==========================================
# COLUMN ALIAS MAP — fuzzy resolver
# Maps any real-world column name variant → internal name
# ==========================================
# Ingestion + data-quality service now in app/services/ingestion.py (svc 5 pt 1).

# Asset spec meta-columns that can optionally appear as file columns









# Suggested fallbacks for missing fields — used in the inspect response so
# users know exactly what will happen if they proceed without a given column.
_MISSING_FIELD_FALLBACKS = {
    "actual_charge":     "assumed 0 MW throughout — charging events won't be detected.",
    "soc":               "not required for the audit; SOC constraints won't gate the optimiser.",
    "curtailment_mw":    "assumed 0 MW — curtailment recovery attribution will be zero.",
    "forecast_price":    "not required; forecast-utilisation score defaults to 0%.",
    "operator_override": "assumed False — override-governance opportunity won't fire.",
    "grid_demand":       "advisory only; the audit engine doesn't use it.",
    "hour":              "auto-generated as 0..N-1 ordered index.",
}






# Order matters: try the strictest / most-informative parses first. ISO 8601
# (including Z-suffixed and offset-suffixed variants) parses cleanly with just
# `utc=True`; only fall through to Gulf/US slash-date if ISO fails.






# Standard energy-market resolutions we snap to (seconds)
# _STANDARD_INTERVALS → app/core/constants.py (refactor step 2A)




# ==========================================
# DATA QUALITY & CLEANING LAYER
# "Trust of result is everything" — every silent auto-correction the pipeline
# makes gets a named flag the operator can read before quoting the audit.
# Severity: "warning" = affects result trust, "info" = cosmetic / advisory.
# ==========================================



# _fmt_money / _json_safe now live in app/utils/formatting.py (refactor step 1).
# Imported at module top; re-exported here so every existing `_fmt_money(...)`
# / `_json_safe(...)` call site in this file is unchanged.






# Column names that carry a comms / link health status in SCADA exports
# _COMMS_STATUS_ALIASES / _COMMS_OK_VALUES → app/core/constants.py (refactor step 2A)










# _CURRENCY_HINTS → app/services/ingestion.py (refactor step 3, service 5 part 1)




# Upload ceiling: a year of 1-minute data for one asset is ~40 MB of CSV;
# anything past this is either the wrong export or a memory-exhaustion attempt.
# _MAX_UPLOAD_BYTES → app/core/constants.py (refactor step 2A)










@router.post("/api/v1/audit/file", response_model=AuditResponse)
@limiter.limit("10/minute")
async def audit_from_file(
    request: Request,   # noqa: ARG001 — used by rate limiter
    background: BackgroundTasks,
    file: UploadFile = File(...),
    lead: TrialLead = Depends(require_audit_runner),
):
    """
    Universal file ingestion. Accepts real-world exports from any SCADA / EMS /
    historian with a two-tier column resolver, JSON support, unit auto-detection,
    and Excel-serial timestamp recovery.

    Accepted formats: .csv  .tsv  .txt  .xlsx  .xls  .xlsm  .json
    """
    try:
        contents = await file.read()
        if len(contents) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={
                "detail": f"File is {len(contents) / 1e6:.0f} MB — the upload limit is "
                          f"{_MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Split the export or "
                          "resample to a coarser interval."})
        df = _parse_file_bytes(contents, file.filename or "")
        if len(df) == 0:
            return JSONResponse(status_code=400, content={
                "detail": "The file parsed but contains no data rows (header only?)."})
        raw_shape = df.shape  # provenance: as-parsed dimensions (C2 manifest)

        # Resolve column aliases (exact → fuzzy)
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Check required fields resolved. Load-class assets (electrolyzers,
        # desalination) report CONSUMPTION, not output — actual_charge alone
        # is a valid audit input for them (the engine falls back internally).
        has_output = ("actual_discharge" in col_map) or ("actual_charge" in col_map)
        if "price" not in col_map or not has_output:
            missing = [r for r in ("price",) if r not in col_map]
            if not has_output:
                missing.append("actual_discharge (or a consumption column like actual_charge)")
            return JSONResponse(status_code=400, content={
                "detail": (
                    f"Could not find required column(s): {missing}. "
                    f"Your file has columns: {list(df.columns)}. "
                    f"Use /api/v1/audit/inspect to see the full mapping attempt."
                )
            })

        # Rename resolved columns to internal names
        rename_map = {v: k for k, v in col_map.items() if v in df.columns}
        df = df.rename(columns=rename_map)

        # Add missing optional columns with defaults. actual_discharge is
        # optional too since load-class files carry only consumption.
        defaults = {
            'hour': None, 'actual_discharge': 0.0, 'actual_charge': 0.0, 'soc': None,
            'grid_demand': None, 'curtailment_mw': 0.0,
            'operator_override': False, 'forecast_price': None,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        # Excel-serial timestamp recovery, then full timestamp matrix.
        df, ts_corrections = _detect_excel_serial_timestamps(df)
        df, ts_format = _parse_timestamps(df)

        # Read-only snapshot for the Data Quality Manifest: taken AFTER
        # timestamp parsing but BEFORE the mutating pipeline (dedupe / coerce /
        # resample), so DQI describes the dataset the customer actually
        # supplied. Never mutated.
        dq_snapshot = df.copy()

        # Clean: drop unparseable timestamps, sort out-of-order, dedupe.
        # Parse-stage flags (banner-header recovery) come first.
        parse_flags = list(df.attrs.get("ingest_flags", []))
        df, dq_flags = _order_and_dedupe_timestamps(df)
        dq_flags = parse_flags + dq_flags

        # If we still have no usable "hour", fall back to a 0..N-1 index. The
        # audit engine only needs ordering; wall-clock time is a nice-to-have
        # for the resolution detector.
        if 'hour' not in df.columns or df['hour'].isnull().all():
            df['hour'] = range(len(df))

        # Coerce numeric columns — tolerates strings like "12.5 MW"; missing
        # prices interpolate (never fake $0), missing power → 0 MW, each with
        # a named flag.
        df, coerce_flags = _coerce_numeric_columns(df)
        dq_flags.extend(coerce_flags)

        # Unit auto-detection (kW→MW, $/kWh→$/MWh)
        df, unit_corrections = _detect_and_apply_units(df)

        # Time-resolution auto-detect + optional resample (only when hour is a
        # real datetime, so this is a no-op for CSV/JSON without a timestamp).
        df, resolution_notes = _detect_and_resample(df)

        # Step duration for the audit engine. Detected from timestamps when
        # available; otherwise the legacy hourly assumption (dt = 1.0).
        res_sec = resolution_notes.get("detected_resolution_sec")
        dt_hours = (res_sec / 3600.0) if res_sec else 1.0
        resolution_notes["dt_hours_used"] = round(dt_hours, 6)

        # Asset specs from meta-columns — first NON-NULL value, because real
        # SCADA exports fill metadata on row 1 only (or on a random row after
        # a historian merge).
        asset_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in df.columns:
                non_null = df[key].dropna()
                if len(non_null):
                    val = non_null.iloc[0]
                    asset_kwargs[key] = val.strip() if isinstance(val, str) else val

        # Initial SoC from the file's first reading when not given explicitly —
        # the MILP's arbitrage budget depends on where the battery started.
        if "soc_init" not in asset_kwargs and "soc" in df.columns:
            soc_series = pd.to_numeric(df["soc"], errors="coerce").dropna()
            if len(soc_series):
                v = float(soc_series.iloc[0])
                v = v / 100.0 if v > 1.5 else v
                asset_kwargs["soc_init"] = min(0.95, max(0.1, v))
                dq_flags.append(_dq("info", "soc_init_from_data",
                                    f"Initial state of charge taken from the file's first reading: "
                                    f"{asset_kwargs['soc_init'] * 100:.0f}%."))
        asset = AssetSpecs(**asset_kwargs)

        # Read-only sensor plausibility checks (comms dropouts, SoC physics,
        # frozen price feed) — run while "hour" is still a datetime.
        dq_flags.extend(_build_sensor_quality_flags(df, dt_hours, asset.p_max, asset.e_max))
        currency = _detect_currency(list(rename_map.keys()) + list(df.columns))

        # Collapse "hour" back to an ordered integer for the audit engine
        if 'hour' in df.columns and pd.api.types.is_datetime64_any_dtype(df['hour']):
            df['hour'] = range(len(df))

        # NaN → None before records: resampling turns absent optional columns
        # (forecast_price, soc, grid_demand) into all-NaN floats, and NaN is
        # not JSON-compliant — it must become null, not poison the response.
        sub = df[[
            'hour', 'price', 'actual_discharge', 'actual_charge',
            'soc', 'grid_demand', 'curtailment_mw', 'operator_override', 'forecast_price'
        ]]
        time_series = sub.astype(object).where(pd.notna(sub), None).to_dict('records')

        result = process_calculation(asset, time_series, dt_hours=dt_hours,
                                     currency=currency or "USD")

        input_sha256 = _hashlib.sha256(contents).hexdigest()

        # ── W1–W4: Data Quality Index + Audit Confidence ────────────────────
        # Data Quality Manifest: read-only integer evidence from the supplied
        # dataset (before any mutation). DQI is the geometric mean of the
        # applicable, asset-agnostic components; absent dimensions are N/A.
        dq_manifest = _collect_data_quality_counts(
            dq_snapshot, asset.p_max, asset.e_max, dt_hours,
            has_forecast_col=("forecast_price" in col_map), col_map=col_map)
        dq_manifest["dataset_sha256"] = input_sha256
        dq_components = _dqi_components_from_manifest(dq_manifest)
        dqi_obj = eda_metrics.build_dqi(dq_components)
        # Audit Confidence — solver-gated, independent of Forecast Reliability.
        solver_proven = not (_dispatch_mode(asset.asset_type) == "storage"
                             and _MILP_LAST.get("status") not in ("Optimal",))
        m_consistency = eda_metrics.model_consistency(result.dq_score_raw)
        ac_obj = eda_metrics.audit_confidence(dqi_obj["value"], m_consistency, solver_proven)
        fr_obj = _forecast_reliability_from_snapshot(dq_snapshot, "forecast_price" in col_map)

        result.data_quality_index = dqi_obj
        result.audit_confidence = ac_obj
        result.forecast_reliability = fr_obj
        result.data_quality_manifest = dq_manifest

        # C2 — chain of custody. Every figure in this audit can be re-derived
        # from the file identified by input_sha256 using the versions below.
        result.audit_manifest = {
            "manifest_version":   "1.0",
            "input_sha256":       input_sha256,
            "original_filename":  file.filename,
            "file_size_bytes":    len(contents),
            "rows_parsed":        int(raw_shape[0]),
            "columns_parsed":     int(raw_shape[1]),
            "steps_audited":      len(time_series),
            "timestamp_range":    {"first": ts_format.get("first_ts"),
                                   "last":  ts_format.get("last_ts")},
            "uploaded_at_utc":    datetime.utcnow().isoformat() + "Z",
            "uploaded_by":        lead.email,
            "parser_version":     PARSER_VERSION,
            "audit_engine_version": ENGINE_VERSION,
            "methodology_version":  METHODOLOGY_VERSION,
            "solver": {
                "name":            SOLVER_NAME,
                "library_version": SOLVER_VERSION,
                "time_limit_s":    45,
                "status":          _MILP_LAST.get("status"),
                # CBC "Optimal" = proven optimal at its default tolerance; a
                # numeric MIP-gap channel is future work — never fabricated.
                "mip_gap":         None,
            },
        }

        # Very large files can hit the MILP wall-clock cap — CBC then returns
        # its best incumbent. Disclose it: the optimum becomes a lower bound.
        if _dispatch_mode(asset.asset_type) == "storage" and \
                _MILP_LAST.get("status") not in ("Optimal",):
            dq_flags.append(_dq("info", "milp_time_capped",
                                f"The optimizer hit its {45}s time cap on {_MILP_LAST.get('steps')} "
                                "steps and returned its best solution so far — the reported optimum "
                                "is a LOWER bound; the true gap can only be larger."))

        # Model/data disagreement: actual "beat" the theoretical optimum →
        # the mapping or specs are wrong, not the operator superhuman. Flag it
        # loudly rather than shipping a quietly-clamped perfect score.
        if (result.dq_score_raw or 0.0) > 1.02:
            dq_flags.append(_dq("warning", "actual_exceeds_optimal",
                                f"Actual captured value exceeds the modeled optimum by "
                                f"{(result.dq_score_raw - 1) * 100:.0f}%. The column mapping or asset "
                                "specs likely don't match this asset — review the resolved mapping "
                                "before quoting these results."))

        # Ch 4.2 third domain case: EDV_optimal ≈ 0 but EDV_actual > 0 is an
        # ERROR STATE per the Reference Manual (profit was mathematically
        # impossible) — surface it, never certify it silently.
        if result.edv_optimal_total <= 0.01 and result.edv_actual_total > 0.01:
            dq_flags.append(_dq("warning", "dq_undefined_error_state",
                                "The model found no economic opportunity in this period, yet the "
                                "asset reports captured value — DQ is undefined here (Ref. Manual "
                                "Ch 4.2 error state). Check asset specs and column mapping."))

        # Reconciliation with the file's OWN gap estimate, when it carries one
        # (many SCADA exports embed a simple-rule gap column). Disclosing the
        # comparison — instead of silently ignoring the column — is what lets
        # an operator trust the MILP figure.
        embedded_col = next(
            (c for c in df.columns
             if "economic_decision_gap" in _normalise_col(str(c))
             or _normalise_col(str(c)).startswith("edg_")
             or _normalise_col(str(c)) in ("edg", "gap_omr", "gap_usd")), None)
        if embedded_col is not None:
            emb = pd.to_numeric(df[embedded_col], errors="coerce").fillna(0.0)
            emb_total = float(emb.sum())
            ours = float(result.total_gap_usd)
            if emb_total > 0:
                ratio = ours / emb_total
                if 0.75 <= ratio <= 1.25:
                    dq_flags.append(_dq("info", "embedded_gap_consistent",
                                        f"Your file carries its own gap estimate ({emb_total:,.0f}) — "
                                        f"consistent with the MILP counterfactual ({ours:,.0f})."))
                else:
                    dq_flags.append(_dq("info", "embedded_gap_differs",
                                        f"Your file carries its own gap estimate ({emb_total:,.0f}), "
                                        f"while the MILP counterfactual finds {ours:,.0f}. The embedded "
                                        "column is typically a simple threshold rule; the MILP evaluates "
                                        "every feasible dispatch trajectory (Ref. Manual Ch 9), so a "
                                        "difference is expected — both are shown for transparency."))

        _latest_by_token[lead.token] = result.dict()   # per-tenant cache — no cross-leak
        background.add_task(_bump_audit_count, lead.token)

        # L3 Economic Knowledge Layer: account users' audits are persisted —
        # the platform remembers. (Blueprint law 1: this row IS the stored
        # Economic State of the audit.) Trial audits stay ephemeral by design.
        # Persistence failure must never break the audit itself.
        try:
            if getattr(lead, "user_id", None):
                _persist_audit_record(lead, result, input_sha256, file.filename)
        except Exception as _pe:
            print(f"[history] WARNING: audit persistence failed (audit unaffected): {_pe}")

        # Non-fatal ingestion notes — surfaced on the response for the frontend
        # to display "we auto-corrected X, confirm before quoting the audit."
        has_notes = (
            unit_corrections or ts_corrections or col_info["fuzzy_scores"]
            or ts_format.get("format_detected") or resolution_notes.get("detected_resolution_sec")
            or dq_flags or currency
        )
        if has_notes:
            result_dict = result.dict()
            result_dict["ingestion_notes"] = {
                "unit_corrections":       unit_corrections,
                "timestamp_corrections":  ts_corrections,
                "fuzzy_column_matches":   col_info["fuzzy_scores"],
                "timestamp_format":       ts_format,
                "time_resolution":        resolution_notes,
                "data_quality":           dq_flags,
                "currency":               currency,
            }
            return JSONResponse(content=_json_safe(result_dict))
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error parsing file: {str(e)}"})


@router.post("/api/v1/audit/inspect")
async def inspect_file(file: UploadFile = File(...)):
    """
    Pre-audit preview per Coverage Tasks 1.6. Returns everything the engine
    would apply if the operator hits "run audit," without spending CPU on MILP.

    Response includes:
      - file_columns, rows, sample_row
      - resolved_mapping   internal → column, from exact + fuzzy tiers
      - fuzzy_column_matches (with score) — anything not exact
      - unresolved_columns — columns we couldn't map, worth manual review
      - unit_corrections   — kW→MW, $/kWh→$/MWh auto-fixes
      - timestamp_corrections — Excel-serial recovery
      - field_warnings     — per missing optional field, the fallback we'd apply
      - will_succeed       — the "safe to proceed" flag
    """
    try:
        contents = await file.read()
        if len(contents) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={
                "detail": f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."})
        df = _parse_file_bytes(contents, file.filename or "")
        col_info = _resolve_columns_verbose(list(df.columns))
        col_map = col_info["resolved"]

        # Simulate the pre-audit normalisation to preview corrections
        preview = df.copy()
        rename_map = {v: k for k, v in col_map.items() if v in preview.columns}
        preview = preview.rename(columns=rename_map)
        parse_flags = list(df.attrs.get("ingest_flags", []))
        preview, ts_corrections = _detect_excel_serial_timestamps(preview) if "hour" in preview.columns else (preview, [])
        preview, ts_format = _parse_timestamps(preview)
        preview, dq_flags = _order_and_dedupe_timestamps(preview)
        dq_flags = parse_flags + dq_flags
        preview, coerce_flags = _coerce_numeric_columns(preview)
        dq_flags.extend(coerce_flags)
        preview, unit_corrections = _detect_and_apply_units(preview)
        preview, resolution_notes = _detect_and_resample(preview)

        # Same dt / asset-spec resolution the audit will apply, so the preview
        # shows the exact sensor-quality flags the audit response will carry.
        res_sec = resolution_notes.get("detected_resolution_sec")
        dt_hours = (res_sec / 3600.0) if res_sec else 1.0
        resolution_notes["dt_hours_used"] = round(dt_hours, 6)
        meta_kwargs = {}
        for key in ASSET_META_ALIASES:
            if key in preview.columns:
                non_null = preview[key].dropna()
                if len(non_null):
                    val = non_null.iloc[0]
                    meta_kwargs[key] = val.strip() if isinstance(val, str) else val
        try:
            asset_preview = AssetSpecs(**meta_kwargs)
        except Exception:
            asset_preview = AssetSpecs()
        dq_flags.extend(_build_sensor_quality_flags(preview, dt_hours,
                                                    asset_preview.p_max, asset_preview.e_max))
        currency = _detect_currency(list(df.columns))

        # Warnings for missing optional fields
        expected_optional = ["actual_charge", "soc", "curtailment_mw", "forecast_price",
                             "operator_override", "grid_demand", "hour"]
        field_warnings = []
        for f in expected_optional:
            if f not in col_map:
                field_warnings.append({
                    "field":    f,
                    "status":   "missing",
                    "fallback": _MISSING_FIELD_FALLBACKS.get(f, "safe default applied."),
                })

        return {
            "file_columns":         list(df.columns),
            "rows":                 len(df),
            "resolved_mapping":     col_map,
            "fuzzy_column_matches": col_info["fuzzy_scores"],
            "unresolved_columns":   [c for c in df.columns if c not in col_map.values()],
            "unit_corrections":     unit_corrections,
            "timestamp_corrections": ts_corrections,
            "timestamp_format":     ts_format,
            "time_resolution":      resolution_notes,
            "data_quality":         dq_flags,
            "currency":             currency,
            "field_warnings":       field_warnings,
            "will_succeed":         "price" in col_map
                                    and ("actual_discharge" in col_map or "actual_charge" in col_map),
            "sample_row":           df.iloc[0].to_dict() if len(df) > 0 else {},
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.post("/api/v1/audit/pdf")
@limiter.limit("20/minute")
async def generate_audit_pdf(
    request: Request,   # noqa: ARG001 — used by rate limiter
    data: AuditResponse,
    lead: TrialLead = Depends(require_trial_or_user),
):
    """
    Produce a branded PDF of the supplied audit result, rendered over the
    corporate letterhead. Gated by trial token like the audit endpoints.
    """
    pdf_bytes = _build_audit_pdf(data.dict())
    safe_asset = "".join(ch for ch in (data.asset_name or "audit") if ch.isalnum() or ch in "-_") or "audit"
    filename = f"PREDAIOT_Audit_{safe_asset}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/v1/audit/ledger.csv")
async def get_audit_ledger_csv(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Economic Energy Ledger (Reference Manual Ch 8.1): the caller's most
    recent audit as a step-by-step CSV. Every headline number on the PDF is
    the sum of a column in this file — anyone can open it and reconcile the
    certificate line by line. R_k rows, fully auditable.
    """
    data = _latest_by_token.get(lead.token)
    if not data or not data.get("decision_log"):
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})

    import csv as _csv
    buf = StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    cur = (data.get("currency") or "USD").lower()
    w.writerow(["step", "hour", f"price_{cur}_per_mwh", "forecast_price",
                "optimal_action_mw", "actual_action_mw",
                f"edv_optimal_step_{cur}", f"edv_actual_step_{cur}",
                f"gap_step_{cur}", f"cumulative_gap_{cur}",
                "decision_type", "soc",
                "curtailment_mw", "operator_override"])
    cum = 0.0
    for i, r in enumerate(data["decision_log"], 1):
        g = float(r.get("gap_step") or 0)
        cum += g
        w.writerow([i, r.get("hour"), r.get("price"), r.get("forecast_price"),
                    r.get("optimal_action"), r.get("actual_action"),
                    r.get("edv_optimal_step"), r.get("edv_actual_step"),
                    round(g, 2), round(cum, 2),
                    r.get("decision_type"), r.get("soc"),
                    r.get("curtailment_mw"), r.get("operator_override")])
    # Trailer: totals for one-glance reconciliation against the PDF.
    w.writerow([])
    w.writerow(["TOTALS", "", "", "", "", "",
                data.get("edv_optimal_total"), data.get("edv_actual_total"),
                data.get("total_gap_usd"), round(cum, 2),
                f"dq_score={data.get('dq_score')}", "", "", ""])
    ga = data.get("gap_attribution") or {}
    if ga:
        w.writerow(["GAP ATTRIBUTION (Ch 8.2)", "", "", "", "", "",
                    f"forecast_gap={ga.get('forecast_gap')}",
                    f"execution_gap={ga.get('execution_gap')}",
                    "", "", "", "", "", ""])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="predaiot_audit_ledger.csv"'},
    )


@router.get("/api/v1/audit/pdf/latest")
async def get_latest_audit_pdf(lead: TrialLead = Depends(require_trial_or_user)):
    """PDF for the caller's most recent audit. Per-tenant cache, no cross-leak."""
    data = _latest_by_token.get(lead.token)
    if not data or data.get("dq_score") is None:
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
    pdf_bytes = _build_audit_pdf(data)
    safe_asset = "".join(ch for ch in (data.get("asset_name") or "audit") if ch.isalnum() or ch in "-_") or "audit"
    filename = f"PREDAIOT_Audit_{safe_asset}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================
# NEW: Claude AI Enhancement Proxy
# ==========================================
@router.post("/api/v1/ai-enhance")
async def ai_enhance(request: Dict[str, Any] = Body(...)):
    """
    Proxy endpoint for Claude AI enhanced commentary.
    Requires ANTHROPIC_API_KEY environment variable.

    Add to your Render / Railway env vars:
      ANTHROPIC_API_KEY = sk-ant-...
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(status_code=503, content={
            "detail": "ANTHROPIC_API_KEY not configured. Add it to your deployment environment variables."
        })
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=request.get("model", "claude-sonnet-4-6"),
            max_tokens=request.get("max_tokens", 1000),
            messages=request.get("messages", []),
        )
        return {"content": [{"type": "text", "text": msg.content[0].text}]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Claude API error: {str(e)}"})
