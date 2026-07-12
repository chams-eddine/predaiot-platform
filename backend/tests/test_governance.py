"""Tracked tests for EDA-GOV-1.0 Governance Record (immutable verification artifact)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def _outcome(status="measured", aei=0.9, dqi=0.95, oid="EDOUT-ABC", did="EDDEC-XYZ", ehash="a" * 64):
    return {"outcome_id": oid, "decision_id": did, "outcome_status": status,
            "evidence_hash": ehash, "confidence": {"audit_confidence": aei, "dqi": dqi}}


_VERIFIER = {"user_id": 7, "email": "cfo@x.om", "role": "finance"}


def test_verdict_guardrail_cannot_confirm_insufficient():
    assert not em.governance_verdict_allowed("insufficient_evidence", "confirmed")
    assert em.governance_verdict_allowed("insufficient_evidence", "disputed")
    assert em.governance_verdict_allowed("insufficient_evidence", "inconclusive")


def test_verdict_measured_allows_any():
    for v in ("confirmed", "disputed", "inconclusive"):
        assert em.governance_verdict_allowed("measured", v)
    assert not em.governance_verdict_allowed("measured", "banana")


def test_record_has_all_contract_fields():
    r = em.build_governance_record(_outcome(), [3, 14], "confirmed", _VERIFIER, "2026-07-12T00:00:00Z")
    for f in ("governance_id", "methodology_version", "outcome_ids", "audit_ids",
              "verdict", "verification_confidence", "evidence_hash", "verifier", "timestamp"):
        assert f in r, f
    assert r["governance_id"].startswith("EDGOV-")
    assert r["version"] == "EDA-GOV-1.0" and r["methodology_version"] == "EDA-GOV-1.0"


def test_references_outcome_and_audits():
    r = em.build_governance_record(_outcome(oid="EDOUT-1"), [3, 14, None], "confirmed", _VERIFIER, "t")
    assert r["outcome_ids"] == ["EDOUT-1"]
    assert r["audit_ids"] == [3, 14]                # None dropped, sorted, deduped
    assert r["outcome_evidence_hash"] == "a" * 64   # links to the Outcome's own hash


def test_verification_confidence_is_carried_measured():
    r = em.build_governance_record(_outcome(aei=0.4649, dqi=1.0), [1, 2], "disputed", _VERIFIER, "t")
    vc = r["verification_confidence"]
    assert vc["audit_confidence"] == 0.4649 and vc["dqi"] == 1.0
    assert vc["grade"] == "D"                        # 0.4649 ≥ 0.40 and < 0.60 → D
    assert "carried" in vc["basis"]


def test_confidence_grade_bands():
    assert em.build_governance_record(_outcome(aei=0.95), [1], "confirmed", _VERIFIER, "t")["verification_confidence"]["grade"] == "A"
    assert em.build_governance_record(_outcome(aei=0.45), [1], "disputed", _VERIFIER, "t")["verification_confidence"]["grade"] == "D"


def test_deterministic_hash():
    a = em.build_governance_record(_outcome(), [3, 14], "confirmed", _VERIFIER, "2026-07-12T00:00:00Z")
    b = em.build_governance_record(_outcome(), [3, 14], "confirmed", _VERIFIER, "2026-07-12T00:00:00Z")
    assert a == b
    # different verdict → different id/hash
    c = em.build_governance_record(_outcome(), [3, 14], "disputed", _VERIFIER, "2026-07-12T00:00:00Z")
    assert a["governance_id"] != c["governance_id"]


def test_governance_is_not_a_status_or_terminal_flag():
    # The Governance module produces records; it exposes no state-mutation helper.
    assert not hasattr(em, "set_governance_status")
    m = em.METRIC_REGISTRY["Governance"]
    assert any("Not a status field" in r for r in m["validation_rules"])


def test_registry_self_describes_governance():
    assert em.METRIC_REGISTRY["Governance"]["version"] == "EDA-GOV-1.0"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-GOV-1.0 TESTS PASS")
