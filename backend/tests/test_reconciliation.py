"""Tracked tests for EDA-RECON-1.0 Live Reconciliation (certification bridge)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def _live(leak=200.0, rec=120.0, health=0.4, ccy="OMR", n=24, ehash="p" * 64):
    return {"provisional": True, "status": "PROVISIONAL", "currency": ccy,
            "live_leakage": leak, "live_recoverable": rec, "economic_health": health,
            "n_events": n, "evidence_sha256": ehash}


def _cert(total_gap=188.62, recoverable=132.24, ccy="OMR", sha="c" * 64):
    return {"currency": ccy, "total_gap_usd": total_gap,
            "recoverable_execution_gap": recoverable,
            "edv_actual_total": -48.21, "edv_optimal_total": 140.41,
            "data_quality_index": {"value": 0.987}, "audit_confidence": {"value": 0.987},
            "data_quality_manifest": {"span_hours": 24.0},
            "audit_manifest": {"input_sha256": sha,
                               "timestamp_range": {"first": "t0", "last": "t1"}}}


_VER = {"user_id": 3, "email": "am@x.om", "role": "asset_manager"}


def _build(live=None, cert=None):
    live = live or _live()
    cert = cert or _cert()
    ces = em.build_economic_state(cert)
    return em.build_reconciliation(live, cert, ces, live_state_id=5, certified_audit_id=9,
                                   stream_id="s1", verifier_identity=_VER, at_iso="2026-07-12T00:00:00Z")


def test_all_contract_fields_present():
    r = _build()
    for f in ("reconciliation_id", "live_state_id", "certified_audit_id", "provisional_hash",
              "certified_hash", "reconciliation_timestamp", "variance", "reconciliation_status",
              "verifier_identity", "evidence_hash"):
        assert f in r, f
    assert r["reconciliation_id"].startswith("EDRECON-") and r["version"] == "EDA-RECON-1.0"
    assert r["authority"] == "certified"


def test_variance_disclosed_primary_leakage():
    r = _build()                                   # live 200 vs certified 188.62
    v = r["variance"]["primary"]
    assert v["metric"] == "live_leakage" and v["basis"] == "economic_gap"
    assert abs(v["absolute"] - (200.0 - 188.62)) < 1e-6
    assert v["provisional_value"] == 200.0 and v["certified_value"] == 188.62


def test_variance_secondary_and_context():
    r = _build()
    assert r["variance"]["secondary"]["metric"] == "recoverable_value"
    assert r["variance"]["context"]["metric"] == "economic_health"
    assert r["variance"]["context"]["certified_value"] is not None   # from certified ES


def test_no_tolerance_no_passfail():
    # A large variance is still 'reconciled' (informational, not a gate).
    r = _build(live=_live(leak=999999.0))
    assert r["reconciliation_status"] == "reconciled"
    assert r["variance"]["primary"]["absolute"] > 0


def test_incompatible_on_currency_mismatch():
    r = _build(live=_live(ccy="USD"))
    assert r["reconciliation_status"] == "incompatible"
    assert r["variance"] is None and "currency mismatch" in r["variance_explanation"]


def test_incompatible_when_not_provisional():
    live = _live(); live["provisional"] = False
    r = _build(live=live)
    assert r["reconciliation_status"] == "incompatible" and r["variance"] is None


def test_certified_is_authority_and_hashes_recorded():
    r = _build()
    assert r["authority"] == "certified"
    assert r["provisional_hash"] == "p" * 64 and r["certified_hash"] == "c" * 64


def test_verifier_identity_immutable_in_record():
    r = _build()
    assert r["verifier_identity"] == _VER


def test_deterministic_and_id_depends_on_ids():
    r1 = _build()
    r2 = _build()
    assert r1 == r2
    ces = em.build_economic_state(_cert())
    r3 = em.build_reconciliation(_live(), _cert(), ces, live_state_id=6, certified_audit_id=9,
                                 stream_id="s1", verifier_identity=_VER, at_iso="2026-07-12T00:00:00Z")
    assert r1["reconciliation_id"] != r3["reconciliation_id"]


def test_no_adjustment_no_recompute():
    # The reconciliation exposes no function that alters either state.
    r = _build()
    assert "adjustment" not in r and "adjusted" not in r
    assert em.METRIC_REGISTRY["Reconciliation"]["version"] == "EDA-RECON-1.0"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-RECON-1.0 TESTS PASS")
