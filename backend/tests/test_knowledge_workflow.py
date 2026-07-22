# -*- coding: utf-8 -*-
"""Phase 6 gate — the Knowledge Engineering Workflow. Given an UNRECOGNIZED
dataset it must (1) score low, (2) list the ungrounded columns as candidate new
signals, (3) admit Unknown (No-Guess), (4) surface real ontology gaps. Given a
recognized dataset it must score high. This makes "add an industry" measurable.
"""
from app.services.facility.gap_analysis import analyze_dataset


def test_unrecognized_dataset_reports_gaps():
    # A cement-like file the ontology does NOT yet know.
    cols = ["timestamp", "price", "kiln_power_mw", "clinker_tph", "raw_mill_kw", "kiln_speed_rpm"]
    r = analyze_dataset(cols)
    assert r.facility_hypothesis == "Unknown"                 # No-Guess
    assert r.recognition_score < 60                           # clearly incomplete
    # the cement-specific columns are surfaced as candidate new signals
    assert any("kiln" in c for c in r.ungrounded_columns)
    assert any("clinker" in c for c in r.ungrounded_columns)


def test_recognized_dataset_scores_high():
    # A battery dataset the ontology DOES know.
    cols = ["timestamp", "price", "bess_discharge_mw", "charge_mw", "soc_pct"]
    r = analyze_dataset(cols)
    assert "energy_storage" in r.recognized_capabilities
    assert r.recognition_score >= 40


def test_partial_match_lists_missing_facts():
    # Transformer + voltage but no rated power → EAF pattern partially matches.
    r = analyze_dataset(["timestamp", "price"],
                        metadata={"transformer_mva": 30, "voltage_primary": 33000})
    cov = {pid: (ratio, fired) for pid, ratio, fired in r.pattern_coverage}
    assert 0 < cov["eaf_high_power"][0] < 1.0                  # partial, not fired
    assert "eaf_high_power" in r.missing_facts_for_partial
    assert "rated_power_mw" in r.missing_facts_for_partial["eaf_high_power"]


def test_ontology_gaps_detected():
    # Referential integrity: the demo KB references concepts with no defining pack
    # (e.g. eaf_high_power implies high_power_furnace, which has no equipment pack;
    # capabilities reference kpi/constraint ids not yet authored).
    r = analyze_dataset(["price", "soc", "charge_mw", "discharge_mw"])
    assert any("high_power_furnace" in g for g in r.ontology_gaps)
    assert any(g.startswith("capability:") or g.startswith("equipment:") for g in r.ontology_gaps)
