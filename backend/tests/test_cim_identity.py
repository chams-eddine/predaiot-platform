# -*- coding: utf-8 -*-
"""Phase 4 S2 gate — the graph CIM adapter must be IDENTITY for the BESS /
default-intent path. `to_wire(compose(profile))` must reproduce the exact
`AssetSpecs + time_series` the engine reads today, and the engine must return the
identical optimum. This is the structural guarantee behind Law 1 (Immutable
Engine): all industry intelligence lives above `to_wire()`; the engine input is
unchanged.
"""
from app.schemas import AssetSpecs
from app.domain.canonical import (
    compose, to_wire, FacilityProfile, DetectedEquipment, Facility, Process,
    Equipment, CapabilityRef, Intent,
)
from app.services.optimization_service import run_optimizer

_PRICES = [10.0, 20.0, 50.0, 15.0, 80.0, 5.0, 60.0, 30.0]


def _bess_asset() -> AssetSpecs:
    return AssetSpecs(asset_type="BESS", asset_name="T", p_max=50.0, e_max=100.0,
                      soc_init=0.2, eta_ch=0.95, eta_dis=0.95, deg_cost=5.0)


def _time_series():
    return [{"hour": i, "price": p, "actual_discharge": 0.0, "actual_charge": 0.0,
             "soc": None, "grid_demand": None, "curtailment_mw": 0.0,
             "operator_override": False, "forecast_price": None}
            for i, p in enumerate(_PRICES)]


def _bess_profile():
    asset, ts = _bess_asset(), _time_series()
    return FacilityProfile(
        equipment=[DetectedEquipment(id="battery", capabilities=["energy_storage"],
                                     specs=asset.model_dump(), time_series=ts)],
        intent="arbitrage", dt_hours=1.0,
    )


def test_compose_resolves_storage_archetype_and_default_intent():
    fac = compose(_bess_profile())
    eq = fac.processes[0].equipment[0]
    beh = eq.behavioral()
    assert beh is not None and beh.id == "energy_storage" and beh.archetype == "storage"
    # default intent is a genuine no-op → byte-identical path
    assert fac.intent.id == "arbitrage"
    assert fac.intent.constraints == [] and fac.intent.wire_params == {}


def test_to_wire_is_identity_for_bess():
    asset, ts = _bess_asset(), _time_series()
    wires = to_wire(compose(_bess_profile()))
    assert len(wires) == 1
    wa = wires[0]
    assert wa.asset == asset            # pydantic equality by field values
    assert wa.time_series == ts
    assert wa.dt_hours == 1.0


def test_engine_result_identical_through_cim():
    asset, ts = _bess_asset(), _time_series()
    wa = to_wire(compose(_bess_profile()))[0]
    assert run_optimizer(wa.asset, wa.time_series, dt_hours=1.0) == \
           run_optimizer(asset, ts, dt_hours=1.0)


def test_intent_reshapes_only_via_to_wire():
    # A non-default intent (wire_params) reshapes the emitted spec WITHOUT any
    # engine change — the mechanism that lets intents like "maintenance" cap p_max.
    fac = Facility(
        id="f",
        processes=[Process(id="p", equipment=[Equipment(
            id="battery",
            capabilities=[CapabilityRef(id="energy_storage", capability_class="behavioral", archetype="storage")],
            specs=_bess_asset().model_dump(), signals=_time_series())])],
        intent=Intent(id="maintenance", wire_params={"specs": {"p_max": 25.0}}),
    )
    wa = to_wire(fac)[0]
    assert wa.asset.p_max == 25.0        # intent shaped the wire, engine untouched
    assert wa.asset.e_max == 100.0       # unrelated fields unchanged
