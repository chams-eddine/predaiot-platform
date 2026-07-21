# -*- coding: utf-8 -*-
"""Facility Understanding Engine (Phase 4 S3, S4 pattern-based). Answers "what is
in front of me?" Its SOLE output is an evidence-based `FacilityProfile` (Rule 1).
Every conclusion is an `Inference` with evidence + confidence (Rule 2); it reads
the Knowledge Graph (Rule 3) and, per rev 6, reasons through the Industrial
Evidence Patterns:

    Facts (Level 1) → Evidence Patterns (Level 2) → Concepts (Level 3) → FacilityProfile

Partial evidence downgrades a conclusion to a more general concept rather than
guessing the specific one (No Guess Without Evidence).
"""
from typing import Any, Dict, List, Optional

from app.knowledge.graph import build_graph
from app.services.facility.patterns import extract_facts, match_patterns, ConceptAssertion
from app.domain.canonical.profile import (
    Evidence, Inference, ProfiledEquipment, FacilityProfile,
)


def _assertion_to_inference(a: ConceptAssertion, source="pattern") -> Inference:
    return Inference(
        value=a.concept, confidence=a.confidence, source=source,
        rule=f"PATTERN:{a.pattern_id}",
        evidence=[Evidence(f) for f in a.matched_facts],
        alternatives=[Inference(value=alt["concept"], confidence=alt["confidence"], source=source)
                      for alt in a.alternatives],
    )


def understand(
    signal_map: Dict[str, str],
    specs: Dict[str, Any],
    time_series: List[Dict[str, Any]],
    intent: str = "arbitrage",
    intent_source: str = "default",
    metadata: Optional[Dict[str, Any]] = None,
    extra_columns: Optional[List[str]] = None,
    currency: str = "USD",
    dt_hours: float = 1.0,
    facility_id: str = "facility",
) -> FacilityProfile:
    g = build_graph()

    # Level 1 → 2 → 3: facts → patterns → concept assertions
    facts = extract_facts(signal_map, specs, metadata)
    assertions = match_patterns(facts, g.patterns)
    equip_as = [a for a in assertions if a.concept_kind == "equipment"]
    cap_as = [a for a in assertions if a.concept_kind == "capability"]

    capability_infs: List[Inference] = []
    if equip_as:
        primary = equip_as[0]
        identity = _assertion_to_inference(primary, source="pattern")
        identity.rule = f"PATTERN:{primary.pattern_id}"
        # equipment → its capabilities (Capability Map)
        for cid in g.capabilities_of_equipment(primary.concept):
            capability_infs.append(Inference(
                value=cid, confidence=primary.confidence, source="ontology", rule="EXHIBITS",
                evidence=[Evidence("equipment", primary.concept)]))
    elif cap_as:
        capability_infs = [_assertion_to_inference(a) for a in cap_as]
        behavioral = next((ci for ci in capability_infs if g.archetype_of(ci.value)), capability_infs[0])
        arche = g.archetype_of(behavioral.value)
        ev = [Evidence("capability", behavioral.value)]
        if specs.get("asset_type"):
            ev.append(Evidence("asset_type", specs["asset_type"]))
        identity = Inference(
            value=specs.get("asset_type") or (f"{arche}_unit" if arche else "unit"),
            confidence=behavioral.confidence, source="ontology",
            rule="EQUIP-FROM-CAPABILITY", evidence=ev)
    else:
        # No pattern fired — No Guess Without Evidence.
        identity = Inference(
            value="Unknown", confidence=0.0, source="ontology", rule="NO-PATTERN-MATCH",
            evidence=[Evidence("facts", ",".join(sorted(facts)) or "none")])

    # signal grounding (evidence = the matched header)
    signal_map_inf = {
        f: Inference(value=col, confidence=1.0, source="alias", rule="ALIAS-MATCH",
                     evidence=[Evidence("header", value=col)])
        for f, col in signal_map.items()
    }

    equipment = [ProfiledEquipment(
        identity=identity, capabilities=capability_infs, specs=dict(specs),
        signal_map=signal_map_inf, time_series=list(time_series))]

    # facility type — recognized composition, else Unknown (No-Guess)
    recognized = {ci.value for ci in capability_infs}
    fac_matches = g.facility_patterns_matching(recognized)
    if fac_matches:
        pid, disp, matched, total = fac_matches[0]
        facility_type = Inference(
            value=disp, confidence=round(len(matched) / total, 2), source="ontology",
            rule="FACILITY-PATTERN",
            evidence=[Evidence("capability", c) for c in sorted(matched)],
            alternatives=[Inference(value=g.facility_patterns[p]["display_name"],
                                    confidence=round(len(m) / t, 2), source="ontology")
                          for p, _d, m, t in fac_matches[1:]])
    else:
        facility_type = Inference(
            value="Unknown", confidence=0.0, source="ontology", rule="FACILITY-NOGUESS",
            evidence=[Evidence("capability", c) for c in sorted(recognized)] or [Evidence("facts", "none")])

    intent_inf = Inference(value=intent, confidence=1.0, source=intent_source, rule=None)

    return FacilityProfile(
        facility_type=facility_type, equipment=equipment, intent=intent_inf,
        currency=currency, dt_hours=dt_hours, facility_id=facility_id,
        unknowns=list(extra_columns or []))
