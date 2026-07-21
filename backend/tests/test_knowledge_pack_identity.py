# -*- coding: utf-8 -*-
"""Phase 4 S1 gate — the BESS-pack extraction must be BYTE-IDENTICAL to the former
inline alias monolith. These SHAs were captured from the pre-extraction code
(app/services/ingestion/columns.py) and freeze column-resolution behavior. If
adding/splitting packs later changes resolution, this fails — by design.
"""
import hashlib
import json

from app.services.ingestion import columns as C
from app.knowledge import registry as R

# Fingerprints captured from the pre-Phase-4 inline COLUMN_ALIASES/ASSET_META_ALIASES.
BASELINE_ALIAS_SHA = "54fd2aed1ef0349cae32ba78635d401a4500517695d7ec1a80043e30f6ca7dd2"
BASELINE_RESOLUTION_SHA = "8111ba2bc0114f1f165c74e5934211339f160dace42fc52f9ac19efe095d58c2"

# Representative multi-industry header set (exact + fuzzy + Arabic + meta).
HEADERS = [
    "Timestamp", "spot_price", "bess_discharge_mw", "solar_output", "Charge_MW",
    "SOC_%", "curtailment", "forecast_price", "grid_demand", "operator_override",
    "asset_type", "capacity_mw", "battery_capacity_mwh", "Discharge_MW_avg",
    "PriceUSDperMWh", "h2_production_kg", "water_m3", "fuel_rate", "السعر", "التوليد",
]


def _alias_sha() -> str:
    blob = json.dumps(
        {"COLUMN_ALIASES": C.COLUMN_ALIASES, "ASSET_META_ALIASES": C.ASSET_META_ALIASES},
        ensure_ascii=False, sort_keys=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_alias_tables_byte_identical_after_pack_extraction():
    assert _alias_sha() == BASELINE_ALIAS_SHA


def test_column_resolution_unchanged():
    res = C._resolve_columns_verbose(HEADERS)
    sha = hashlib.sha256(json.dumps(res, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    assert sha == BASELINE_RESOLUTION_SHA


def test_columns_module_sources_from_registry():
    # The tables must be the SAME objects the registry produced (i.e. actually
    # pack-driven, not a re-inlined copy that happens to match).
    assert C.COLUMN_ALIASES == R.merged_column_aliases()
    assert C.ASSET_META_ALIASES == R.merged_asset_meta_aliases()


def test_ontology_packs_load_by_kind():
    packs = R.load_packs()
    # Storage capability (behavioral -> storage archetype), the descriptor.
    assert "energy_storage" in packs
    es = packs["energy_storage"]
    assert es.kind == "capability" and es.capability_class == "behavioral"
    assert es.archetype == "storage"
    # Signal-tier recognition pack carries the (transitional) alias monolith.
    assert "legacy_signal_aliases" in packs
    rec = packs["legacy_signal_aliases"]
    assert rec.kind == "recognition" and rec.tier == "signal"
    # No industry-shaped pack remains (facilities, not industries).
    assert "bess" not in packs
