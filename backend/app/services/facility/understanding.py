# -*- coding: utf-8 -*-
"""Facility Understanding Engine (Phase 4 S3). Answers "what is in front of me?"
Its SOLE output is an evidence-based `FacilityProfile` (Rule 1). Every conclusion
is an `Inference` with evidence + confidence (Rule 2); when it cannot prove a
thing it reports `Unknown` rather than guessing (No Guess Without Evidence). It
reads the Industrial Knowledge Graph (knowledge, not conclusions — Rule 3) and
produces no audit/decision.

Input is the L1-interpreted upload: `signal_map` (canonical field → source column,
from ingestion alias resolution), the resolved `specs`, and the `time_series`.
"""
from typing import Any, Dict, List, Optional

from app.knowledge.graph import build_graph
from app.domain.canonical.profile import (
    Evidence, Inference, ProfiledEquipment, FacilityProfile,
)


def understand(
    signal_map: Dict[str, str],
    specs: Dict[str, Any],
    time_series: List[Dict[str, Any]],
    intent: str = "arbitrage",
    intent_source: str = "default",
    extra_columns: Optional[List[str]] = None,
    currency: str = "USD",
    dt_hours: float = 1.0,
    facility_id: str = "facility",
) -> FacilityProfile:
    g = build_graph()
    present = set(signal_map.keys())

    # ── Capabilities implied by the present signals (evidence = matched fields) ──
    cap_infs: List[Inference] = []
    for cid, matched, total in g.capabilities_from_signals(present):
        cap_infs.append(Inference(
            value=cid, confidence=round(len(matched) / total, 2) if total else 0.0,
            source="signal", rule="CAP-SIGNAL-MATCH",
            evidence=[Evidence(signal=f) for f in sorted(matched)],
        ))

    # ── Equipment identity from the behavioral capability (No-Guess if none) ──
    behavioral = next((ci for ci in cap_infs if g.archetype_of(ci.value)), None)
    if behavioral is not None:
        arche = g.archetype_of(behavioral.value)
        ev = [Evidence("capability", behavioral.value)]
        if specs.get("asset_type"):
            ev.append(Evidence("asset_type", specs["asset_type"]))
        identity = Inference(
            value=specs.get("asset_type") or f"{arche}_unit",
            confidence=behavioral.confidence, source="ontology",
            rule="EQUIP-FROM-CAPABILITY", evidence=ev,
        )
    else:
        identity = Inference(
            value="Unknown", confidence=0.0, source="ontology", rule="EQUIP-NOGUESS",
            evidence=[Evidence("signals", ",".join(sorted(present)) or "none")],
        )

    # ── Signal grounding (evidence = the matched header) ──
    signal_map_inf = {
        field_: Inference(value=col, confidence=1.0, source="alias", rule="ALIAS-MATCH",
                          evidence=[Evidence("header", value=col)])
        for field_, col in signal_map.items()
    }

    equipment = [ProfiledEquipment(
        identity=identity, capabilities=cap_infs, specs=dict(specs),
        signal_map=signal_map_inf, time_series=list(time_series),
    )]

    # ── Facility type — recognized composition, else Unknown (No-Guess) ──
    recognized = {ci.value for ci in cap_infs}
    patterns = g.facility_patterns_matching(recognized)
    if patterns:
        pid, disp, matched, total = patterns[0]
        facility_type = Inference(
            value=disp, confidence=round(len(matched) / total, 2), source="ontology",
            rule="FACILITY-PATTERN",
            evidence=[Evidence("capability", c) for c in sorted(matched)],
            alternatives=[Inference(value=g.facility_patterns[p]["display_name"],
                                    confidence=round(len(m) / t, 2), source="ontology")
                          for p, _d, m, t in patterns[1:]],
        )
    else:
        facility_type = Inference(
            value="Unknown", confidence=0.0, source="ontology", rule="FACILITY-NOGUESS",
            evidence=[Evidence("capability", c) for c in sorted(recognized)]
                     or [Evidence("signals", "none")],
        )

    intent_inf = Inference(value=intent, confidence=1.0, source=intent_source, rule=None)

    return FacilityProfile(
        facility_type=facility_type, equipment=equipment, intent=intent_inf,
        currency=currency, dt_hours=dt_hours, facility_id=facility_id,
        unknowns=list(extra_columns or []),
    )
