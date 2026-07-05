// Deterministic-ish BESS telemetry simulator. Mirrors the Vite app's demo
// profile: off-peak charge, peak discharge, sinusoidal daily price.
let step = 0;
let soc = 0.5;

function nextTick() {
  step += 1;
  const base = 30 + 70 * Math.sin((step - 72) * (Math.PI / 144));
  const price = Math.max(5, +(base + (Math.random() - 0.5) * 10).toFixed(2));
  let discharge = 0;
  let charge = 0;
  if (price < 20 && soc < 0.9) {
    charge = 40;
    soc = Math.min(0.95, soc + (charge * 0.95) / 100);
  } else if (price > 40 && soc > 0.2) {
    discharge = Math.min(40, (soc - 0.2) * 100);
    soc = Math.max(0.1, soc - discharge / 0.95 / 100);
  }
  return {
    price,
    forecastPrice: +(price * (0.9 + Math.random() * 0.2)).toFixed(2),
    actualDischargeMw: +discharge.toFixed(2),
    actualChargeMw: charge,
    soc: +soc.toFixed(4),
    tempC: +(24 + 6 * Math.random()).toFixed(1),
  };
}

module.exports = { nextTick };
