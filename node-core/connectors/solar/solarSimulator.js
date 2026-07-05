// Solar telemetry simulator — bell-curve irradiance day with occasional
// curtailment during the midday price dip.
let step = 0;

function nextTick() {
  step += 1;
  const hourOfDay = (step % 288) / 12; // 5-min cadence mapped onto 24h
  const irradianceShape = Math.max(0, Math.sin(((hourOfDay - 6) / 12) * Math.PI));
  const output = +(450 * irradianceShape * (0.9 + 0.1 * Math.random())).toFixed(2);
  const price = +(8 + 6 * Math.sin(((hourOfDay - 15) / 12) * Math.PI) + Math.random()).toFixed(2);
  const curtailed = price < 6 && output > 100 ? +(output * 0.1).toFixed(2) : 0;
  return {
    price,
    actualDischargeMw: +(output - curtailed).toFixed(2),
    curtailmentMw: curtailed,
    irradianceWm2: +(1000 * irradianceShape).toFixed(0),
  };
}

module.exports = { nextTick };
