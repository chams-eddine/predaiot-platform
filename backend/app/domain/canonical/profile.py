# -*- coding: utf-8 -*-
"""Evidence-based FacilityProfile (Phase 4 S3) — the SOLE output of the Facility
Understanding Engine. Every element is an `Inference {value, confidence, source,
evidence[], rule?, alternatives[]}` — never a bare value (Rule 2: No Guess Without
Evidence). `Unknown` is a first-class outcome.

`resolve()` collapses to the plain `ResolvedProfile` the Composer needs (highest-
confidence interpretation). `explain()` traces every inference to its evidence +
ontology rule (Rule 4: Explainability is a test). This module produces NO audit,
recommendation, or decision (Rule 1).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.domain.canonical.model import ResolvedEquipment, ResolvedProfile


@dataclass
class Evidence:
    signal: str                       # what was observed, e.g. "transformer_rating"
    value: Any = None                 # observed value, if any
    detail: Optional[str] = None

    def __str__(self) -> str:
        if self.value is not None:
            return f"{self.signal}={self.value}"
        return self.signal


@dataclass
class Inference:
    """One evidence-backed conclusion. `source` ∈ ontology|signal|alias|default|user.
    `alternatives` carries the competing hypotheses (the No-Guess distribution)."""
    value: Any
    confidence: float
    source: str
    evidence: List[Evidence] = field(default_factory=list)
    rule: Optional[str] = None
    alternatives: List["Inference"] = field(default_factory=list)

    def is_traceable(self) -> bool:
        # A conclusion is defensible if it rests on evidence, or is an explicit
        # default/user assertion (which needs no signal evidence). A signal/ontology
        # inference with NO evidence is a guess → not traceable (Rule 4).
        return bool(self.evidence) or self.source in ("default", "user")


@dataclass
class ProfiledEquipment:
    identity: Inference                          # value = equipment id / class
    capabilities: List[Inference]                # each value = capability id
    specs: Dict[str, Any]                        # resolved AssetSpecs fields
    signal_map: Dict[str, Inference]             # canonical field -> Inference(value=source column)
    time_series: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FacilityProfile:
    facility_type: Inference                     # value = facility label; alternatives = distribution
    equipment: List[ProfiledEquipment]
    intent: Inference                            # value = intent id
    currency: str = "USD"
    dt_hours: float = 1.0
    facility_id: str = "facility"
    unknowns: List[str] = field(default_factory=list)  # ungrounded columns/signals
    # Ontology-driven digital-twin node chain (source → equipment → sink), built
    # from the recognized archetype + equipment. The frontend RENDERS this — it
    # never decides the topology (Phase 5 golden rule).
    topology: List[Dict[str, Any]] = field(default_factory=list)

    # ── Rule 1: this is the only output; no audit/decision methods live here ──

    def resolve(self) -> ResolvedProfile:
        """Highest-confidence interpretation, as the Composer input."""
        return ResolvedProfile(
            equipment=[ResolvedEquipment(
                id=e.identity.value,
                capabilities=[c.value for c in e.capabilities],
                specs=e.specs, time_series=e.time_series,
            ) for e in self.equipment],
            intent=self.intent.value, currency=self.currency,
            dt_hours=self.dt_hours, facility_id=self.facility_id,
        )

    def all_inferences(self) -> List[Inference]:
        infs = [self.facility_type, self.intent]
        for e in self.equipment:
            infs.append(e.identity)
            infs.extend(e.capabilities)
            infs.extend(e.signal_map.values())
        return infs

    def is_fully_traceable(self) -> bool:
        """Rule 4 gate: every inference must trace to evidence or an explicit default."""
        return all(inf.is_traceable() for inf in self.all_inferences())

    def to_dict(self) -> dict:
        """JSON-safe understanding for the API / frontend (structured + explanation).
        Carries the recognition, not the raw time series."""
        def _inf(i: Inference) -> dict:
            return {"value": i.value, "confidence": i.confidence, "source": i.source,
                    "rule": i.rule, "evidence": [str(e) for e in i.evidence],
                    "alternatives": [{"value": a.value, "confidence": a.confidence}
                                     for a in i.alternatives]}
        return {
            "facility_type": _inf(self.facility_type),
            "intent": _inf(self.intent),
            "equipment": [{
                "identity": _inf(e.identity),
                "capabilities": [_inf(c) for c in e.capabilities],
                "signals": {k: _inf(v) for k, v in e.signal_map.items()},
            } for e in self.equipment],
            "unknowns": list(self.unknowns),
            "topology": list(self.topology),
            "traceable": self.is_fully_traceable(),
            "explanation": self.explain(),
        }

    def explain(self) -> str:
        """Human-readable traceability — every inference → evidence + rule."""
        def _line(label: str, inf: Inference, indent: int = 0) -> str:
            pad = "  " * indent
            rule = f" · rule {inf.rule}" if inf.rule else ""
            ev = ("  ⟵ " + ", ".join(str(e) for e in inf.evidence)) if inf.evidence else ""
            alt = ""
            if inf.alternatives:
                alt = "\n" + pad + "    candidates: " + ", ".join(
                    f"{a.value} ({a.confidence:.2f})" for a in inf.alternatives)
            return f"{pad}{label}: {inf.value} ({inf.confidence:.2f}) ← {inf.source}{rule}{ev}{alt}"

        lines = [f"FACILITY UNDERSTANDING — {self.facility_id}"]
        lines.append(_line("Facility type", self.facility_type))
        lines.append(_line("Intent", self.intent))
        lines.append("Equipment:")
        for e in self.equipment:
            lines.append(_line("Equipment", e.identity, indent=1))
            for c in e.capabilities:
                lines.append(_line("capability", c, indent=2))
            for field_name, inf in e.signal_map.items():
                lines.append(_line(f"signal {field_name}", inf, indent=2))
        if self.unknowns:
            lines.append("Unknowns (ungrounded): " + ", ".join(self.unknowns))
        return "\n".join(lines)
