"""Tracked tests for EDA-OUT-1.0 Outcome (measured realized impact; facts only)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def _audit(root_causes, currency="OMR", sha="base", aei=0.9, dqi=0.95, span=24.0):
    return {
        "currency": currency, "root_causes": root_causes,
        "audit_confidence": {"value": aei, "grade": "B"},
        "data_quality_index": {"value": dqi},
        "data_quality_manifest": {"span_hours": span},
        "audit_manifest": {"input_sha256": sha,
                           "timestamp_range": {"first": "2024-07-01T00:00:00+00:00",
                                               "last": "2024-07-01T23:00:00+00:00"}},
    }


def _decision(value_at_stake=569.77, currency="OMR", rcid="missed-arbitrage"):
    return {"decision_id": "EDDEC-TEST", "root_cause_id": rcid,
            "expected_value_impact": {"value_at_stake": value_at_stake, "currency": currency},
            "evidence_reference": {"decision_evidence_sha256": "deadbeef"}}


BASELINE = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 569.77}],
                  sha="baseline_sha")


def test_measured_when_bucket_reobserved_lower():
    # verification audit: same bucket now only 200 -> realized reduction 369.77
    ver = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 200.0}],
                 sha="verify_sha", aei=0.88)
    o = em.build_outcome(_decision(), BASELINE, ver, verification_audit_id=99)
    assert o["outcome_status"] == "measured"
    assert abs(o["realized_value"] - (569.77 - 200.0)) < 1e-6
    assert o["confidence"]["audit_confidence"] == 0.88     # verification-audit confidence (measured)
    assert o["outcome_id"].startswith("EDOUT-")
    assert len(o["evidence_hash"]) == 64


def test_insufficient_when_bucket_not_reobserved():
    # verification audit lacks the bucket -> NOT measurable (no assumed elimination)
    ver = _audit([{"category": "Partial Capture", "contribution_pct": 100.0, "loss_usd": 10.0}],
                 sha="v2")
    o = em.build_outcome(_decision(), BASELINE, ver, verification_audit_id=99)
    assert o["outcome_status"] == "insufficient_evidence"
    assert o["realized_value"] is None
    assert o["root_cause_reobserved"] is False


def test_insufficient_on_currency_mismatch():
    ver = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 100.0}],
                 currency="USD", sha="v3")
    o = em.build_outcome(_decision(), BASELINE, ver, verification_audit_id=99)
    assert o["outcome_status"] == "insufficient_evidence"
    assert o["realized_value"] is None
    assert "currency mismatch" in o["measurement_note"]


def test_baseline_and_verification_windows_present():
    ver = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 300.0}],
                 sha="v4")
    o = em.build_outcome(_decision(), BASELINE, ver, verification_audit_id=42)
    assert o["baseline_reference"]["baseline_dataset_sha256"] == "baseline_sha"
    assert o["verification_window"]["verification_dataset_sha256"] == "v4"
    assert o["verification_window"]["verification_audit_id"] == 42
    assert o["baseline_reference"]["decision_evidence_sha256"] == "deadbeef"


def test_reproducible_and_id_depends_on_verification_audit():
    ver = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 300.0}], sha="v5")
    o1 = em.build_outcome(_decision(), BASELINE, ver, 42)
    o2 = em.build_outcome(_decision(), BASELINE, ver, 42)
    assert o1 == o2
    o3 = em.build_outcome(_decision(), BASELINE, ver, 43)
    assert o1["outcome_id"] != o3["outcome_id"]


def test_outcome_does_not_judge_success():
    # Facts only — no 'verified'/'success'/'pass' verdict field (that is Governance).
    ver = _audit([{"category": "Missed Arbitrage", "contribution_pct": 100.0, "loss_usd": 200.0}], sha="v6")
    o = em.build_outcome(_decision(), BASELINE, ver, 42)
    assert o["outcome_status"] in ("measured", "insufficient_evidence")
    assert "verified" not in o and "success" not in o and "verdict" not in o


def test_registry_self_describes_outcome():
    m = em.METRIC_REGISTRY["Outcome"]
    assert m["version"] == "EDA-OUT-1.0"
    assert any("Governance verifies" in r for r in m["validation_rules"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-OUT-1.0 TESTS PASS")
