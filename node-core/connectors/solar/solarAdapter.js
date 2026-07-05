// Solar connector adapter → Unified Asset Model.
const { makeAssetPayload } = require("../../core/models/assetPayload");
const sim = require("./solarSimulator");

async function readTick(assetId) {
  const t = sim.nextTick();
  return makeAssetPayload({
    assetId,
    assetType: "Solar",
    measurements: {
      actualDischargeMw: t.actualDischargeMw,
      actualChargeMw: 0,
      curtailmentMw: t.curtailmentMw,
      irradianceWm2: t.irradianceWm2,
    },
    market: { priceMwh: t.price, currency: "USD" },
    constraints: { pMax: 500, eMax: 0, socInit: 0, etaCh: 1, etaDis: 1, degCost: 0 },
  });
}

module.exports = { readTick };
