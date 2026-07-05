// BESS connector adapter: pulls one telemetry tick from its source (here the
// simulator; in production a Modbus/OPC-UA/MQTT bridge) and normalises it
// into the Unified Asset Model.
const { makeAssetPayload } = require("../../core/models/assetPayload");
const sim = require("./bessSimulator");

async function readTick(assetId) {
  const t = sim.nextTick();
  return makeAssetPayload({
    assetId,
    assetType: "BESS",
    measurements: {
      actualDischargeMw: t.actualDischargeMw,
      actualChargeMw: t.actualChargeMw,
      soc: t.soc,
      tempC: t.tempC,
    },
    market: { priceMwh: t.price, forecastPriceMwh: t.forecastPrice, currency: "USD" },
    constraints: { pMax: 50, eMax: 100, socInit: 0.5, etaCh: 0.95, etaDis: 0.95, degCost: 5.0 },
  });
}

module.exports = { readTick };
