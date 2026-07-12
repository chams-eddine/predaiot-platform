# PREDAIOT Edge Collector — OPC-UA (read-only)

Item 1 of the Live Economic Pipeline. `EDA-EDGE-OPCUA-1.0`.

Runs on customer premises; reads OPC-UA tags read-only, buffers locally
(store-and-forward), and forwards signed batches to the PREDAIOT platform.
**It computes no economics** — all intelligence stays on the certified
server-side Layer 2 engine. The collector is a transport / update mechanism.

## Guarantees
- **Read-only on OT**: only `read_value()` is used; the agent never writes,
  sets, or calls control methods (enforced by a tracked test).
- **Store-and-forward**: a local SQLite ring buffer retains readings across
  network/platform outages; batches are re-sent until the server acks.
- **Signed**: each batch carries an `X-Edge-Signature` HMAC-SHA256 header.

## Run
```
pip install -r requirements.txt        # asyncua only needed for real hardware
cp config.example.json config.json     # set server_url, tags, ingest_url, hmac_key
python opcua_collector.py --config config.json
```
Set `"simulate": true` to run without OPC-UA hardware (synthetic tags) — useful
for validating buffering + forwarding end-to-end before wiring real tags.

## Verification status
- Pure logic + buffer + read-only guarantee: covered by `test_collector.py`.
- OT-hardware verification (a real OPC-UA server) is customer-premises and is
  not exercised in CI.
- The server ingest endpoint (`/api/v1/live/ingest`) is delivered with the
  next pipeline items (MQTT streaming / Window Builder).
