# -*- coding: utf-8 -*-
"""Knowledge Engineering Workflow (Phase 6) — turn "add an industry" into a
repeatable, MEASURABLE engineering loop instead of hand-authoring packs.

Given a real dataset it runs the understanding pipeline and reports exactly WHAT
KNOWLEDGE IS MISSING to recognize the facility:

    Real Dataset → Facts → Missing-Facts → Pattern-Coverage → Unknown Equipment
    → Unknown Capabilities → Ontology-Gap Report → (author pack) → Re-run
    → Recognition Score

The score is objective, so a pack edit's effect is measurable ("62% → 97%").
Nothing here is industry-specific; it works for any dataset (Principle 8).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.knowledge.graph import build_graph
from app.knowledge.registry import load_packs
from app.services.ingestion import _resolve_columns
from app.services.facility.patterns import extract_facts, match_pattern
from app.services.facility import understand


@dataclass
class GapReport:
    recognition_score: float                       # 0-100 objective recognition
    grounded_columns: Dict[str, str]               # canonical field -> source column
    ungrounded_columns: List[str]                  # candidate NEW signals (author aliases/patterns)
    facts_present: List[str]
    pattern_coverage: List[Tuple[str, float, Optional[str]]]  # (pattern_id, match_ratio, fired_concept)
    missing_facts_for_partial: Dict[str, List[str]]           # pattern_id -> predicate facts it lacks
    recognized_equipment: str
    recognized_capabilities: List[str]
    facility_hypothesis: str
    facility_confidence: float
    ontology_gaps: List[str]                       # references to undefined concepts

    def render(self) -> str:
        L = [f"KNOWLEDGE ENGINEERING REPORT — recognition score: {self.recognition_score:.1f} / 100", ""]
        L.append(f"Facility hypothesis : {self.facility_hypothesis} "
                 f"({self.facility_confidence*100:.0f}%)")
        L.append(f"Recognized equipment: {self.recognized_equipment}")
        L.append(f"Recognized capabilities: {', '.join(self.recognized_capabilities) or '(none)'}")
        L.append("")
        L.append(f"Grounded signals ({len(self.grounded_columns)}): "
                 + ", ".join(f"{k}←{v}" for k, v in self.grounded_columns.items()))
        if self.ungrounded_columns:
            L.append(f"UNGROUNDED columns ({len(self.ungrounded_columns)}) — candidate new signals: "
                     + ", ".join(self.ungrounded_columns))
        L.append("")
        L.append("Pattern coverage:")
        for pid, ratio, fired in self.pattern_coverage:
            tag = f"FIRED → {fired}" if fired else ("partial" if ratio > 0 else "no match")
            L.append(f"  {pid:<22} {ratio*100:5.0f}%  {tag}")
        if self.missing_facts_for_partial:
            L.append("")
            L.append("To complete a partially-matched pattern, supply these facts:")
            for pid, facts in self.missing_facts_for_partial.items():
                L.append(f"  {pid}: needs {', '.join(facts)}")
        if self.ontology_gaps:
            L.append("")
            L.append(f"ONTOLOGY GAPS ({len(self.ontology_gaps)}) — referenced but undefined:")
            for g in self.ontology_gaps:
                L.append(f"  • {g}")
        return "\n".join(L)


def _ontology_gaps() -> List[str]:
    """Referential integrity of the knowledge base: every id a pack references
    (capability/kpi/constraint/equipment) must have a defining pack."""
    packs = load_packs()
    ids = {kind: {p.id for p in packs.values() if p.kind == kind}
           for kind in ("capability", "equipment", "kpi", "constraint", "units", "process")}
    gaps: List[str] = []

    def _need(kind, ref, where):
        if ref not in ids.get(kind, set()):
            gaps.append(f"{where} → {kind}:{ref} (undefined)")

    for p in packs.values():
        if p.kind == "capability":
            for k in p.kpis: _need("kpi", k, f"capability:{p.id}")
            for c in p.constraints: _need("constraint", c, f"capability:{p.id}")
        elif p.kind == "equipment":
            for cap in p.exhibits: _need("capability", cap, f"equipment:{p.id}")
            for k in p.kpis: _need("kpi", k, f"equipment:{p.id}")
            for c in p.constraints: _need("constraint", c, f"equipment:{p.id}")
        elif p.kind == "pattern":
            for im in p.implies:
                _need(im.concept_kind, im.concept, f"pattern:{p.id}")
        elif p.kind == "recognition" and p.tier == "facility":
            for cap in p.typical_capabilities: _need("capability", cap, f"facility:{p.id}")
            for eq in p.typical_equipment: _need("equipment", eq, f"facility:{p.id}")
    return sorted(set(gaps))


def analyze_dataset(columns: List[str], metadata: Optional[Dict[str, Any]] = None,
                    specs: Optional[Dict[str, Any]] = None) -> GapReport:
    """Run the full understanding pipeline over a dataset's COLUMNS (+ optional
    nameplate metadata) and report the knowledge gaps + a recognition score."""
    g = build_graph()
    specs = specs or {}
    signal_map = _resolve_columns(list(columns))                 # canonical field -> column
    grounded_cols = set(signal_map.values())
    ungrounded = [c for c in columns if c not in grounded_cols]

    facts = extract_facts(signal_map, specs, metadata)
    fact_names = set(facts)

    # Pattern coverage + missing facts for partial matches
    coverage: List[Tuple[str, float, Optional[str]]] = []
    missing_partial: Dict[str, List[str]] = {}
    for pid, pack in g.patterns.items():
        total = sum(p.weight for p in pack.predicates) or 0.0
        matched = [p for p in pack.predicates if _pred_ok(p, facts)]
        ratio = (sum(p.weight for p in matched) / total) if total else 0.0
        a = match_pattern(pack, facts)
        coverage.append((pid, round(ratio, 2), a.concept if a else None))
        # Not fully satisfied AND either nothing fired or only the general
        # (needs_more_evidence) tier did → supplying the missing facts would push
        # it toward the more-specific concept. A confidently-fired pattern needs nothing.
        if 0 < ratio < 1.0 and (a is None or a.needs_more_evidence):
            missing_partial[pid] = [p.fact for p in pack.predicates if p not in matched
                                    and p.op != "absent"]
    coverage.sort(key=lambda t: -t[1])

    profile = understand(signal_map, specs, [], metadata=metadata, extra_columns=ungrounded)
    eq = profile.equipment[0]
    caps = [c.value for c in eq.capabilities]

    # Objective recognition score (0-100)
    grounding = (len(signal_map) / len(columns)) if columns else 0.0
    cap_ok = 1.0 if caps else 0.0
    equip_ok = 1.0 if eq.identity.value not in ("Unknown",) else 0.0
    fac_conf = profile.facility_type.confidence or 0.0
    score = round(100.0 * (0.30 * grounding + 0.25 * cap_ok + 0.20 * equip_ok + 0.25 * fac_conf), 1)

    return GapReport(
        recognition_score=score,
        grounded_columns=dict(signal_map),
        ungrounded_columns=ungrounded,
        facts_present=sorted(fact_names),
        pattern_coverage=coverage,
        missing_facts_for_partial=missing_partial,
        recognized_equipment=eq.identity.value,
        recognized_capabilities=caps,
        facility_hypothesis=profile.facility_type.value,
        facility_confidence=fac_conf,
        ontology_gaps=_ontology_gaps(),
    )


def _pred_ok(pred, facts) -> bool:
    # local mirror of the matcher's predicate test (kept private to patterns.py)
    from app.services.facility.patterns import _match_predicate
    return _match_predicate(pred, facts)
