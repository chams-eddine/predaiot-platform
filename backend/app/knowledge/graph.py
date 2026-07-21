# -*- coding: utf-8 -*-
"""Industrial Knowledge Graph (Phase 4 S3). Assembled at startup from the
Knowledge Packs. It stores INDUSTRIAL KNOWLEDGE — the relationships between
equipment, capabilities, signals, intents and facility patterns — and NOTHING
ELSE (Rule 3: the graph stores knowledge, not conclusions). It holds
`equipment —exhibits→ capability`, `capability —drives→ signals`,
`facility-pattern —typically-has→ {capabilities, equipment}`. It never holds a
"best operating strategy" — that is an economic decision, owned by the frozen
engine.

Imports only its own registry/schema (rank 1). No engine, no services, no domain.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

from app.knowledge.registry import load_packs


@dataclass
class KnowledgeGraph:
    # capability id -> knowledge about it
    capabilities: Dict[str, dict] = field(default_factory=dict)   # {class, archetype, signals:set}
    equipment: Dict[str, dict] = field(default_factory=dict)      # {exhibits:[...], aliases:{...}}
    intents: Dict[str, dict] = field(default_factory=dict)        # {constraints, wire_params}
    facility_patterns: Dict[str, dict] = field(default_factory=dict)  # {display_name, caps, equip}

    # ── knowledge queries (relationships only — never conclusions) ──
    def archetype_of(self, cap_id: str) -> Optional[str]:
        c = self.capabilities.get(cap_id)
        return c["archetype"] if c else None

    def capabilities_from_signals(self, present: Set[str]) -> List[Tuple[str, Set[str], int]]:
        """Which capabilities do the present canonical fields imply? Returns
        (cap_id, matched_signals, total_signals) for every capability with ≥1 match."""
        out = []
        for cid, c in self.capabilities.items():
            sigs: Set[str] = c["signals"]
            matched = sigs & present
            if matched:
                out.append((cid, matched, len(sigs)))
        return sorted(out, key=lambda t: (-len(t[1]), t[0]))

    def facility_patterns_matching(self, cap_ids: Set[str]) -> List[Tuple[str, str, Set[str], int]]:
        """Facility-type candidates from recognized capabilities. Returns
        (pattern_id, display_name, matched_caps, total_caps). Empty until facility
        recognition packs are authored (S4) → the FUE reports Unknown (No-Guess)."""
        out = []
        for pid, p in self.facility_patterns.items():
            typ: Set[str] = set(p["caps"])
            matched = typ & cap_ids
            if matched:
                out.append((pid, p["display_name"], matched, len(typ) or 1))
        return sorted(out, key=lambda t: -len(t[2]))


@lru_cache(maxsize=1)
def build_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    for pack in load_packs().values():
        if pack.kind == "capability":
            g.capabilities[pack.id] = {
                "class": pack.capability_class,
                "archetype": pack.archetype,
                "signals": set(pack.signals),
            }
        elif pack.kind == "equipment":
            g.equipment[pack.id] = {"exhibits": list(pack.exhibits), "aliases": dict(pack.column_aliases)}
        elif pack.kind == "intent":
            g.intents[pack.id] = {"constraints": list(pack.constraints), "wire_params": dict(pack.wire_params)}
        elif pack.kind == "recognition" and pack.tier == "facility":
            g.facility_patterns[pack.id] = {
                "display_name": pack.display_name or pack.id,
                "caps": list(pack.typical_capabilities),
                "equip": list(pack.typical_equipment),
            }
    return g
