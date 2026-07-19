# -*- coding: utf-8 -*-
"""Ingestion + data-quality service (package).

Turns a raw uploaded file into a clean, quality-assessed DataFrame + DQ flags/
indices. Split from a single 1015-line module into cohesive submodules (approved
boundary review, ADR 0005); this __init__ re-exports the public surface VERBATIM
so callers (main.py) import from `app.services.ingestion` unchanged.

Internal dependency direction (all services-tier; no economic math, no business
rules): formats -> columns -> _primitives; {timestamps, values, quality} ->
_primitives. NO cross-layer imports.

Submodules: _primitives, formats, columns, timestamps, values, quality.
"""
from app.services.ingestion._primitives import _normalise_col, _dq  # noqa: F401
from app.services.ingestion.columns import COLUMN_ALIASES, ASSET_META_ALIASES, _FUZZY_THRESHOLD, _resolve_columns_verbose, _resolve_columns  # noqa: F401
from app.services.ingestion.timestamps import _detect_excel_serial_timestamps, _TIMESTAMP_FORMAT_ATTEMPTS, _parse_timestamps, _fill_ts_bounds, _detect_and_resample, _order_and_dedupe_timestamps  # noqa: F401
from app.services.ingestion.values import _detect_and_apply_units, _coerce_numeric_columns, _detect_currency  # noqa: F401
from app.services.ingestion.quality import _build_sensor_quality_flags, _collect_data_quality_counts, _dqi_components_from_manifest, _forecast_reliability_from_snapshot  # noqa: F401
from app.services.ingestion.formats import _looks_numeric, _fix_banner_header, _parse_file_bytes, _parse_file_bytes_raw  # noqa: F401

__all__ = [
    "COLUMN_ALIASES",
    "ASSET_META_ALIASES",
    "_normalise_col",
    "_FUZZY_THRESHOLD",
    "_resolve_columns_verbose",
    "_resolve_columns",
    "_detect_and_apply_units",
    "_detect_excel_serial_timestamps",
    "_TIMESTAMP_FORMAT_ATTEMPTS",
    "_parse_timestamps",
    "_fill_ts_bounds",
    "_detect_and_resample",
    "_dq",
    "_order_and_dedupe_timestamps",
    "_coerce_numeric_columns",
    "_build_sensor_quality_flags",
    "_collect_data_quality_counts",
    "_dqi_components_from_manifest",
    "_forecast_reliability_from_snapshot",
    "_detect_currency",
    "_looks_numeric",
    "_fix_banner_header",
    "_parse_file_bytes",
    "_parse_file_bytes_raw",
]
