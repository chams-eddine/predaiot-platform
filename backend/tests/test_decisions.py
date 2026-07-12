"""Tracked tests for EDA-DEC-1.0 Decision Intelligence (economic commitments).

Pure-module tests (no network/DB). Run: python backend/tests/test_decisions.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def _audit(root_causes, captured=-48.21, recoverable=132.24, currency="OMR",
           dqi=0.987, aei=0.987, span=24.0, sha="abc123"):
    return {
        "edv_actual_total": captured, "edv_optimal_total": captured + recoverable,
        "total_gap_usd": sum(r["loss_usd"] for r in root_causes),
        "recoverable_execution_gap": recoverable, "currency": currency,
        "root_causes": root_causes,
        "data_quality_index": {"value": dqi, "grade": "A"},
        "audit_confidence": {"value": aei, "grade": "A"},
        "data_quality_manifest": {"span_hours": span},
        "audit_manifest": {"input_sha256": sha,
                           "timestamp_range": {"first": "2024-07-01T00:00:00+00:00",
                                               "last": "2024-07-01T23:00:00+00:00"}},
    }


IBRI2_RC = [
    {"category": "Missed Arbitrage", "contribution_pct": 80.3, "loss_usd": 569.77},
    {"category": "Schedule-based Dispatch", "contribution_pct": 11.5, "loss_usd": 81.78},
    {"category": "Partial Capture", "contribution_pct": 8.2, "loss_usd": 58.12},
]


def _decs(rc=None, **kw):
    a = _audit(rc if rc is not None else IBRI2_RC, **kw)
    es = em.build_economic_state(a)
    return a, es, em.build_decisions(a, es, audit_id=1)


def test_one_decision_per_positive_bucket():
    _, _, d = _decs()
    assert len(d) == 3


def test_no_decision_without_quantified_impact():
    rc = [{"category": "Correct Dispatch", "contribution_pct": 100.0, "loss_usd": 0.0},
          {"category": "Missed Arbitrage", "contribution_pct": 0.0, "loss_usd": -5.0}]
    _, _, d = _decs(rc)
    assert d == []                       # LAW: no impact -> no decision


def test_value_at_stake_is_recorded_loss_no_annualization():
    _, _, d = _decs()
    top = d[0]
    assert top["expected_value_impact"]["value_at_stake"] == 569.77
    assert top["expected_value_impact"]["annualized"] is None      # LAW: no annualization
    assert "forward" not in top["expected_value_impact"]["basis"].lower()


def test_confidence_is_measured_not_predicted():
    _, _, d = _decs()
    c = d[0]["confidence"]
    assert c["audit_confidence"] == 0.987 and c["dqi"] == 0.987
    assert c["basis"].startswith("measured")


def test_decision_type_enum():
    _, _, d = _decs()
    types = {x["decision_type"] for x in d}
    assert types <= {"CORRECTIVE", "OPTIMIZATION", "RECOVERY", "MONITORING"}
    by_rc = {x["root_cause_id"]: x["decision_type"] for x in d}
    assert by_rc["missed-arbitrage"] == "OPTIMIZATION"
    assert by_rc["schedule-based-dispatch"] == "CORRECTIVE"


def test_decision_deadline_retrospective_null():
    _, _, d = _decs()
    for x in d:
        assert x["decision_mode"] == "retrospective"
        assert x["decision_deadline"]["timestamp"] is None


def test_governance_owner_object_default():
    _, _, d = _decs()
    assert d[0]["governance_owner"] == {"role": "asset_manager", "assigned_user_id": None}


def test_decision_id_prefix_and_depends_on_audit_id():
    a, es, d1 = _decs()
    assert d1[0]["decision_id"].startswith("EDDEC-")
    d2 = em.build_decisions(a, es, audit_id=2)          # amendment 4: id includes audit_id
    assert d1[0]["decision_id"] != d2[0]["decision_id"]


def test_reproducible():
    a, es, d1 = _decs()
    assert em.build_decisions(a, es, 1) == d1


def test_evidence_chain_anchor_present():
    _, _, d = _decs()
    ref = d[0]["evidence_reference"]
    assert ref["dataset_sha256"] == "abc123"
    assert len(ref["decision_evidence_sha256"]) == 64        # sha256 hex
    assert "gross attributed loss" in ref["ledger_derivation"]


def test_alternative_is_status_quo_with_consequence():
    _, _, d = _decs()
    alt = d[0]["alternative_action"]
    assert alt["action_code"] == "STATUS_QUO"
    assert alt["economic_consequence"] == 569.77


def test_registry_self_describes_decisions():
    m = em.METRIC_REGISTRY["DecisionIntelligence"]
    assert m["version"] == "EDA-DEC-1.0"
    assert m["action_library_version"] == "EDA-DEC-ACTIONS-1.0"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-DEC-1.0 TESTS PASS")
