"""Tracked tests for the Canonical Economic Event (EDA-EVENT-1.0)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import canonical_event as ce  # noqa: E402


def test_normalize_produces_canonical_shape():
    e = ce.normalize_event({"timestamp": "2024-07-01T00:00:00Z", "spot_price": 42.5,
                            "actual_discharge": 30}, "s1", "opcua", "OMR")
    for f in ("event_id", "stream_id", "source", "timestamp", "spot_price",
              "actual_charge", "actual_discharge", "currency", "version"):
        assert f in e
    assert e["source"] == "opcua" and e["currency"] == "OMR" and e["actual_charge"] == 0.0


def test_event_id_dedup_deterministic():
    raw = {"timestamp": "t1", "spot_price": 10, "actual_charge": 1, "actual_discharge": 0}
    a = ce.normalize_event(raw, "s", "mqtt")
    b = ce.normalize_event(raw, "s", "mqtt")
    assert a["event_id"] == b["event_id"]           # same reading → same id (dedup)


def test_source_normalized_and_unknown_falls_back():
    assert ce.normalize_event({"timestamp": "t"}, "s", "modbus")["source"] == "modbus"
    assert ce.normalize_event({"timestamp": "t"}, "s", "weirdproto")["source"] == "rest"


def test_no_opcua_specific_dependency():
    # The same processing works regardless of source — no connector-specific field.
    a = ce.normalize_event({"timestamp": "t", "spot_price": 5}, "s", "opcua")
    b = ce.normalize_event({"timestamp": "t", "spot_price": 5}, "s", "csv")
    assert ce.to_time_step(a, 0) == ce.to_time_step(b, 0)   # identical bridge to L2


def test_validity_gate():
    assert ce.event_is_valid(ce.normalize_event({"timestamp": "t", "spot_price": 1}, "s", "rest"))
    assert not ce.event_is_valid(ce.normalize_event({"timestamp": "t"}, "s", "rest"))   # no price
    assert not ce.event_is_valid(ce.normalize_event({"spot_price": 1}, "s", "rest"))    # no ts


def test_window_dedups_orders_and_caps():
    evs = [ce.normalize_event({"timestamp": f"2024-07-01T{h:02d}:00:00Z", "spot_price": h}, "s", "rest")
           for h in range(10)]
    evs += [evs[0]]                                  # duplicate
    w = ce.build_window(evs, max_len=5)
    assert len(w) == 5                               # capped
    ts = [e["timestamp"] for e in w]
    assert ts == sorted(ts)                          # ordered (late-event safe)


def test_window_manifest_evidence_hash_stable():
    evs = [ce.normalize_event({"timestamp": "t1", "spot_price": 10}, "s", "rest"),
           ce.normalize_event({"timestamp": "t2", "spot_price": 20}, "s", "rest")]
    m1 = ce.window_manifest(ce.build_window(evs))
    m2 = ce.window_manifest(ce.build_window(evs))
    assert m1["evidence_sha256"] == m2["evidence_sha256"] and len(m1["evidence_sha256"]) == 64
    assert m1["n_events"] == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} CANONICAL EVENT TESTS PASS")
