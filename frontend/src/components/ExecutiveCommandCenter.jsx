// ============================================================================
// PREDAIOT — The Executive Briefing (SPEC-EX + SPEC-ST + SPEC-DL).
// S01 is ONE continuous decision narrative, not a widget grid:
//   Act 01 THE LOSS         → Q1  How much are we losing?
//   Act 02 THE OPPORTUNITY  → Q2  How much can we recover? (+ Q9 if we wait)
//   Act 03 THE ACTION       → Q4  What should we do next?  (SPEC-AI block,
//                                  Expected Impact = the block's right column)
//   Act 04 THE EVIDENCE     → Q5/Q6  Why — and can we prove it?
//   Act 05 THE OPERATIONS RECORD → Q7  What happened, step by step / live?
// Every act header names the executive question it answers (the Existence
// Test, rendered). Consumes ONLY the existing audit response; absent data
// renders as absent (SPEC-TR; FM-1/FM-3); annualized figures never render.
// ============================================================================
import React, { lazy, Suspense } from 'react';
import { PDS, gradeColor, riskColor, opportunityColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, EvidenceBadge, StatusDot } from '../design/components';
import { Zone } from '../workspace/Workspace';
import { ChartSkeleton } from '../instruments/theme';

const FinancialTimeline = lazy(() =>
  import('../instruments/charts').then((m) => ({ default: m.FinancialTimeline })));

const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));

/* Act header — the narrative spine. Each act states its question outright. */
function ActHeader({ n, title, question }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
      <span className="pds-num" style={{ fontSize: 11, color: PDS.accent, fontWeight: 700 }}>{n}</span>
      <span className="pds-kicker" style={{ color: PDS.accent }}>{title}</span>
      <span aria-hidden style={{ flex: 1, height: 1, background: PDS.hairline, alignSelf: 'center' }} />
      <span style={{ fontSize: 10, color: PDS.text3, fontStyle: 'italic', flexShrink: 0 }}>{question}</span>
    </div>
  );
}

export default function ExecutiveCommandCenter({ data, log, live, onOpenLive }) {
  if (!data) return null;
  const currency = data.currency || 'USD';
  const leakage = num(data.total_gap_usd);
  const attribution = data.gap_attribution || {};
  const recoverable = num(data.recoverable_execution_gap) ?? num(attribution.execution_gap);
  const forecastGap = num(attribution.forecast_gap);
  const captured = num(data.edv_actual_total);
  const ceiling = num(data.edv_optimal_total);
  const ecf = num(data.dq_score);
  const ecfPct = ecf != null ? Math.max(0, Math.min(100, ecf * 100)) : null;
  const ac = data.audit_confidence || {};
  const dqi = data.data_quality_index || {};
  const acGrade = (ac.grade && ac.grade !== 'INDETERMINATE') ? ac.grade : null;
  const acPct = num(ac.value_pct);
  const dqiPct = num(dqi.value_pct);

  const opps = (data.opportunities || []).slice()
    .sort((a, b) => (num(b.period_gain) ?? -Infinity) - (num(a.period_gain) ?? -Infinity));
  const primary = opps.find((o) => !o.experimental && num(o.period_gain) != null) || null;
  const alternatives = opps.filter((o) => o !== primary).slice(0, 2);
  const rcs = (data.root_causes || []).slice()
    .sort((a, b) => (b.loss_usd || 0) - (a.loss_usd || 0));

  const isLive = !!live;
  const datasetHash = (data.audit_manifest || {}).input_sha256
    || (data.data_quality_manifest || {}).dataset_sha256 || null;
  const recPct = (leakage && recoverable != null && leakage !== 0)
    ? Math.max(0, Math.min(100, (recoverable / Math.abs(leakage)) * 100)) : null;
  const period = data.audit_period_label || 'the audited period';

  return (
    <div className="pds-rise" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--ws-zone-gap)' }}>

      {/* ═══ ACT 01 — THE LOSS ═══════════════════════════════════════ */}
      <section aria-label="The loss">
        <ActHeader n="01" title="The Loss" question="How much are we losing?" />
        <Panel pad={PDS.s6} style={{ boxShadow: 'var(--pds-glow-loss), var(--pds-shadow-1)' }}>
          <div style={{ display: 'flex', gap: PDS.s6, flexWrap: 'wrap', alignItems: 'stretch' }}>
            {/* The statement — one sentence, one dominant number. */}
            <div style={{ flex: 2, minWidth: 300 }}>
              <div style={{ fontSize: 15, color: PDS.text2, lineHeight: 1.6 }}>
                <span style={{ color: PDS.text, fontWeight: 700 }}>{data.asset_name || 'This asset'}</span>
                {' '}left
              </div>
              <div className="pds-num" style={{
                fontSize: 'clamp(44px, 4.6vw, 72px)', fontWeight: 800, lineHeight: 1.05,
                color: PDS.loss, letterSpacing: '-0.02em',
                textShadow: '0 0 40px rgba(255,92,122,0.18)',
              }}>
                {leakage != null
                  ? Math.abs(leakage).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                  : '—'}
                <span style={{ fontSize: '0.32em', color: PDS.text2, fontWeight: 600, marginLeft: 10 }}>{currency}</span>
              </div>
              <div style={{ fontSize: 15, color: PDS.text2, lineHeight: 1.6, marginTop: 4 }}>
                of achievable value unrealized in {period}
                {ecfPct != null && <> — <span style={{ color: PDS.text, fontWeight: 700 }}>{ecfPct.toFixed(1)}%</span> of the optimum was captured.</>}
              </div>
            </div>
            {/* The verdict — dial + risk + provenance (Q3, folded into Act 01). */}
            <div style={{ minWidth: 220, display: 'flex', flexDirection: 'column', gap: 10,
                          justifyContent: 'center', alignItems: 'flex-start',
                          borderLeft: `1px solid ${PDS.hairline}`, paddingLeft: PDS.s5 }}>
              <VerdictDial ecfPct={ecfPct} riskLevel={data.risk_level} />
              <div style={{ fontSize: 11, color: PDS.text3 }}>
                {acGrade ? `Audit confidence ${acGrade}${acPct != null ? ` · ${acPct.toFixed(0)}%` : ''}`
                  : dqiPct != null ? `Data quality ${dqiPct.toFixed(0)}%`
                  : 'Capture measured against the optimal dispatch benchmark'}
              </div>
              <EvidenceBadge provisional={isLive} hash={datasetHash}
                status={isLive ? 'PROVISIONAL' : 'CERTIFIED'} />
            </div>
          </div>
          {/* IN-04 Economic Allocation — where the period's value went. */}
          <AllocationBar captured={captured} recoverable={recoverable}
            forecastGap={forecastGap} leakage={leakage} ceiling={ceiling} currency={currency} />
        </Panel>
      </section>

      {/* ═══ ACT 02 — THE OPPORTUNITY ════════════════════════════════ */}
      <section aria-label="The opportunity">
        <ActHeader n="02" title="The Opportunity" question="How much can we recover?" />
        <div style={{ padding: `0 ${PDS.s2}` }}>
          <div style={{ fontSize: 17, color: PDS.text2, lineHeight: 1.7, maxWidth: 'var(--pds-prose-max)' }}>
            <span className="pds-num" style={{ fontSize: 26, fontWeight: 800, color: PDS.recover }}>
              {recoverable != null ? fmtMoney(Math.abs(recoverable), currency) : '—'}
            </span>
            {recPct != null && <> — <span style={{ color: PDS.text, fontWeight: 700 }}>{fmtPct(recPct)}</span> of the loss —</>}
            {' '}was winnable with the information available at decision time.
            {forecastGap != null && forecastGap > 0 && (
              <span style={{ color: PDS.text3 }}> The remaining {fmtMoney(forecastGap, currency)} required
              perfect price foresight and is not operator-attributable.</span>
            )}
          </div>
          {/* Q9 — the cost of waiting, in recorded terms only. */}
          {recoverable != null && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 10 }}>
              This period recorded {fmtMoney(Math.abs(recoverable), currency)} recoverable in {period}.
              Basis: recorded period only — no forward projection.
            </div>
          )}
        </div>
      </section>

      {/* ═══ ACT 03 — THE ACTION (+ Expected Impact) ═════════════════ */}
      <section aria-label="The recommended action">
        <ActHeader n="03" title="The Action" question="What should we do — and what is it worth?" />
        <RecommendationBlock primary={primary} alternatives={alternatives}
          currency={currency} acGrade={acGrade} acPct={acPct} dqiPct={dqiPct}
          fallbackRc={rcs[0]} />
      </section>

      {/* ═══ ACT 04 — THE EVIDENCE ═══════════════════════════════════ */}
      <section aria-label="The evidence">
        <ActHeader n="04" title="The Evidence" question="Why did it happen — and can we prove it?" />
        <Zone row="primary">
          <ReasoningPanel rcs={rcs} currency={currency} />
          <EvidencePanel isLive={isLive} datasetHash={datasetHash} dqi={dqi} ac={ac} data={data} />
        </Zone>
      </section>

      {/* ═══ ACT 05 — THE OPERATIONS RECORD ══════════════════════════ */}
      <section aria-label="The operations record">
        <ActHeader n="05" title="The Operations Record"
          question={isLive ? 'What is happening right now?' : 'What happened, step by step?'} />
        <Panel pad={PDS.s5}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                        marginBottom: 10, gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: PDS.text2 }}>
              Market price against per-step captured value — {period}
              {isLive && <span style={{ color: PDS.provisional }}> · PROVISIONAL live stream</span>}
            </span>
            {onOpenLive && (
              <button onClick={onOpenLive} style={{
                background: 'none', border: `1px solid ${PDS.border}`, color: PDS.text2,
                borderRadius: PDS.rSm, padding: '5px 12px', cursor: 'pointer',
                fontSize: 10, letterSpacing: '0.1em', fontWeight: 700,
              }}>
                OPEN LIVE MONITOR
              </button>
            )}
          </div>
          <Suspense fallback={<ChartSkeleton h={230} />}>
            <FinancialTimeline log={log} />
          </Suspense>
        </Panel>
      </section>
    </div>
  );
}

/* IN-01 Economic Dial — compact verdict form for the Act-01 hero. */
function VerdictDial({ ecfPct, riskLevel }) {
  const c = riskColor(riskLevel);
  const pct = ecfPct != null ? ecfPct : 0;
  const R = 26, C = 2 * Math.PI * R;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ position: 'relative', width: 64, height: 64, flexShrink: 0 }}>
        <svg width="64" height="64" style={{ transform: 'rotate(-90deg)' }} role="img"
             aria-label={`Decision health: ${ecfPct != null ? ecfPct.toFixed(1) : 'unknown'} percent of achievable value captured${riskLevel ? ` — ${riskLevel} risk` : ''}`}>
          <circle cx="32" cy="32" r={R} fill="none" stroke={PDS.border} strokeWidth="6" />
          <circle cx="32" cy="32" r={R} fill="none" stroke={c} strokeWidth="6" strokeLinecap="round"
                  strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)}
                  style={{ transition: 'stroke-dashoffset var(--pds-dur-slow) var(--pds-ease)',
                           filter: `drop-shadow(0 0 5px ${c}88)` }} />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', color: c }}>
          <span className="pds-num" style={{ fontSize: 15, fontWeight: 800 }}>
            {ecfPct != null ? Math.round(ecfPct) : '—'}<span style={{ fontSize: 9 }}>%</span>
          </span>
        </div>
      </div>
      <div>
        <div className="pds-kicker" style={{ marginBottom: 4 }}>Decision Health</div>
        <div style={{ fontSize: 18, fontWeight: 800, color: c, letterSpacing: '-0.01em' }}>
          {riskLevel ? `${riskLevel} risk` : '—'}
        </div>
      </div>
    </div>
  );
}

/* IN-04 Economic Allocation — one full-width bar: where the value went.
   Ceiling is context, never a value class (SPEC-EV rule 2). */
function AllocationBar({ captured, recoverable, forecastGap, leakage, ceiling, currency }) {
  const segs = [];
  if (captured != null) segs.push({ k: 'Captured', v: Math.max(0, captured), c: PDS.recover, cls: 'money protected' });
  if (recoverable != null) segs.push({ k: 'Recoverable execution gap', v: Math.abs(recoverable), c: PDS.loss, cls: 'money recoverable' });
  if (forecastGap != null && forecastGap > 0) segs.push({ k: 'Forecast-unreachable', v: forecastGap, c: PDS.text3, cls: 'benchmark context' });
  if (segs.length < 2 && leakage != null && captured != null) {
    segs.length = 0;
    segs.push({ k: 'Captured', v: Math.max(0, captured), c: PDS.recover });
    segs.push({ k: 'Economic gap', v: Math.abs(leakage), c: PDS.loss });
  }
  const total = segs.reduce((a, s) => a + s.v, 0);
  if (!total) return null;
  return (
    <div style={{ marginTop: PDS.s5 }}>
      <div style={{ display: 'flex', height: 10, borderRadius: 6, overflow: 'hidden',
                    border: `1px solid ${PDS.border}` }} role="img"
           aria-label={`Economic allocation: ${segs.map((s) => `${s.k} ${fmtMoney(s.v, currency)}`).join(', ')}`}>
        {segs.map((s) => (
          <div key={s.k} style={{ width: `${(s.v / total) * 100}%`, background: s.c, opacity: 0.85 }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: PDS.s5, marginTop: 8, flexWrap: 'wrap' }}>
        {segs.map((s) => (
          <span key={s.k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: PDS.text3 }}>
            <StatusDot color={s.c} size={6} />
            {s.k} <span className="pds-num" style={{ color: PDS.text2, fontWeight: 700 }}>{fmtMoney(s.v, currency)}</span>
          </span>
        ))}
        {ceiling != null && (
          <span style={{ fontSize: 11, color: PDS.text3, marginLeft: 'auto' }}>
            Theoretical ceiling <span className="pds-num">{fmtMoney(ceiling, currency)}</span> — perfect-foresight benchmark, not a target
          </span>
        )}
      </div>
    </div>
  );
}

/* Act 03 — the PREDAIOT Recommendation Block (SPEC-AI minimum lawful
   anatomy). Expected Impact is the block's right column; alternatives are
   always visible; annualized gains never render (rule 5). */
function RecommendationBlock({ primary, alternatives, currency, acGrade, acPct, dqiPct, fallbackRc }) {
  if (!primary && !fallbackRc) {
    return (
      <Panel pad={PDS.s6}>
        <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 8 }}>PREDAIOT Recommendation</div>
        <div style={{ fontSize: 14, color: PDS.text2 }}>
          No material action — decisions are near economic-optimal for this period.
        </div>
      </Panel>
    );
  }
  const p = primary || {
    name: fallbackRc.category, period_gain: fallbackRc.loss_usd,
    description: 'Largest recorded economic-loss bucket in this audit period.',
    evidence: null, derivation: null, intervals_observed: null, experimental: false,
  };
  const confidenceLine = p.confidence_pct != null
    ? `Opportunity confidence ${fmtPct(p.confidence_pct, 0)}`
    : acGrade
      ? `Audit confidence ${acGrade}${acPct != null ? ` · ${acPct.toFixed(0)}%` : ''}`
      : dqiPct != null
        ? `Data quality ${dqiPct.toFixed(0)}%`
        : 'Confidence INDETERMINATE — data-quality index not computed on this audit path';
  return (
    <Panel pad={PDS.s6}>
      <div style={{ display: 'flex', gap: PDS.s6, flexWrap: 'wrap' }}>
        <div style={{ flex: 2, minWidth: 300 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span className="pds-kicker" style={{ color: PDS.accent }}>PREDAIOT Recommendation</span>
            {p.experimental && (
              <span className="pds-num" style={{ fontSize: 9, letterSpacing: '0.1em', color: PDS.text3,
                border: `1px solid ${PDS.border}`, borderRadius: PDS.rPill, padding: '2px 8px' }}>
                EXPERIMENTAL
              </span>
            )}
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: PDS.text, marginBottom: 6 }}>{p.name}</div>
          <div style={{ fontSize: 13, color: PDS.text2, lineHeight: 1.6, maxWidth: 'var(--pds-prose-max)' }}>
            {p.description}
          </div>
          {p.evidence && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 10, lineHeight: 1.55,
                          maxWidth: 'var(--pds-prose-max)' }}>
              <span style={{ color: PDS.text2, fontWeight: 700 }}>Evidence · </span>{p.evidence}
            </div>
          )}
          <div style={{ fontSize: 11, color: PDS.text3, marginTop: 6 }}>
            <span style={{ color: PDS.text2, fontWeight: 700 }}>Confidence · </span>{confidenceLine}
          </div>
          {p.derivation && (
            <div style={{ fontSize: 10, color: PDS.text3, marginTop: 6, opacity: 0.8,
                          maxWidth: 'var(--pds-prose-max)' }}>
              <span style={{ fontWeight: 700 }}>Method · </span>{p.derivation}
            </div>
          )}
        </div>
        <div style={{ textAlign: 'right', minWidth: 180, flex: 1 }}>
          <div className="pds-kicker" style={{ marginBottom: 8 }}>Expected Impact</div>
          <div style={{ fontSize: 34, fontWeight: 800, color: PDS.recover, lineHeight: 1 }}>
            <span className="pds-num">{fmtMoney(Math.abs(num(p.period_gain) ?? 0), currency)}</span>
          </div>
          <div style={{ fontSize: 10, color: PDS.text3, marginTop: 8 }}>
            recorded this period — no forward projection
          </div>
          {p.intervals_observed != null && (
            <div className="pds-num" style={{ fontSize: 10, color: PDS.text3, marginTop: 4 }}>
              {p.intervals_observed} intervals observed
            </div>
          )}
        </div>
      </div>
      {alternatives && alternatives.length > 0 && (
        <div style={{ marginTop: PDS.s5, paddingTop: PDS.s4, borderTop: `1px solid ${PDS.hairline}` }}>
          <div className="pds-kicker" style={{ marginBottom: 8 }}>Alternative Actions</div>
          <div style={{ display: 'flex', gap: PDS.s5, flexWrap: 'wrap' }}>
            {alternatives.map((a) => {
              const gain = num(a.period_gain);
              return (
                <div key={a.name} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <StatusDot color={opportunityColor(a.experimental)} size={6} />
                  <span style={{ fontSize: 12, color: PDS.text2 }}>{a.name}</span>
                  {gain != null ? (
                    <span className="pds-num" style={{ fontSize: 12, color: opportunityColor(a.experimental), fontWeight: 700 }}>
                      {fmtMoney(Math.abs(gain), currency)}
                    </span>
                  ) : (
                    <span style={{ fontSize: 10, color: PDS.text3 }}>no recorded gain</span>
                  )}
                  {a.experimental && <span style={{ fontSize: 9, color: PDS.text3, letterSpacing: '0.08em' }}>EXPERIMENTAL</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Panel>
  );
}

/* Act 04 left — why value leaked: recorded root-cause attribution. */
function ReasoningPanel({ rcs, currency }) {
  return (
    <Panel pad={PDS.s5}>
      <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 12 }}>Why Value Leaked</div>
      {(!rcs || rcs.length === 0) ? (
        <div style={{ fontSize: 12, color: PDS.text3 }}>No root-cause decomposition recorded for this audit.</div>
      ) : rcs.slice(0, 4).map((rc) => (
        <div key={rc.category} style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
            <span style={{ fontSize: 12, color: PDS.text2 }}>{rc.category}</span>
            <span className="pds-num" style={{ fontSize: 12, color: PDS.loss, fontWeight: 700 }}>
              {fmtMoney(rc.loss_usd, currency)}
              <span style={{ color: PDS.text3, fontWeight: 400 }}> · {fmtPct(rc.contribution_pct, 0)}</span>
            </span>
          </div>
          <div style={{ height: 4, background: PDS.hairline, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: '100%', height: '100%',
                          background: PDS.loss, borderRadius: 2, opacity: 0.8,
                          transform: `scaleX(${Math.min(100, rc.contribution_pct || 0) / 100})`,
                          transformOrigin: 'left',
                          transition: 'transform var(--pds-dur-slow) var(--pds-ease)' }} />
          </div>
        </div>
      ))}
    </Panel>
  );
}

/* Act 04 right — evidence: only artifacts that actually exist render. */
function EvidencePanel({ isLive, datasetHash, dqi, ac, data }) {
  const rows = [
    { k: 'Provenance', v: isLive ? 'PROVISIONAL — live state, awaiting reconciliation' : 'CERTIFIED — batch audit engine', c: isLive ? PDS.provisional : PDS.verified },
    datasetHash && { k: 'Dataset SHA-256', v: `${String(datasetHash).slice(0, 18)}…`, mono: true, full: datasetHash },
    data.audit_period_label && { k: 'Audited period', v: data.audit_period_label },
    dqi.grade && { k: 'Data quality', v: `Grade ${dqi.grade}${dqi.value_pct != null ? ` · ${dqi.value_pct}%` : ''}`, c: gradeColor(dqi.grade) },
    ac.grade && { k: 'Audit confidence', v: `${ac.grade}${ac.value_pct != null ? ` · ${ac.value_pct}%` : ''}`, c: gradeColor(ac.grade) },
    !datasetHash && { k: 'Input manifest', v: 'None — JSON audit input (no file manifest)' },
  ].filter(Boolean);
  return (
    <Panel pad={PDS.s5}>
      <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 12 }}>Evidence</div>
      {rows.map((r) => (
        <div key={r.k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12,
                                padding: '7px 0', borderBottom: `1px solid ${PDS.hairline}` }}>
          <span style={{ fontSize: 11, color: PDS.text3, flexShrink: 0 }}>{r.k}</span>
          <span className={r.mono ? 'pds-num' : undefined}
                title={r.full || undefined}
                onClick={r.full ? () => navigator.clipboard && navigator.clipboard.writeText(r.full) : undefined}
                style={{ fontSize: 11, color: r.c || PDS.text2, textAlign: 'right',
                         cursor: r.full ? 'copy' : 'default', overflowWrap: 'anywhere' }}>
            {r.v}
          </span>
        </div>
      ))}
    </Panel>
  );
}
