# -*- coding: utf-8 -*-
"""CIM → frozen engine adapter (Phase 4 S2). `to_wire()` is the SOLE boundary at
which the graph CIM becomes the engine's immutable interface. It walks the
Facility graph and emits, per PRICED asset (an equipment carrying a behavioral
capability), the exact `AssetSpecs + time_series` the engine reads today.

Operational Intent influences the audit ONLY here + in constraint generation
(Law 1): `intent.wire_params` may reshape the emitted specs (e.g. a maintenance
intent caps `p_max`); the DEFAULT `arbitrage` intent carries empty params, so the
BESS path is byte-identical. The engine never sees the graph or the intent.

Imports only `app.schemas` (rank 0, downward). Never the engine.
"""
from dataclasses import dataclass
from typing import Any, Dict, List

from app.schemas import AssetSpecs
from app.domain.canonical.model import Facility


@dataclass
class WireAsset:
    """One priced asset in the frozen engine's input shape."""
    asset: AssetSpecs
    time_series: List[Dict[str, Any]]
    dt_hours: float


def to_wire(facility: Facility) -> List[WireAsset]:
    """Flatten the CIM graph into the frozen engine interface — one WireAsset per
    equipment that carries a behavioral capability (a dispatch archetype)."""
    out: List[WireAsset] = []
    intent = facility.intent
    spec_overrides: Dict[str, Any] = dict(intent.wire_params.get("specs", {}))  # empty for arbitrage

    for process in facility.processes:
        for eq in process.equipment:
            if eq.behavioral() is None:
                continue  # descriptive-only equipment is not independently priced
            specs = {**eq.specs, **spec_overrides}
            out.append(WireAsset(
                asset=AssetSpecs(**specs),
                time_series=list(eq.signals),
                dt_hours=facility.dt_hours,
            ))
    return out
