# -*- coding: utf-8 -*-
"""Knowledge Pack schemas (Phase 4, Layer 4 · rev 3 Industrial Ontology).

Every pack describes exactly ONE ontology tier and is pure DATA (YAML) — no logic,
no industry. Packs REFERENCE other concepts by id; they never inline another tier.
The seven kinds, discriminated on `kind`:

    units · kpi · constraint · capability · equipment · process · recognition

Ontology ladder: Signal -> Equipment -> Capability -> Process -> Facility. A
`capability` maps (if behavioral) to one of the engine's frozen archetypes; it
never invents engine behavior (Law 1: Immutable Engine).
"""
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

# The four physics archetypes the FROZEN engine routes on (optimization_service).
ARCHETYPES = {"storage", "intermittent", "dispatchable", "load"}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str


class UnitsPack(_Base):
    kind: Literal["units"]
    units: List[str] = []
    conversions: Dict[str, float] = {}


class KpiPack(_Base):
    kind: Literal["kpi"]
    name: str
    formula: Optional[str] = None
    unit: Optional[str] = None
    applies_to: List[str] = []


class ConstraintPack(_Base):
    kind: Literal["constraint"]
    parameters: Dict[str, Any] = {}
    applies_to: List[str] = []


class CapabilityPack(_Base):
    kind: Literal["capability"]
    # 'class' is a Python keyword — accept the YAML key `class`, expose `capability_class`.
    capability_class: Literal["behavioral", "descriptive"] = Field(alias="class")
    archetype: Optional[str] = None          # behavioral -> one of ARCHETYPES; descriptive -> null
    signals: List[str] = []                  # canonical fields this capability drives
    kpis: List[str] = []                     # kpi pack ids
    constraints: List[str] = []              # constraint pack ids
    adds_units: List[str] = []

    @model_validator(mode="after")
    def _archetype_matches_class(self):
        if self.capability_class == "behavioral":
            if self.archetype not in ARCHETYPES:
                raise ValueError(
                    f"behavioral capability '{self.id}' needs archetype in {sorted(ARCHETYPES)}"
                )
        elif self.archetype is not None:
            raise ValueError(f"descriptive capability '{self.id}' must have archetype: null")
        return self


class EquipmentPack(_Base):
    kind: Literal["equipment"]
    exhibits: List[str] = []                 # capability ids it has
    terminology: List[str] = []
    column_aliases: Dict[str, List[str]] = {}   # signal headers this equipment is known by
    kpis: List[str] = []
    constraints: List[str] = []


class ProcessPack(_Base):
    kind: Literal["process"]
    involves_capabilities: List[str] = []
    involves_equipment: List[str] = []
    stages: List[str] = []
    couplings: List[Dict[str, Any]] = []     # cross-stage links (surfaced, not co-optimized in P4)
    kpis: List[str] = []
    constraints: List[str] = []


class Predicate(BaseModel):
    """One condition over a Level-1 Fact."""
    model_config = ConfigDict(extra="forbid")
    fact: str
    op: Literal["gt", "ge", "lt", "le", "eq", "present"]
    value: Any = None                        # unused for op == present
    weight: float = 1.0


class Implication(BaseModel):
    """What a pattern implies at a given match completeness. Most-specific has the
    highest `min_match`; a partial match falls back to the more general concept."""
    model_config = ConfigDict(extra="forbid")
    concept: str
    concept_kind: Literal["equipment", "capability"] = "equipment"
    min_match: float = 1.0                   # fraction of predicate weight required
    confidence: float = 0.5
    needs_more_evidence: bool = False


class PatternPack(_Base):
    kind: Literal["pattern"]
    # Industrial Evidence Pattern (Level 2): a bundle of evidence, not a rule.
    predicates: List[Predicate] = []
    implies: List[Implication] = []


class IntentPack(_Base):
    kind: Literal["intent"]
    display_name: Optional[str] = None
    # Operational Intent influences ONLY constraint generation + to_wire (Law 1).
    # Declarative: the Composer/to_wire apply these generically (no `if intent ==`).
    constraints: List[str] = []              # constraint pack ids this intent generates
    wire_params: Dict[str, Any] = {}         # declarative params the adapter reads


class RecognitionPack(_Base):
    kind: Literal["recognition"]
    tier: Literal["signal", "facility"]
    # tier == "signal": header -> canonical-field alias tables (the S1 monolith lives here
    # transitionally; S4 redistributes header aliases to their owning equipment packs).
    column_aliases: Dict[str, List[str]] = {}
    asset_meta_aliases: Dict[str, List[str]] = {}
    # tier == "facility" (S4): a named composition label — NO behavior.
    display_name: Optional[str] = None
    typical_capabilities: List[str] = []
    typical_equipment: List[str] = []


Pack = Annotated[
    Union[UnitsPack, KpiPack, ConstraintPack, CapabilityPack, EquipmentPack, ProcessPack,
          PatternPack, IntentPack, RecognitionPack],
    Field(discriminator="kind"),
]
_PACK_ADAPTER: TypeAdapter = TypeAdapter(Pack)


def parse_pack(raw: Dict[str, Any]) -> Pack:
    """Validate a raw dict into exactly one pack kind (discriminated on `kind`)."""
    return _PACK_ADAPTER.validate_python(raw)
