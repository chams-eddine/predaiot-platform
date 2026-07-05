// System status controller.
const { activeAssets } = require("../core/models/assetRegistry");
const { clientCount } = require("../realtime/broadcaster");
const { uptimeSeconds } = require("../realtime/scheduler");
const { milpHealth } = require("../core/milpClient");

// GET /api/v1/system/status
async function systemStatus(req, res) {
  const milp = await milpHealth();
  res.json({
    ok: true,
    uptimeSeconds: uptimeSeconds(),
    activeAssets: activeAssets().map(({ assetId, assetType }) => ({ assetId, assetType })),
    clients: clientCount(),
    milpService: milp,
  });
}

module.exports = { systemStatus };
