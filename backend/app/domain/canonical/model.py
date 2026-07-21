# -*- coding: utf-8 -*-
"""Canonical Industrial Model (CIM) — the graph representation (Phase 4 S2).

The CIM is a GRAPH, not a flat spec:

    Facility (intent)
      └── Process[]
            └── Equipment[]
                  ├── signals      { canonical_field -> per-step values }
                  ├── constraints  [Constraint]        (descriptive caps + intent)
                  └── capabilities [CapabilityRef]     (behavioral ⇒ a priced asset)

`CIM.to_wire()` (see to_wire.py) is the SOLE adapter to the frozen engine; it walks
this graph and emits the byte-identical `AssetSpecs + time_series` the engine reads
today. The engine never learns the graph — or the intent — exists (Law 1).

`FacilityProfile` is the Facility-Understanding-Engine (S3) OUTPUT and the Composer
INPUT; defined here as the contract so S2 can prove `to_wire(compose(profile))` is
identity for the BESS/default-intent case without the FUE existing yet.

Pure domain data — depends only on stdlib. No engine, no I/O.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── CIM graph nodes ─────────────────────────────────────────────────────────
@dataclass
class CapabilityRef:
    id: str
    capability_class: str            # "behavioral" | "descriptive"
    archetype: Optional[str] = None  # behavioral ⇒ one of the engine's 4; else None


@dataclass
class Constraint:
    id: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Intent:
    id: str = "arbitrage"            # default: price arbitrage (no-op modifier)
    constraints: List[Constraint] = field(default_factory=list)
    wire_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Equipment:
    id: str
    capabilities: List[CapabilityRef] = field(default_factory=list)
    specs: Dict[str, Any] = field(default_factory=dict)          # AssetSpecs fields
    signals: List[Dict[str, Any]] = field(default_factory=list)  # per-step records (TimeStepData-shaped)
    constraints: List[Constraint] = field(default_factory=list)

    def behavioral(self) -> Optional[CapabilityRef]:
        for c in self.capabilities:
            if c.capability_class == "behavioral" and c.archetype:
                return c
        return None


@dataclass
class Process:
    id: str
    equipment: List[Equipment] = field(default_factory=list)


@dataclass
class Facility:
    id: str
    processes: List[Process] = field(default_factory=list)
    intent: Intent = field(default_factory=Intent)
    currency: str = "USD"
    dt_hours: float = 1.0


# ── Composer input (FUE output contract, S3) ────────────────────────────────
@dataclass
class DetectedEquipment:
    id: str
    capabilities: List[str]                       # capability pack ids, e.g. ["energy_storage"]
    specs: Dict[str, Any]                         # AssetSpecs fields
    time_series: List[Dict[str, Any]]             # per-step records (TimeStepData-shaped)


@dataclass
class FacilityProfile:
    equipment: List[DetectedEquipment]
    intent: str = "arbitrage"
    currency: str = "USD"
    dt_hours: float = 1.0
    facility_id: str = "facility"
