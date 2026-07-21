# -*- coding: utf-8 -*-
"""Phase 4 S4 gate — Industrial Evidence Patterns (Facts → Patterns → Concepts) and
the Pattern Stability Test: removing one piece of evidence must DOWNGRADE the
conclusion to a more general concept, never keep asserting the specific one
(No Guess Without Evidence).
"""
from app.knowledge.graph import build_graph
from app.services.facility import understand
from app.services.facility.patterns import extract_facts, match_pattern, Fact


# ── Level 1: Facts extraction ────────────────────────────────────────────────
def test_facts_extraction():
    facts = extract_facts({"price": "p", "soc": "s"}, {"p_max": 50.0}, {"transformer_mva": 30})
    assert facts["price"].present and facts["soc"].present
    assert facts["transformer_mva"].value == 30
    assert facts["rated_power_mw"].value == 50.0            # derived from the nameplate p_max


# ── Level 2→3: the matcher, and Pattern Stability at the pattern level ───────
def test_pattern_matcher_full_partial_and_noguess():
    eaf = build_graph().patterns["eaf_high_power"]
    full = {"transformer_mva": Fact("transformer_mva", 30),
            "voltage_primary": Fact("voltage_primary", 33000),
            "rated_power_mw": Fact("rated_power_mw", 27)}
    a = match_pattern(eaf, full)
    assert a.concept == "electric_arc_furnace" and a.confidence == 0.82 and a.match_ratio == 1.0

    partial = {"transformer_mva": Fact("transformer_mva", 30),
               "voltage_primary": Fact("voltage_primary", 33000)}   # rated_power_mw removed
    a2 = match_pattern(eaf, partial)
    assert a2.concept == "high_power_furnace" and a2.needs_more_evidence is True
    assert a2.concept != "electric_arc_furnace"

    too_little = {"transformer_mva": Fact("transformer_mva", 30)}   # 1/3 → below every threshold
    assert match_pattern(eaf, too_little) is None                   # No-Guess


# ── FUE integration: full EAF evidence → EAF → capabilities → Steel Plant ────
def test_understands_steel_from_evidence_pattern():
    meta = {"transformer_mva": 30, "voltage_primary": 33000, "rated_power_mw": 27}
    prof = understand({}, {}, [], metadata=meta)
    eq = prof.equipment[0]
    assert eq.identity.value == "electric_arc_furnace" and eq.identity.confidence == 0.82
    caps = {c.value for c in eq.capabilities}
    assert {"flexible_load", "thermal"} <= caps                     # via the Capability Map (exhibits)
    assert prof.facility_type.value == "Steel Plant"                # recognized composition
    assert prof.is_fully_traceable()


# ── Pattern Stability at the FUE level (the headline rule) ───────────────────
def test_pattern_stability_downgrades_not_guesses():
    # transformer + voltage present, but NO rated power → must NOT say EAF.
    prof = understand({}, {}, [], metadata={"transformer_mva": 30, "voltage_primary": 33000})
    eq = prof.equipment[0]
    assert eq.identity.value == "high_power_furnace"
    assert eq.identity.value != "electric_arc_furnace"
    assert eq.identity.confidence == 0.54
    # the specific concept survives only as a candidate needing more evidence
    assert any(alt.value == "electric_arc_furnace" for alt in eq.identity.alternatives)
    assert prof.facility_type.value == "Unknown"                    # not enough to name a facility
