// Active-asset registry. One line per asset — add a connector module and a
// row here and the realtime engine picks it up on the next boot.
const bessAdapter = require("../../connectors/bess/bessAdapter");
const solarAdapter = require("../../connectors/solar/solarAdapter");

const ASSETS = [
  { assetId: "bess-01",  assetType: "BESS",  adapter: bessAdapter },
  { assetId: "solar-01", assetType: "Solar", adapter: solarAdapter },
];

function activeAssets() {
  return ASSETS;
}

function getAsset(assetId) {
  return ASSETS.find((a) => a.assetId === assetId) || null;
}

module.exports = { activeAssets, getAsset };
