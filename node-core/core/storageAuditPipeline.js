// One-call storage audit: MILP (verbatim production optimizer via HTTP)
// followed by the EDV/DQ/Gap ledger. This is the Node equivalent of
// backend/main.py's run_optimizer_full + process_calculation (storage mode).
const { getOptimalDispatch } = require("./milpClient");
const { calculateStorageAudit } = require("./economicEngine");

/**
 * @param {object} asset       Unified Asset Model constraints
 *                             { pMax, eMax, socInit, etaCh, etaDis, degCost }
 * @param {Array}  timeSeries  [{ price, actualDischarge, actualCharge }, ...]
 * @param {number} dtHours     step duration in hours (1/12 = 5-minute data)
 */
async function runStorageAudit(asset, timeSeries, dtHours) {
  const prices = timeSeries.map((ts) => Number(ts.price || 0));
  const { optimalDischarge, optimalCharge, status } =
    await getOptimalDispatch(asset, prices, dtHours);
  const audit = calculateStorageAudit(asset, timeSeries, optimalDischarge, optimalCharge, dtHours);
  return { ...audit, milpStatus: status };
}

module.exports = { runStorageAudit };
