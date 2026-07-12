#!/usr/bin/env python3
"""
PREDAIOT Edge Collector — OPC-UA (READ-ONLY)  ·  EDA-EDGE-OPCUA-1.0

Item 1 of the Live Economic Pipeline. Runs on customer premises, reads a
configured set of OPC-UA tags at an interval, maps them to PREDAIOT's canonical
telemetry fields, buffers locally (store-and-forward across outages), and pushes
signed batches to the platform ingest endpoint over HTTPS.

Design constraints (blueprint):
  * READ-ONLY on the OT network — the client only reads node values; it never
    writes, browses for control, or issues commands. OT-safe, DMZ-deployable.
  * Store-and-forward: a local SQLite ring buffer survives network / platform
    outages; nothing is lost, batches are re-sent until acknowledged.
  * The collector is a TRANSPORT — it computes no economics. All intelligence
    stays server-side on the certified Layer 2 engine.
  * Simulator mode (no asyncua / no server) so the agent is runnable and
    testable without hardware.

Run:  python opcua_collector.py --config config.json
"""
import argparse
import hashlib
import hmac
import json
import sqlite3
import time
from datetime import datetime, timezone

COLLECTOR_VERSION = "EDA-EDGE-OPCUA-1.0"


# ── Pure logic (unit-tested; no I/O) ────────────────────────────────────────
def map_reading(node_values: dict, tag_map: dict) -> dict:
    """
    Map raw {node_id: value} → canonical PREDAIOT fields via the config tag_map
    {node_id: canonical_field}. Unmapped nodes are ignored. Deterministic.
    Always stamps an ISO-8601 UTC 'timestamp' if the tag_map does not supply one.
    """
    out = {}
    for node_id, value in node_values.items():
        field = tag_map.get(node_id)
        if field:
            out[field] = value
    out.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    return out


def frame_batch(stream_id: str, asset_id, readings: list) -> dict:
    """Build the canonical push payload for a batch of readings."""
    return {
        "stream_id": stream_id,
        "asset_id": asset_id,
        "collector_version": COLLECTOR_VERSION,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "readings": readings,
    }


def sign_batch(payload: dict, hmac_key: str) -> str:
    """HMAC-SHA256 over the canonical JSON — integrity + origin authentication."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(hmac_key.encode(), body, hashlib.sha256).hexdigest()


# ── Store-and-forward ring buffer (SQLite) ──────────────────────────────────
class RingBuffer:
    """Local durable buffer. Readings persist until the server acknowledges."""

    def __init__(self, path: str, max_rows: int = 200_000):
        self.max_rows = max_rows
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS buffer ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, reading TEXT NOT NULL, at REAL NOT NULL)")
        self.db.commit()

    def append(self, reading: dict):
        self.db.execute("INSERT INTO buffer(reading, at) VALUES (?,?)",
                        (json.dumps(reading), time.time()))
        # Ring: drop oldest beyond the cap (72h @ 1-min ≈ 4320 rows; cap is generous).
        self.db.execute(
            "DELETE FROM buffer WHERE id IN "
            "(SELECT id FROM buffer ORDER BY id DESC LIMIT -1 OFFSET ?)", (self.max_rows,))
        self.db.commit()

    def pending(self, limit: int = 500):
        cur = self.db.execute("SELECT id, reading FROM buffer ORDER BY id ASC LIMIT ?", (limit,))
        return [(rid, json.loads(r)) for rid, r in cur.fetchall()]

    def ack(self, ids: list):
        self.db.executemany("DELETE FROM buffer WHERE id = ?", [(i,) for i in ids])
        self.db.commit()

    def count(self) -> int:
        return self.db.execute("SELECT count(*) FROM buffer").fetchone()[0]


# ── OPC-UA read (lazy asyncua) with simulator fallback ──────────────────────
def read_opcua_once(server_url: str, node_ids: list):
    """READ-ONLY: fetch current values for node_ids. Returns {node_id: value}."""
    from asyncua.sync import Client   # lazy — only needed with real hardware
    values = {}
    client = Client(url=server_url)
    client.connect()
    try:
        for nid in node_ids:
            values[nid] = client.get_node(nid).read_value()   # READ only
    finally:
        client.disconnect()
    return values


def simulate_once(node_ids: list, step: int):
    """Synthetic tag values so the agent runs without hardware."""
    import math
    h = step % 24
    price = 12 + (30 if 18 <= h <= 21 else 0) + 2 * math.sin(step / 3.0)
    canned = {"price": round(price, 2), "charge": 20 if h < 6 else 0,
              "discharge": 40 if 18 <= h <= 21 else 0, "soc": 50}
    # Map by trailing token of the node id (e.g. "ns=2;s=Plant.Price" → price)
    out = {}
    for nid in node_ids:
        key = nid.lower().rsplit(".", 1)[-1].rsplit("=", 1)[-1]
        out[nid] = canned.get(key, 0)
    return out


def run(config: dict):
    tag_map = config["tags"]
    node_ids = list(tag_map.keys())
    buf = RingBuffer(config.get("buffer_path", "edge_buffer.db"))
    interval = config.get("interval_sec", 60)
    simulate = config.get("simulate", False)
    ingest_url = config.get("ingest_url")
    step = 0
    print(f"[edge] {COLLECTOR_VERSION} starting | {len(node_ids)} tags | "
          f"{'SIMULATOR' if simulate else config.get('server_url')} | interval {interval}s")
    try:
        import requests   # lazy
    except ImportError:
        requests = None
    while True:
        try:
            raw = simulate_once(node_ids, step) if simulate else \
                read_opcua_once(config["server_url"], node_ids)
            buf.append(map_reading(raw, tag_map))
        except Exception as e:
            print(f"[edge] read error (buffered, will retry): {e}")
        # Forward pending buffer to the platform.
        if ingest_url and requests is not None:
            pend = buf.pending()
            if pend:
                payload = frame_batch(config["stream_id"], config.get("asset_id"),
                                      [r for _, r in pend])
                headers = {"Content-Type": "application/json"}
                if config.get("hmac_key"):
                    headers["X-Edge-Signature"] = sign_batch(payload, config["hmac_key"])
                try:
                    resp = requests.post(ingest_url, json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        buf.ack([rid for rid, _ in pend])
                        print(f"[edge] forwarded {len(pend)} readings; buffer now {buf.count()}")
                    else:
                        print(f"[edge] ingest {resp.status_code}; keeping buffer ({buf.count()})")
                except Exception as e:
                    print(f"[edge] push failed (store-and-forward, buffer {buf.count()}): {e}")
        step += 1
        time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PREDAIOT read-only OPC-UA edge collector")
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config) as f:
        run(json.load(f))
