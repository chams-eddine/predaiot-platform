// ============================================================================
// PREDAIOT — Executive Command Center (the first screen).
// Answers only four questions, in order of executive priority:
//   1. How much money are we losing?      (Financial Leakage)
//   2. How much can we recover?           (Recoverable Value)
//   3. How healthy are our decisions?     (Decision Confidence)
//   4. What should we do next?            (Recommended Action)
// Consumes ONLY the existing audit response. No backend, no fake data.
// ============================================================================
import React from 'react';
import { PDS, gradeColor, riskColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, KpiCard, GradeBadge, EvidenceBadge, StatusDot } from '../design/components';
import { useWorkspaceTier } from '../workspace/tier';

const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));

export default function ExecutiveCommandCenter({ data, live }) {
  const tier = useWorkspaceTier();
  if (!data) return null;
  const currency = data.currency || 'USD';
  const leakage = num(data.total_gap_usd);
  const recoverable = num(data.recoverable_execution_gap) ??
    num((data.gap_attribution || {}).execution_gap);
  const ac = data.audit_confidence || {};
  const dqi = data.data_quality_index || {};
  // Audit-confidence grade is only populated on the file-upload path (rich DQI).
  // It is a *trust* signal shown when present — never fabricated when absent.
  const acGrade = (ac.grade && ac.grade !== 'INDETERMINATE') ? ac.grade : null;
  const acPct = num(ac.value_pct);
  const dqiPct = num(dqi.value_pct);

  // Decision health — the Economic Capture Fraction (dq_score = captured ÷ optimal,
  // Reference Manual Ch 6.1). Always present on every audit response. This is the
  // honest answer to "how healthy are our decisions?": what share of achievable
  // value the decisions actually captured.
  const ecf = num(data.dq_score);
  const ecfPct = ecf != null ? Math.max(0, Math.min(100, ecf * 100)) : null;

  // Recommended action — reuse backend-computed opportunities / root causes.
  const opps = (data.opportunities || []).filter((o) => !o.experimental && o.period_gain != null)
    .sort((a, b) => (b.period_gain || 0) - (a.period_gain || 0));
  const rcs = (data.root_causes || []).slice().sort((a, b) => (b.loss_usd || 0) - (a.loss_usd || 0));
  const action = opps[0]
    ? { title: opps[0].name, value: num(opps[0].period_gain), detail: opps[0].description || opps[0].derivation }
    : rcs[0]
      ? { title: rcs[0].category, value: num(rcs[0].loss_usd),
          detail: 'Largest recorded economic-loss bucket in this audit period.' }
      : null;

  const isLive = !!live;
  const provisional = isLive ? true : false;   // audits are certified; live states provisional

  // Recovery share of leakage (display-only ratio; no new economic logic).
  const recPct = (leakage && recoverable != null && leakage !== 0)
    ? Math.max(0, Math.min(100, (recoverable / Math.abs(leakage)) * 100)) : null;

  return (
    <div className="pds-rise">
      {/* ── Command header ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
                    flexWrap: 'wrap', gap: PDS.s4, marginBottom: PDS.s6 }}>
        <div>
          <div className="pds-kicker" style={{ color: PDS.accent }}>
            {isLive ? 'LIVE ECONOMIC COMMAND CENTER' : 'ECONOMIC DECISION AUDIT'}
          </div>
          <div style={{ fontSize: 30, fontWeight: 800, color: PDS.text, letterSpacing: '-0.015em', marginTop: 6 }}>
            {data.asset_name || 'Energy Asset'}
          </div>
          <div style={{ fontSize: 12, color: PDS.text3, marginTop: 6, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <span>{data.asset_type || 'Generic'}</span>
            <span>·</span>
            <span>{data.audit_period_label || 'Audit period'}</span>
            {data.risk_level && <>
              <span>·</span>
              <span style={{ color: riskColor(data.risk_level), display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <StatusDot color={riskColor(data.risk_level)} size={7} /> {data.risk_level} risk
              </span>
            </>}
          </div>
        </div>
        <EvidenceBadge provisional={provisional}
          hash={(data.audit_manifest || {}).input_sha256 || (data.data_quality_manifest || {}).dataset_sha256}
          status={isLive ? 'PROVISIONAL' : 'CERTIFIED'} />
      </div>

      {/* ── The four executive answers ─────────────────────────────── */}
      {/* SPEC-WS §6.3 card-grid: three answer cards, each capped at 560px;
          when they hit max, surplus width belongs to chart/rail zones —
          never card fat. Single column on T1. */}
      <div style={{ display: 'grid',
                    gridTemplateColumns: tier === 'T1' ? '1fr' : 'repeat(3, minmax(0, 560px))',
                    justifyContent: 'start', gap: 'var(--ws-card-gap)' }}>
        <KpiCard label="Financial Leakage" value={leakage != null ? Math.abs(leakage) : '—'}
          decimals={2} currency={currency} color={PDS.loss} big live={isLive}
          sub="economic gap this period" />
        <KpiCard label="Recoverable Value" value={recoverable != null ? Math.abs(recoverable) : '—'}
          decimals={2} currency={currency} color={PDS.recover} big
          sub={recPct != null ? `${fmtPct(recPct)} of leakage` : 'execution-gap basis'} />
        <DecisionHealthCard ecfPct={ecfPct} riskLevel={data.risk_level}
          acGrade={acGrade} acPct={acPct} dqiPct={dqiPct} />
      </div>

      {/* ── What to do next ────────────────────────────────────────── */}
      <div style={{ marginTop: 'var(--ws-card-gap)' }}>
        <Panel pad={PDS.s6} style={{ display: 'flex', gap: PDS.s6, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 10 }}>Recommended Action Now</div>
            {action ? (
              <>
                <div style={{ fontSize: 20, fontWeight: 800, color: PDS.text, marginBottom: 6 }}>{action.title}</div>
                <div style={{ fontSize: 13, color: PDS.text2, lineHeight: 1.6, maxWidth: 640 }}>{action.detail}</div>
              </>
            ) : (
              <div style={{ fontSize: 15, color: PDS.text2 }}>
                No material action — decisions are near economic-optimal for this period.
              </div>
            )}
          </div>
          {action && action.value != null && (
            <div style={{ textAlign: 'right', minWidth: 180 }}>
              <div className="pds-kicker" style={{ marginBottom: 8 }}>Value at Stake</div>
              <div style={{ fontSize: 34, fontWeight: 800, color: PDS.recover, lineHeight: 1 }}>
                <span className="pds-num">{fmtMoney(Math.abs(action.value), currency)}</span>
              </div>
              <div style={{ fontSize: 10, color: PDS.text3, marginTop: 8 }}>
                historical basis — no forward projection
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* Decision-health card — a circular gauge on the Economic Capture Fraction
   (share of achievable value the decisions actually captured). Colored by the
   backend risk band so the ring, the number and the verdict always agree.
   Audit-confidence / data-quality grades appear as a trust line only when the
   response carries them (file-upload path); never fabricated when absent. */
function DecisionHealthCard({ ecfPct, riskLevel, acGrade, acPct, dqiPct }) {
  const c = riskColor(riskLevel);              // low→recover, moderate→warn, severe→loss
  const pct = ecfPct != null ? ecfPct : 0;
  const R = 34, C = 2 * Math.PI * R;
  const off = C * (1 - pct / 100);
  const trust = acGrade
    ? `Audit confidence ${acGrade}${acPct != null ? ` · ${acPct.toFixed(0)}%` : ''}`
    : (dqiPct != null ? `Data quality ${dqiPct.toFixed(0)}%` : 'Capture vs optimal dispatch');
  return (
    <Panel pad={PDS.s5} style={{ flex: 1, minWidth: 240, display: 'flex', gap: PDS.s5, alignItems: 'center' }}>
      <div style={{ position: 'relative', width: 84, height: 84, flexShrink: 0 }}>
        <svg width="84" height="84" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="42" cy="42" r={R} fill="none" stroke={PDS.border} strokeWidth="7" />
          <circle cx="42" cy="42" r={R} fill="none" stroke={c} strokeWidth="7" strokeLinecap="round"
                  strokeDasharray={C} strokeDashoffset={off}
                  style={{ transition: 'stroke-dashoffset 0.8s var(--pds-ease)', filter: `drop-shadow(0 0 6px ${c}88)` }} />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', color: c }}>
          <span className="pds-num" style={{ fontSize: 20, fontWeight: 800, lineHeight: 1 }}>
            {ecfPct != null ? Math.round(ecfPct) : '—'}<span style={{ fontSize: 11 }}>%</span>
          </span>
        </div>
      </div>
      <div>
        <div className="pds-kicker" style={{ marginBottom: 8 }}>Decision Health</div>
        <div style={{ fontSize: 24, fontWeight: 800, color: c, letterSpacing: '-0.01em' }}>
          {riskLevel ? `${riskLevel} risk` : '—'}
        </div>
        <div style={{ fontSize: 11, color: PDS.text3, marginTop: 6, maxWidth: 180 }}>
          {ecfPct != null ? `${ecfPct.toFixed(1)}% of achievable value captured` : trust}
        </div>
        <div style={{ fontSize: 10, color: PDS.text3, marginTop: 4, opacity: 0.85 }}>{trust}</div>
      </div>
    </Panel>
  );
}
