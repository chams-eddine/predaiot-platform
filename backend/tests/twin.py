# -*- coding: utf-8 -*-
"""Self-contained digital-twin telemetry generator for the characterization
suite. Physics-plausible hybrid-site SCADA data + a fault-injection library,
used to drive the frozen audit engine and assert behaviour-preserving
invariants. No external files — safe to run in CI.
"""
from __future__ import annotations
import io
import math
import numpy as np
import pandas as pd


def _price(n, dt_h, rng, regime):
    hod = (np.arange(n) * dt_h) % 24.0
    base = 40 + 30 * np.exp(-((hod - 9) ** 2) / 6) + 45 * np.exp(-((hod - 19) ** 2) / 5)
    if regime == "flat":
        return np.round(np.full(n, 50.0) + rng.normal(0, 0.5, n), 2)
    if regime == "volatile":
        return np.round(base + rng.normal(0, 22, n), 2)
    if regime == "negative":
        return np.round(base - 70 * np.exp(-((hod - 13) ** 2) / 5), 2)
    return np.round(base + rng.normal(0, 3, n), 2)


def _bess_operator(prices, dt_h, rng, p_max=50.0, e_max=100.0):
    lo, hi = np.percentile(prices, 35), np.percentile(prices, 70)
    soc, dis, ch, socs = 0.3 * e_max, np.zeros(len(prices)), np.zeros(len(prices)), np.zeros(len(prices))
    for i, pr in enumerate(prices):
        if pr >= hi and soc > 0.1 * e_max:
            d = min(p_max, (soc - 0.1 * e_max) / dt_h); dis[i] = round(d, 3); soc -= d * dt_h
        elif pr <= lo and soc < 0.9 * e_max:
            cc = min(p_max, (0.9 * e_max - soc) / dt_h); ch[i] = round(cc, 3); soc += cc * dt_h * 0.95
        socs[i] = round(soc / e_max, 4)
    return dis, ch, socs


def base_frame(asset, hours, dt_min, seed, regime):
    rng = np.random.default_rng(seed)
    dt_h = dt_min / 60.0
    n = int(round(hours / dt_h))
    ts = [pd.Timestamp("2024-07-01 00:00:00") + pd.Timedelta(minutes=dt_min * i) for i in range(n)]
    price = _price(n, dt_h, rng, regime)
    df = pd.DataFrame({"timestamp": ts, "spot_price": price})
    if asset == "solar":
        hod = (np.arange(n) * dt_h) % 24.0
        df["solar_output"] = np.round(50 * np.clip(np.sin((hod - 6) / 12 * math.pi), 0, None)
                                      * (1 - 0.25 * rng.random(n)), 3)
        df["curtailment_mw"] = np.where(price < 0, df["solar_output"] * 0.5, 0.0)
        df["asset_type"] = ["Solar" if i == 0 else "" for i in range(n)]
    else:
        dis, ch, socs = _bess_operator(price, dt_h, rng)
        df["bess_discharge_mw"], df["bess_charge_mw"], df["soc"] = dis, ch, socs
        df["forecast_price"] = np.round(price + rng.normal(0, 6, n), 2)
        df["asset_type"] = ["Battery Storage" if i == 0 else "" for i in range(n)]
    return df


# ── fault injectors (transport-layer / value) ───────────────────────────────
def _col(df):
    for c in ("bess_discharge_mw", "solar_output"):
        if c in df.columns:
            return c
    return df.columns[-1]


def f_offset_timestamps(df, rng):     # the real-SCADA off-the-hour case
    df["timestamp"] = pd.to_datetime(df["timestamp"]) + pd.Timedelta(minutes=9)
    return df


def f_corrupted_packets(df, rng):
    c = _col(df); idx = rng.choice(len(df), max(1, len(df) // 12), replace=False)
    df[c] = df[c].astype(object)
    for i in idx:
        df.at[i, c] = rng.choice(["NaN", "", "#REF!", "null"])
    return df


def f_duplicate_events(df, rng):
    idx = rng.choice(len(df), max(1, len(df) // 6), replace=False)
    return pd.concat([df, df.iloc[idx]], ignore_index=True)


def f_out_of_order(df, rng):
    return df.sample(frac=1.0, random_state=int(rng.integers(0, 1 << 30))).reset_index(drop=True)


def f_negative_prices(df, rng):
    idx = rng.choice(len(df), max(1, len(df) // 6), replace=False)
    df.loc[idx, "spot_price"] = -rng.uniform(5, 60, len(idx))
    return df


def f_price_spike(df, rng):
    df.loc[rng.integers(0, len(df)), "spot_price"] = rng.uniform(500, 5000)
    return df


FAULTS = {
    "offset_timestamps": f_offset_timestamps, "corrupted_packets": f_corrupted_packets,
    "duplicate_events": f_duplicate_events, "out_of_order": f_out_of_order,
    "negative_prices": f_negative_prices, "price_spike": f_price_spike,
}
_STRUCTURAL = ("duplicate_events", "out_of_order", "corrupted_packets", "offset_timestamps")


def build(asset="bess", hours=24, dt_min=60, seed=0, regime="normal", faults=()):
    rng = np.random.default_rng(seed + 7919)
    df = base_frame(asset, hours, dt_min, seed, regime)
    ordered = ([f for f in faults if f not in _STRUCTURAL]
               + [f for f in faults if f in _STRUCTURAL])
    for f in ordered:
        df = FAULTS[f](df, rng)
    return df


def to_csv_bytes(df):
    buf = io.StringIO(); df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
