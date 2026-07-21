# -*- coding: utf-8 -*-
"""Industrial Evidence Patterns engine (Phase 4 S4) — the Level-1→2→3 reasoning
that sits between raw Facts and semantic Concepts. A bundle of evidence forms a
pattern; how COMPLETELY it matches decides whether a specific or a more general
concept is asserted (No Guess Without Evidence — partial evidence downgrades the
conclusion, it never keeps asserting the specific one).

    Facts (Level 1) → Patterns (Level 2) → Concepts (Level 3)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Fact:
    name: str
    value: Any = None
    present: bool = True


@dataclass
class ConceptAssertion:
    concept: str
    concept_kind: str                 # "equipment" | "capability"
    confidence: float
    match_ratio: float
    matched_facts: List[str]
    pattern_id: str
    needs_more_evidence: bool = False
    alternatives: List[dict] = field(default_factory=list)  # other implications as candidates


def extract_facts(signal_map: Dict[str, str], specs: Dict[str, Any],
                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Fact]:
    """Level 1 — derive Facts from the interpreted upload. Signal-presence facts
    (a canonical field is present) + numeric/nameplate facts (from metadata + specs)."""
    facts: Dict[str, Fact] = {}
    for field_name, col in signal_map.items():
        facts[field_name] = Fact(name=field_name, value=col, present=True)
    for k, v in (metadata or {}).items():
        facts[k] = Fact(name=k, value=v, present=True)
    # a rated-power fact is derivable from the asset nameplate if not given explicitly
    if specs.get("p_max") is not None and "rated_power_mw" not in facts:
        facts["rated_power_mw"] = Fact(name="rated_power_mw", value=specs["p_max"], present=True)
    return facts


def _match_predicate(pred, facts: Dict[str, Fact]) -> bool:
    f = facts.get(pred.fact)
    if pred.op == "absent":
        return f is None or not f.present
    if f is None or not f.present:
        return False
    if pred.op == "present":
        return True
    val = f.value
    if val is None:
        return False
    try:
        if pred.op == "gt": return val > pred.value
        if pred.op == "ge": return val >= pred.value
        if pred.op == "lt": return val < pred.value
        if pred.op == "le": return val <= pred.value
        if pred.op == "eq": return val == pred.value
    except TypeError:
        return False
    return False


def match_pattern(pack, facts: Dict[str, Fact]) -> Optional[ConceptAssertion]:
    """Evaluate one Evidence Pattern. Returns the most-specific implication whose
    min_match ≤ match_ratio, or None (No-Guess) when below every threshold."""
    preds = pack.predicates
    total = sum(p.weight for p in preds) or 0.0
    if total <= 0:
        return None
    matched = [p for p in preds if _match_predicate(p, facts)]
    matched_w = sum(p.weight for p in matched)
    ratio = matched_w / total

    # most-specific implication first (highest required match)
    impls = sorted(pack.implies, key=lambda im: im.min_match, reverse=True)
    chosen = next((im for im in impls if ratio >= im.min_match), None)
    if chosen is None:
        return None
    alternatives = [
        {"concept": im.concept, "confidence": im.confidence, "min_match": im.min_match}
        for im in impls if im is not chosen
    ]
    return ConceptAssertion(
        concept=chosen.concept, concept_kind=chosen.concept_kind,
        confidence=chosen.confidence, match_ratio=round(ratio, 2),
        matched_facts=[p.fact for p in matched], pattern_id=pack.id,
        needs_more_evidence=chosen.needs_more_evidence, alternatives=alternatives,
    )


def match_patterns(facts: Dict[str, Fact], patterns: Dict[str, object]) -> List[ConceptAssertion]:
    """Level 2→3 — run every pattern; keep the assertions that fired, best first."""
    out = [a for a in (match_pattern(p, facts) for p in patterns.values()) if a is not None]
    return sorted(out, key=lambda a: -a.confidence)
