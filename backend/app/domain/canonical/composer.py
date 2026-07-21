# -*- coding: utf-8 -*-
"""Capability Composer (Phase 4 S2) — Equipment → Capabilities → Processes →
Intent → Facility. Generic PLATFORM logic (not a pack). It keys ONLY on declared
capability/intent PROPERTIES read from Knowledge Packs — never on capability or
industry NAMES (Law 2). It resolves:

  * each capability id → its class + archetype (from `capability` packs)
  * the facility intent id → its constraints + wire_params (from `intent` packs)

and assembles the CIM graph. It imports the knowledge registry (rank 1, downward)
and never the engine (Law 1).
"""
from typing import Dict

from app.knowledge.registry import load_packs
from app.domain.canonical.model import (
    CapabilityRef, Constraint, Intent, Equipment, Process, Facility, ResolvedProfile,
)


def _capability_index() -> Dict[str, object]:
    return {p.id: p for p in load_packs().values() if p.kind == "capability"}


def _intent_index() -> Dict[str, object]:
    return {p.id: p for p in load_packs().values() if p.kind == "intent"}


def _resolve_capability(cap_id: str, caps: Dict[str, object]) -> CapabilityRef:
    pack = caps.get(cap_id)
    if pack is None:
        # Unknown capability id: carry it as descriptive/no-archetype rather than guess.
        return CapabilityRef(id=cap_id, capability_class="descriptive", archetype=None)
    return CapabilityRef(id=pack.id, capability_class=pack.capability_class, archetype=pack.archetype)


def _resolve_intent(intent_id: str, intents: Dict[str, object]) -> Intent:
    pack = intents.get(intent_id)
    if pack is None:
        return Intent(id=intent_id)                       # unknown → treated as no-op
    return Intent(
        id=pack.id,
        constraints=[Constraint(id=c) for c in pack.constraints],
        wire_params=dict(pack.wire_params),
    )


def compose(profile: ResolvedProfile) -> Facility:
    """Compose a resolved facility view into the CIM graph."""
    caps = _capability_index()
    intents = _intent_index()

    equipment = []
    for det in profile.equipment:
        refs = [_resolve_capability(cid, caps) for cid in det.capabilities]
        equipment.append(Equipment(
            id=det.id,
            capabilities=refs,
            specs=dict(det.specs),
            signals=list(det.time_series),
        ))

    # S2: one default process holding the facility's equipment. `process` packs
    # refine the grouping in S4; the audit is unaffected by the grouping.
    process = Process(id="default", equipment=equipment)
    intent = _resolve_intent(profile.intent, intents)

    return Facility(
        id=profile.facility_id, processes=[process], intent=intent,
        currency=profile.currency, dt_hours=profile.dt_hours,
    )
