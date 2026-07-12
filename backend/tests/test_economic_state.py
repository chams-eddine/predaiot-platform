"""Tracked tests for EDA-ES-1.0 Economic State (canonical business object).

Runnable with `python -m pytest backend/tests/` or standalone
`python backend/tests/test_economic_state.py`. Unlike the gitignored smoke_*
scripts, this file is version-controlled — the first tracked test, so CI can
run it. Pure-module tests need no network or DB.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eda_metrics as em  # noqa: E402


def _audit(captured, optimal, ceiling_gap, recoverable, span_hours=24.0,
           currency="OMR", dqi=0.98, aei=0.98, sha="abc123"):
    return {
        "edv_actual_total": captured, "edv_optimal_total": optimal,
        "total_gap_usd": ceiling_gap, "recoverable_execution_gap": recoverable,
        "currency": currency,
        "data_quality_index": {"value": dqi}, "audit_confidence": {"value": aei},
        "data_quality_manifest": {"span_hours": span_hours},
        "audit_manifest": {"input_sha256": sha,
                           "timestamp_range": {"first": "2024-07-01T00:00:00+00:00",
                                               "last": "2024-07-01T23:00:00+00:00"}},
    }


def test_version_and_evidence_anchor():
    es = em.build_economic_state(_audit(900, 1000, 100, 56, sha="deadbeef"))
    assert es["version"] == "EDA-ES-1.0"
    assert es["evidence_sha256"] == "deadbeef"
    assert es["currency"] == "OMR"


def test_health_healthy_asset():
    # captured 900, recoverable 56 -> achievable 956 -> health 0.941
    es = em.build_economic_state(_audit(900, 1000, 100, 56))
    assert abs(es["economic_health"] - 900 / 956) < 1e-6
    assert es["economic_health_grade"] == "A"


def test_health_destructive_dispatch_clamps_to_zero():
    # Ibri2-like: captured -48.21, recoverable 132.24 -> raw negative -> clamp 0
    es = em.build_economic_state(_audit(-48.21, 140.41, 188.62, 132.24, span_hours=23.9167))
    assert es["economic_health"] == 0.0
    assert es["economic_health_raw"] < 0
    assert es["economic_health_grade"] == "E"


def test_leakage_rate_units():
    # ceiling_gap 120 over 24h -> 5.0 currency/h
    es = em.build_economic_state(_audit(880, 1000, 120, 60, span_hours=24.0))
    assert abs(es["leakage_rate"] - 5.0) < 1e-9


def test_na_when_recoverable_missing():
    a = _audit(900, 1000, 100, None)
    a["gap_attribution"] = {}  # no execution_gap anywhere
    es = em.build_economic_state(a)
    assert es["recoverable_value"] is None
    assert es["economic_health"] is None            # unknown stays unknown
    assert es["economic_health_grade"] == "N/A"


def test_na_when_span_missing():
    a = _audit(900, 1000, 100, 60)
    a["data_quality_manifest"] = {}                  # no span_hours
    es = em.build_economic_state(a)
    assert es["leakage_rate"] is None


def test_reproducible():
    a = _audit(900, 1000, 100, 56)
    assert em.build_economic_state(a) == em.build_economic_state(a)


def test_no_invented_fields_are_derived_from_inputs():
    es = em.build_economic_state(_audit(900, 1000, 100, 56))
    assert es["captured_value"] == 900
    assert es["economic_potential"] == 1000
    assert es["recoverable_value"] == 56


def test_registry_self_describes_economic_state():
    assert "EconomicState" in em.METRIC_REGISTRY
    assert em.METRIC_REGISTRY["EconomicState"]["version"] == "EDA-ES-1.0"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDA-ES-1.0 TESTS PASS")
