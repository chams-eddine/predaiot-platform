// Multi-asset realtime state. A Map<assetId, latestTick> — never a single
// global tick, so N assets stream concurrently without clobbering each other.
const latestByAsset = new Map();
const statsByAsset = new Map(); // cumulative session economics per asset

function setTick(assetId, tick) {
  latestByAsset.set(assetId, tick);
}

function getTick(assetId) {
  return latestByAsset.get(assetId) || null;
}

function allTicks() {
  return Object.fromEntries(latestByAsset.entries());
}

function bumpStats(assetId, { edvOptStep, edvActStep }) {
  const s = statsByAsset.get(assetId) || { steps: 0, cumulativeOpt: 0, cumulativeAct: 0 };
  s.steps += 1;
  s.cumulativeOpt += Math.max(0, edvOptStep);
  s.cumulativeAct += edvActStep;
  statsByAsset.set(assetId, s);
  return s;
}

function getStats(assetId) {
  return statsByAsset.get(assetId) || { steps: 0, cumulativeOpt: 0, cumulativeAct: 0 };
}

module.exports = { setTick, getTick, allTicks, bumpStats, getStats };
