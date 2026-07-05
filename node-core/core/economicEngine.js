// Economic engine — EDV / DQ / Gap.
//
// MATH SOURCE OF TRUTH: backend/main.py `process_calculation` (storage mode)
// and its DQ block, at commit fb5e692. Each formula below is a line-for-line
// transcription — do NOT "improve" it here; change backend/main.py first and
// re-transcribe.
//
// Python (storage branch):
//   edv_opt_step = ((price - asset.deg_cost) * opt_dis - price * opt_ch) * dt_hours
//   edv_act_step = ((price - asset.deg_cost) * act_dis - price * act_ch) * dt_hours
//   gap_step     = edv_opt_step - edv_act_step
//
// Python (DQ block, Ref. Manual Ch 4.2):
//   _EDV_EPS = 1e-9
//   if total_edv_opt > _EDV_EPS:           dq = total_edv_act / total_edv_opt
//   elif abs(total_edv_act) <= _EDV_EPS:   dq = 1.0
//   else:                                  dq = 0.0
//   dq_raw kept; dq clamped into [0, 1]

const EDV_EPS = 1e-9;

/**
 * Per-step EDV for a storage asset (Reference Manual Vol II Ch 3 —
 * charging is paid for at the market price).
 */
function calculateStepEDV({ price, degCost, optDis, optCh, actDis, actCh, dtHours }) {
  const edvOptStep = ((price - degCost) * optDis - price * optCh) * dtHours;
  const edvActStep = ((price - degCost) * actDis - price * actCh) * dtHours;
  return {
    edvOptStep,
    edvActStep,
    gapStep: edvOptStep - edvActStep,
  };
}

/**
 * DQ with the Ch 4.2 domain restrictions. Returns both the clamped score
 * (what certificates display) and the raw ratio (negative = destructive
 * dispatch, > 1 = model/data disagreement).
 */
function calculateDQ(totalEdvOpt, totalEdvAct) {
  let dq;
  if (totalEdvOpt > EDV_EPS) {
    dq = totalEdvAct / totalEdvOpt;
  } else if (Math.abs(totalEdvAct) <= EDV_EPS) {
    dq = 1.0; // no opportunity existed and none was missed — full score
  } else {
    dq = 0.0; // Ch 4.2 error state (profit was mathematically impossible)
  }
  const dqRaw = dq;
  return { dqScore: Math.max(0, Math.min(1, dq)), dqScoreRaw: dqRaw };
}

/**
 * Full storage audit ledger: walks the time series against the optimal
 * dispatch, producing the same per-step rows and totals as
 * backend/main.py's process_calculation (storage mode).
 *
 * @param {object} asset       { degCost, ... } (constraints from the Unified Asset Model)
 * @param {Array}  timeSeries  [{ price, actualDischarge, actualCharge }, ...]
 * @param {number[]} optimalDischarge  aligned with timeSeries
 * @param {number[]} optimalCharge     aligned with timeSeries
 * @param {number} dtHours
 */
function calculateStorageAudit(asset, timeSeries, optimalDischarge, optimalCharge, dtHours) {
  const degCost = Number(asset.degCost ?? 5.0);
  let totalEdvOpt = 0;
  let totalEdvAct = 0;
  const decisionLog = [];

  timeSeries.forEach((ts, i) => {
    const price = Number(ts.price || 0);
    const actDis = Number(ts.actualDischarge || 0);
    const actCh = Number(ts.actualCharge || 0);
    const optDis = Number(optimalDischarge[i] || 0);
    const optCh = Number(optimalCharge[i] || 0);

    const { edvOptStep, edvActStep, gapStep } = calculateStepEDV({
      price, degCost, optDis, optCh, actDis, actCh, dtHours,
    });
    totalEdvOpt += edvOptStep;
    totalEdvAct += edvActStep;

    decisionLog.push({
      step: i,
      price,
      optimalAction: round2(optDis),
      optimalCharge: round2(optCh),
      actualAction: round2(actDis),
      actualCharge: round2(actCh),
      edvOptimalStep: round2(edvOptStep),
      edvActualStep: round2(edvActStep),
      gapStep: round2(gapStep),
    });
  });

  const { dqScore, dqScoreRaw } = calculateDQ(totalEdvOpt, totalEdvAct);
  const totalGap = totalEdvOpt - totalEdvAct;

  return {
    edvOptimalTotal: round2(totalEdvOpt),
    edvActualTotal: round2(totalEdvAct),
    totalGap: round2(totalGap),
    dqScore: round4(dqScore),
    dqScoreRaw: round4(dqScoreRaw),
    steps: timeSeries.length,
    dtHours,
    decisionLog,
  };
}

const round2 = (v) => Math.round(v * 100) / 100;
const round4 = (v) => Math.round(v * 10000) / 10000;

module.exports = { calculateStepEDV, calculateDQ, calculateStorageAudit, EDV_EPS };
