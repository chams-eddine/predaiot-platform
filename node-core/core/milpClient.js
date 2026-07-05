// HTTP client for milp-service — the verbatim production optimizer.
// The Node core never re-implements the MILP; it always asks the Python
// service so both stacks share one mathematical brain.
const { MILP_SERVICE_URL } = require("../config/system");

/**
 * @param {object} asset   constraints (Unified Asset Model): pMax, eMax,
 *                         socInit, etaCh, etaDis, degCost
 * @param {number[]} prices
 * @param {number} dtHours
 * @returns {Promise<{optimalDischarge:number[], optimalCharge:number[], status:string}>}
 */
async function getOptimalDispatch(asset, prices, dtHours) {
  const body = {
    asset: {
      p_max: asset.pMax,
      e_max: asset.eMax,
      soc_init: asset.socInit,
      eta_ch: asset.etaCh,
      eta_dis: asset.etaDis,
      deg_cost: asset.degCost,
    },
    prices,
    dt_hours: dtHours,
  };
  const res = await fetch(`${MILP_SERVICE_URL}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`milp-service ${res.status}: ${detail.slice(0, 200)}`);
  }
  const data = await res.json();
  // Service returns {index: value} maps keyed 0..N-1 — flatten to arrays.
  const n = prices.length;
  const optimalDischarge = new Array(n).fill(0);
  const optimalCharge = new Array(n).fill(0);
  for (const [k, v] of Object.entries(data.optimal_discharge || {})) optimalDischarge[+k] = v;
  for (const [k, v] of Object.entries(data.optimal_charge || {})) optimalCharge[+k] = v;
  return { optimalDischarge, optimalCharge, status: data.status || "Unknown" };
}

async function milpHealth() {
  try {
    const res = await fetch(`${MILP_SERVICE_URL}/health`);
    return res.ok ? await res.json() : { ok: false, status: res.status };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}

module.exports = { getOptimalDispatch, milpHealth };
