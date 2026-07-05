// Multi-Asset Realtime Engine.
//
// Every tick: iterate the registry, read each connector, evaluate the step's
// economics, store + broadcast. EACH asset is wrapped in its own try/catch —
// one failing connector (sensor offline, adapter bug) must never stall the
// other assets' streams.
const { activeAssets } = require("../core/models/assetRegistry");
const { calculateStepEDV, calculateDQ } = require("../core/economicEngine");
const state = require("./state");
const { broadcast } = require("./broadcaster");
const { DEFAULT_DT_HOURS } = require("../config/system");

/**
 * Advisory step evaluation for one Unified Asset Model payload. A greedy
 * per-step upper bound stands in for the optimal at live cadence (the full
 * MILP runs in batch audits, not per-tick): discharge at p_max when the
 * margin (price − degCost) is positive, else idle.
 */
function evaluateStep(payload) {
  const { priceMwh } = payload.market;
  const { pMax, degCost } = payload.constraints;
  const actDis = payload.measurements.actualDischargeMw;
  const actCh = payload.measurements.actualChargeMw;

  const optDis = priceMwh - degCost > 0 ? pMax : 0;
  const optCh = 0;

  const { edvOptStep, edvActStep, gapStep } = calculateStepEDV({
    price: priceMwh, degCost, optDis, optCh, actDis, actCh, dtHours: DEFAULT_DT_HOURS,
  });

  const stats = state.bumpStats(payload.assetId, { edvOptStep, edvActStep });
  const { dqScore } = calculateDQ(stats.cumulativeOpt, stats.cumulativeAct);

  return {
    ...payload,
    economics: {
      optimalActionMw: optDis,
      edvOptimalStep: r2(edvOptStep),
      edvActualStep: r2(edvActStep),
      gapStep: r2(gapStep),
      cumulativeGap: r2(stats.cumulativeOpt - stats.cumulativeAct),
      dqScoreLive: r2(dqScore * 100),
      step: stats.steps,
    },
  };
}

async function tickAllAssets() {
  const results = [];
  for (const { assetId, adapter } of activeAssets()) {
    try {
      const payload = await adapter.readTick(assetId);
      const evaluated = evaluateStep(payload);
      state.setTick(assetId, evaluated);
      broadcast({ type: "tick", asset: evaluated });
      results.push({ assetId, ok: true });
    } catch (err) {
      // Isolated failure: record it, keep the loop going for other assets.
      results.push({ assetId, ok: false, error: String(err.message || err) });
      broadcast({ type: "asset_error", assetId, error: String(err.message || err) });
    }
  }
  return results;
}

const r2 = (v) => Math.round(v * 100) / 100;

module.exports = { tickAllAssets, evaluateStep };
