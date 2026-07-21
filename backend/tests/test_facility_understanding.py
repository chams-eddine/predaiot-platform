# -*- coding: utf-8 -*-
"""Phase 4 S3 gate — the Facility Understanding Engine and its four rules.
1) FacilityProfile is the ONLY output.  2) evidence-based + confidence (No Guess
Without Evidence).  3) the Knowledge Graph stores knowledge, not conclusions.
4) Explainability is a test — every inference must trace to evidence + rules.
"""
from dataclasses import fields

from app.schemas import AssetSpecs
from app.services.facility import understand
from app.domain.canonical import compose, to_wire, FacilityProfile, Inference, Evidence, ProfiledEquipment
from app.knowledge.graph import build_graph
from app.services.optimization_service import run_optimizer

_PRICES = [10.0, 20.0, 50.0, 15.0, 80.0, 5.0, 60.0, 30.0]
_SIGNAL_MAP = {"price": "spot_price", "actual_discharge": "bess_discharge_mw",
               "actual_charge": "charge_mw", "soc": "soc_pct"}


def _bess_asset() -> AssetSpecs:
    return AssetSpecs(asset_type="BESS", asset_name="T", p_max=50.0, e_max=100.0,
                      soc_init=0.2, eta_ch=0.95, eta_dis=0.95, deg_cost=5.0)


def _ts():
    return [{"hour": i, "price": p, "actual_discharge": 0.0, "actual_charge": 0.0,
             "soc": None, "grid_demand": None, "curtailment_mw": 0.0,
             "operator_override": False, "forecast_price": None}
            for i, p in enumerate(_PRICES)]


def _bess_profile() -> FacilityProfile:
    return understand(_SIGNAL_MAP, _bess_asset().model_dump(), _ts(), intent="arbitrage")


# ── Rule 2: evidence-based understanding ─────────────────────────────────────
def test_understands_bess_with_evidence():
    prof = _bess_profile()
    caps = prof.equipment[0].capabilities
    assert len(caps) == 1 and caps[0].value == "energy_storage"
    assert caps[0].confidence == 1.0                       # all 3 signals present
    ev = {str(e) for e in caps[0].evidence}
    assert {"actual_discharge", "actual_charge", "soc"} <= ev
    assert caps[0].source == "signal" and caps[0].rule == "CAP-SIGNAL-MATCH"


# ── No Guess Without Evidence ────────────────────────────────────────────────
def test_no_guess_facility_type_without_pattern():
    # A storage capability is recognized, but NO facility-recognition pack exists
    # yet (S4) — so the FUE must say Unknown, not invent "Battery Facility".
    prof = _bess_profile()
    assert prof.facility_type.value == "Unknown"
    assert prof.facility_type.rule == "FACILITY-NOGUESS"
    assert prof.facility_type.evidence                     # still traceable (why unknown)


def test_no_guess_when_no_signals_match():
    prof = understand({"price": "p"}, {}, [], intent="arbitrage")
    assert prof.equipment[0].capabilities == []            # nothing invented
    assert prof.equipment[0].identity.value == "Unknown"
    assert prof.facility_type.value == "Unknown"
    assert prof.is_fully_traceable()                       # honest ignorance is still traceable


# ── Rule 4: Explainability is a test ─────────────────────────────────────────
def test_profile_is_fully_traceable_and_explains():
    prof = _bess_profile()
    assert prof.is_fully_traceable()
    text = prof.explain()
    assert "energy_storage" in text and "Unknown" in text and "← signal" in text


def test_explainability_gate_catches_unevidenced_guess():
    # A signal inference with source 'signal' but NO evidence is a guess → the gate fails.
    bad = FacilityProfile(
        facility_type=Inference("X", 0.5, "ontology", evidence=[Evidence("c")]),
        equipment=[ProfiledEquipment(
            identity=Inference("e", 1.0, "ontology", evidence=[Evidence("x")]),
            capabilities=[], specs={},
            signal_map={"price": Inference("col", 1.0, "signal", evidence=[])})],  # ← no evidence
        intent=Inference("arbitrage", 1.0, "default"),
    )
    assert bad.is_fully_traceable() is False


# ── Rule 1: FacilityProfile is the ONLY output (no audit/decision here) ──────
def test_profile_carries_no_audit_or_decision():
    prof = _bess_profile()
    for forbidden in ("audit", "recommend", "recommendation", "decide", "decision",
                      "optimize", "optimise"):
        assert not hasattr(prof, forbidden)


# ── Rule 3: the graph stores knowledge, not conclusions ─────────────────────
def test_graph_stores_knowledge_not_conclusions():
    g = build_graph()
    assert g.archetype_of("energy_storage") == "storage"
    field_names = {f.name for f in fields(g)}
    assert field_names == {"capabilities", "equipment", "intents", "facility_patterns"}
    blob = " ".join(field_names) + " " + " ".join(d for d in dir(g) if not d.startswith("_"))
    for forbidden in ("strateg", "recommend", "decision", "audit", "optimi"):
        assert forbidden not in blob.lower()


# ── S3 → S2 → engine: resolve() composes to the identical engine input ──────
def test_resolve_composes_to_engine_identity():
    asset, ts = _bess_asset(), _ts()
    wa = to_wire(compose(_bess_profile().resolve()))[0]
    assert wa.asset == asset and wa.time_series == ts and wa.dt_hours == 1.0
    assert run_optimizer(wa.asset, wa.time_series, dt_hours=1.0) == \
           run_optimizer(asset, ts, dt_hours=1.0)
