// Live + audit controllers.
const { tickAllAssets } = require("../realtime/realtimeEngine");
const state = require("../realtime/state");
const { runStorageAudit } = require("../core/storageAuditPipeline");

// POST /api/v1/live/step — force one tick across ALL active assets and
// return each asset's evaluated payload (REST alternative to the WS stream).
async function liveStep(req, res) {
  try {
    const results = await tickAllAssets();
    res.json({ results, assets: state.allTicks() });
  } catch (err) {
    res.status(500).json({ error: String(err.message || err) });
  }
}

// POST /api/v1/audit/storage — full batch audit through milp-service.
// Body: { asset: {pMax, eMax, socInit, etaCh, etaDis, degCost},
//         timeSeries: [{price, actualDischarge, actualCharge}], dtHours }
async function storageAudit(req, res) {
  try {
    const { asset = {}, timeSeries, dtHours = 1.0 } = req.body || {};
    if (!Array.isArray(timeSeries) || timeSeries.length === 0) {
      return res.status(400).json({ error: "timeSeries must be a non-empty array" });
    }
    const audit = await runStorageAudit(asset, timeSeries, dtHours);
    res.json(audit);
  } catch (err) {
    res.status(502).json({ error: String(err.message || err) });
  }
}

module.exports = { liveStep, storageAudit };
