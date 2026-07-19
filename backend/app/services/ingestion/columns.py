# -*- coding: utf-8 -*-
"""Column resolution — maps arbitrary uploaded headers to the canonical schema
via alias tables + fuzzy matching.

Public API: COLUMN_ALIASES, ASSET_META_ALIASES, _FUZZY_THRESHOLD,
_resolve_columns_verbose, _resolve_columns.
Dependencies: ingestion._primitives (_normalise_col). Extracted VERBATIM.
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

from app.services.ingestion._primitives import _normalise_col  # noqa: F401


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
