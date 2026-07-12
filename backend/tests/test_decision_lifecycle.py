"""Tracked tests for EDA-DEC-LIFE-1.0 Decision Lifecycle state machine (pure)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def test_valid_forward_path():
    assert em.lifecycle_can_transition("proposed", "accepted")
    assert em.lifecycle_can_transition("accepted", "in_execution")
    assert em.lifecycle_can_transition("in_execution", "executed")


def test_none_current_is_proposed():
    assert em.lifecycle_can_transition(None, "accepted")     # None ⇒ proposed
    assert not em.lifecycle_can_transition(None, "executed")  # can't skip states


def test_invalid_transitions_rejected():
    assert not em.lifecycle_can_transition("proposed", "executed")   # no skipping
    assert not em.lifecycle_can_transition("rejected", "accepted")   # rejected is terminal (→superseded only)
    assert not em.lifecycle_can_transition("executed", "in_execution")  # no re-open


def test_terminal_states():
    assert em.LIFECYCLE_TERMINAL == {"executed", "rejected", "superseded"}
    assert em.LIFECYCLE_TRANSITIONS["superseded"] == set()          # fully terminal
    assert em.lifecycle_can_transition("executed", "superseded")    # only exit from executed


def test_role_gate_viewer_denied_everywhere():
    for st in ("accepted", "rejected", "deferred", "in_execution", "executed", "superseded"):
        assert not em.lifecycle_role_allowed("viewer", st)


def test_role_gate_owner_allowed_everywhere():
    for st in ("accepted", "rejected", "deferred", "in_execution", "executed", "superseded"):
        assert em.lifecycle_role_allowed("owner", st)


def test_role_gate_operator_executes_but_not_accepts():
    assert em.lifecycle_role_allowed("operator", "in_execution")
    assert em.lifecycle_role_allowed("operator", "executed")
    assert not em.lifecycle_role_allowed("operator", "accepted")     # operators execute, don't approve
    assert not em.lifecycle_role_allowed("operator", "rejected")


def test_role_gate_asset_manager_approves():
    assert em.lifecycle_role_allowed("asset_manager", "accepted")
    assert em.lifecycle_role_allowed("asset_manager", "executed")


def test_finance_cannot_transition():
    for st in em.LIFECYCLE_STATES:
        if st == "proposed":
            continue
        assert not em.lifecycle_role_allowed("finance", st)


def test_lifecycle_does_not_compute_value():
    # The lifecycle module exposes NO realized-value function — that is Governance.
    assert not hasattr(em, "realized_value")
    assert not hasattr(em, "governance_verify")


def test_registry_self_describes_lifecycle():
    m = em.METRIC_REGISTRY["DecisionLifecycle"]
    assert m["version"] == "EDA-DEC-LIFE-1.0"
    assert any("never computes realized value" in r for r in m["validation_rules"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-DEC-LIFE-1.0 TESTS PASS")
