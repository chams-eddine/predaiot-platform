// Tick scheduler — drives the realtime engine at a fixed cadence.
const { TICK_INTERVAL_MS } = require("../config/system");
const { tickAllAssets } = require("./realtimeEngine");

let timer = null;
let started = null;

function start() {
  if (timer) return;
  started = Date.now();
  timer = setInterval(() => {
    tickAllAssets().catch(() => { /* engine already isolates per-asset errors */ });
  }, TICK_INTERVAL_MS);
}

function stop() {
  if (timer) clearInterval(timer);
  timer = null;
}

function uptimeSeconds() {
  return started ? Math.floor((Date.now() - started) / 1000) : 0;
}

module.exports = { start, stop, uptimeSeconds };
