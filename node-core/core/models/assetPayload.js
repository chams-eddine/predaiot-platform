// Unified Asset Model — every connector, regardless of asset physics,
// normalises its telemetry into this one shape before it enters the core.
// { assetId, assetType, timestamp, measurements, market, constraints }

/**
 * @param {object} p
 * @param {string} p.assetId       e.g. "bess-01"
 * @param {string} p.assetType     "BESS" | "Solar" | "Wind" | ...
 * @param {string} [p.timestamp]   ISO-8601; defaults to now
 * @param {object} p.measurements  { actualDischargeMw, actualChargeMw, soc, ... }
 * @param {object} p.market        { priceMwh, forecastPriceMwh, currency }
 * @param {object} p.constraints   { pMax, eMax, socInit, etaCh, etaDis, degCost }
 */
function makeAssetPayload(p) {
  if (!p || typeof p !== "object") throw new TypeError("payload must be an object");
  if (!p.assetId) throw new TypeError("assetId is required");
  if (!p.assetType) throw new TypeError("assetType is required");
  return {
    assetId: String(p.assetId),
    assetType: String(p.assetType),
    timestamp: p.timestamp || new Date().toISOString(),
    measurements: {
      actualDischargeMw: num(p.measurements?.actualDischargeMw, 0),
      actualChargeMw: num(p.measurements?.actualChargeMw, 0),
      soc: p.measurements?.soc ?? null,
      curtailmentMw: num(p.measurements?.curtailmentMw, 0),
      ...p.measurements,
    },
    market: {
      priceMwh: num(p.market?.priceMwh, 0),
      forecastPriceMwh: p.market?.forecastPriceMwh ?? null,
      currency: p.market?.currency || "USD",
    },
    constraints: {
      pMax: num(p.constraints?.pMax, 50),
      eMax: num(p.constraints?.eMax, 100),
      socInit: num(p.constraints?.socInit, 0.2),
      etaCh: num(p.constraints?.etaCh, 0.95),
      etaDis: num(p.constraints?.etaDis, 0.95),
      degCost: num(p.constraints?.degCost, 5.0),
    },
  };
}

function num(v, dflt) {
  const n = Number(v);
  return Number.isFinite(n) ? n : dflt;
}

module.exports = { makeAssetPayload };
