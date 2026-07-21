# -*- coding: utf-8 -*-
"""PackSchema — the strict, DATA-ONLY contract every Knowledge Pack must satisfy
(Phase 4, Layer 4). A pack DESCRIBES an industry; it contains NO business logic.
Because packs are YAML validated by this model, they physically cannot carry
code, and `arch_graph` forbids `app.knowledge` from importing the engine.

A new industry (incl. one that does not exist today) is added by dropping a new
`packs/<industry>/pack.yaml` that conforms to this schema — no change to the
Engine, the Canonical Model, or Mission Control (the future-proof contract).
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

# The four physics archetypes the FROZEN engine already routes on
# (optimization_service._dispatch_mode). A pack MUST map its industry to one of
# these — it never invents optimization behavior.
ARCHETYPES = {"storage", "intermittent", "dispatchable", "load"}


class Recognition(BaseModel):
    """Signal signature used by Layer 2 (industry recognition). Descriptive only."""
    model_config = ConfigDict(extra="forbid")
    strong_signals: List[str] = []      # column/field names that strongly imply this industry
    units_seen: List[str] = []          # engineering units typical of it (t, kWh/t, m³, …)
    keywords: List[str] = []            # free-text tokens seen in headers/metadata


class KnowledgePack(BaseModel):
    """One industry, described. No logic — data the platform reads."""
    model_config = ConfigDict(extra="forbid")

    industry: str                        # stable id, e.g. "steel"
    display_name: str                    # human label, e.g. "Steel Manufacturing"
    archetype: str                       # one of ARCHETYPES — reuses the engine's routing
    asset_family: List[str] = []         # equipment classes, e.g. [electric_arc_furnace, ...]

    recognition: Recognition = Recognition()

    # Header → canonical-field alias tables (the S1 extraction target).
    column_aliases: Dict[str, List[str]] = {}
    asset_meta_aliases: Dict[str, List[str]] = {}

    # Descriptive metadata (used by L2/L5; never by the engine).
    kpis: List[str] = []
    constraints: List[str] = []
    defaults: Dict[str, float] = {}      # default AssetSpecs numerics for this industry
    labels: Dict[str, Optional[str]] = {}  # canonical-field → UI label (None hides it)

    @field_validator("archetype")
    @classmethod
    def _archetype_known(cls, v: str) -> str:
        if v not in ARCHETYPES:
            raise ValueError(
                f"archetype '{v}' is not one of {sorted(ARCHETYPES)}. A pack maps to an "
                "existing physics archetype; it must not invent engine behavior."
            )
        return v
