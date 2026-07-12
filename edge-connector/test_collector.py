"""Tracked tests for the read-only OPC-UA edge collector (pure logic + buffer)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opcua_collector as oc  # noqa: E402


def test_map_reading_uses_tag_map_and_ignores_unmapped():
    tag_map = {"ns=2;s=Plant.Price": "spot_price", "ns=2;s=Plant.SOC": "soc_percent"}
    raw = {"ns=2;s=Plant.Price": 42.5, "ns=2;s=Plant.SOC": 55, "ns=2;s=Unmapped": 9}
    r = oc.map_reading(raw, tag_map)
    assert r["spot_price"] == 42.5 and r["soc_percent"] == 55
    assert "ns=2;s=Unmapped" not in r and 9 not in r.values()
    assert "timestamp" in r                       # always stamped


def test_frame_batch_shape():
    b = oc.frame_batch("stream-1", 7, [{"spot_price": 10}])
    assert b["stream_id"] == "stream-1" and b["asset_id"] == 7
    assert b["collector_version"] == oc.COLLECTOR_VERSION
    assert b["readings"] == [{"spot_price": 10}]


def test_sign_batch_deterministic_and_key_sensitive():
    p = oc.frame_batch("s", 1, [{"a": 1}])
    # 'sent_at' varies; sign a stable subset
    stable = {"stream_id": "s", "readings": [{"a": 1}]}
    s1 = oc.sign_batch(stable, "key1")
    s2 = oc.sign_batch(stable, "key1")
    s3 = oc.sign_batch(stable, "key2")
    assert s1 == s2 and s1 != s3 and len(s1) == 64


def test_ring_buffer_store_and_forward():
    path = tempfile.mktemp(suffix=".db")
    try:
        buf = oc.RingBuffer(path, max_rows=1000)
        for i in range(5):
            buf.append({"spot_price": i})
        assert buf.count() == 5
        pend = buf.pending()
        assert len(pend) == 5 and pend[0][1]["spot_price"] == 0
        buf.ack([rid for rid, _ in pend[:3]])
        assert buf.count() == 2                    # only acked rows removed (forward guarantee)
        buf.db.close()
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def test_ring_buffer_caps_oldest():
    path = tempfile.mktemp(suffix=".db")
    try:
        buf = oc.RingBuffer(path, max_rows=10)
        for i in range(25):
            buf.append({"v": i})
        assert buf.count() == 10                   # ring drops oldest beyond cap
        vals = [r["v"] for _, r in buf.pending(50)]
        assert min(vals) >= 15                      # newest retained
        buf.db.close()
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def test_simulate_maps_by_trailing_token():
    nodes = ["ns=2;s=Plant.Price", "ns=2;s=Plant.SOC"]
    v = oc.simulate_once(nodes, step=19)           # peak hour → non-zero price
    assert v["ns=2;s=Plant.Price"] > 0 and v["ns=2;s=Plant.SOC"] == 50


def test_readonly_no_write_symbols():
    # Guardrail: the collector must never write to OPC-UA. No write/set/call helpers.
    src = open(os.path.join(os.path.dirname(__file__), "opcua_collector.py")).read()
    assert ".write_value(" not in src and ".set_value(" not in src and ".call_method(" not in src


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print(f"ALL {len(fns)} EDGE COLLECTOR TESTS PASS")
