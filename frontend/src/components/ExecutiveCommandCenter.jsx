// ============================================================================
// PREDAIOT — THE EXECUTIVE BRIEFING (S01). GOV-AL amendment #2.
// Six Executive Acts on one continuous spine — a board presentation, never a
// dashboard. Each Act carries a formal contract (below, defined before its
// implementation), answers exactly ONE executive question, consumes only the
// frozen audit API, and leads into the next Act. No KPI appears twice.
// Absent data renders as absent (SPEC-TR; FM-1/FM-3); annualized figures
// never render (SPEC-AI rule 5).
// ============================================================================
import React, { lazy, Suspense } from 'react';
import { PDS, gradeColor, riskColor, opportunityColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, EvidenceBadge, StatusDot } from '../design/components';
import { facilityName } from '../presentation/ontology/TerminologyResolver';
import { Zone } from '../workspace/Workspace';
import { ChartSkeleton } from '../instruments/theme';
import PrimeCounter from '../motion/PrimeCounter';

const FinancialTimeline = lazy(() =>
  import('../instruments/charts').then((m) => ({ default: m.FinancialTimeline })));

const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));

/* ── The spine ───────────────────────────────────────────────────────────
   Acts sit on a single vertical rail; each Act's numeral is a node on it.
   The rail is the visual transition between Acts — the page reads as one
   document flowing downward, never as adjacent widgets. */
function Act({ n, title, question, children }) {
  return (
    <section aria-label={`Act ${n} — ${title}`} style={{ position: 'relative', paddingLeft: 38 }}>
      {/* node on the spine */}
      <span aria-hidden className="pds-num" style={{
        position: 'absolute', left: 0, top: 0, width: 22, height: 22,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 800, color: PDS.accent,
        border: `1px solid ${PDS.accent}55`, borderRadius: '50%',
        background: PDS.panel,
      }}>{n}</span>
      {/* editorial standfirst: quiet label left, the question as a calm
          right-aligned deck — no italics, no ornament. */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 18, minHeight: 22 }}>
        <span className="pds-kicker" style={{ color: PDS.accent }}>{title}</span>
        <span aria-hidden style={{ flex: 1, height: 1, background: PDS.hairline, alignSelf: 'center', opacity: 0.6 }} />
        <span style={{ fontSize: 11, color: PDS.text3, letterSpacing: '0.02em', flexShrink: 0 }}>{question}</span>
      </div>
      {children}
    </section>
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
    <div className="pds-rise" style={{ position: 'relative', display: 'flex', flexDirection: 'column',
                                       gap: 'calc(var(--ws-zone-gap) * 1.5)' }}>
      {/* the spine rail itself — accent at the top, fading to hairline */}
      <div aria-hidden style={{
        position: 'absolute', left: 11, top: 22, bottom: 10, width: 1,
        background: `linear-gradient(180deg, ${PDS.accent}55, var(--pds-hairline) 30%, var(--pds-hairline))`,
      }} />

      {/* ══════════════════════════════════════════════════════════════
          ACT I — ECONOMIC SITUATION
          · Executive Question   What is our current economic reality?
          · Purpose              Orient the executive: which asset, which
                                 period, how healthy its decisions are, and
                                 whether this picture is certified truth.
          · Required API fields  asset_name, asset_type, audit_period_label,
                                 dq_score (ECF), risk_level, audit_confidence,
                                 data_quality_index, audit_manifest hash,
                                 provenance (live flag).
          · Why it exists        No figure is meaningful before identity,
                                 verdict, and trust state are established.
          · Decision supported   "Do I need to act on this asset at all?"
          · Why before Act II    Situation precedes quantification — a board
                                 hears the state of affairs before the bill.
          · Instrument           IN-01 Economic Dial (compact verdict form).
          · Never inside it      Money numerals of any value class (they
                                 belong to Act II), charts, opportunities.
      ══════════════════════════════════════════════════════════════ */}
      <Act n="I" title="Economic Situation" question="What is our current economic reality?">
        {/* Open editorial title page — no box. The masthead, one standfirst
            sentence, the trust anchors; the verdict figure to the right. */}
        <div style={{ display: 'flex', gap: PDS.s7, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 2, minWidth: 300 }}>
            <div style={{ fontSize: 'clamp(26px, 2.4vw, 38px)', fontWeight: 800, color: PDS.text,
                          letterSpacing: '-0.02em', lineHeight: 1.15 }}>
              {data.asset_name || facilityName(data.facility_profile)}
            </div>
            <div style={{ fontSize: 16, color: PDS.text2, lineHeight: 1.75, marginTop: 12,
                          maxWidth: 'var(--pds-prose-max)' }}>
              Over {period}, this {data.facility_profile ? facilityName(data.facility_profile) : (data.asset_type || 'asset')} operated at{' '}
              <span style={{ color: riskColor(data.risk_level), fontWeight: 700 }}>
                {ecfPct != null ? `${ecfPct.toFixed(1)}%` : 'an unmeasured share'} of its achievable economic optimum
              </span>
              {data.risk_level && <> — a <span style={{ color: riskColor(data.risk_level), fontWeight: 700 }}>{data.risk_level.toLowerCase()}-risk</span> decision posture</>}.
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginTop: 16 }}>
              <EvidenceBadge provisional={isLive} hash={datasetHash}
                status={isLive ? 'PROVISIONAL' : 'CERTIFIED'} />
              <span style={{ fontSize: 11, color: PDS.text3 }}>
                {acGrade ? `Audit confidence ${acGrade}${acPct != null ? ` · ${acPct.toFixed(0)}%` : ''}`
                  : dqiPct != null ? `Data quality ${dqiPct.toFixed(0)}%`
                  : 'Measured against the optimal-dispatch benchmark of the certified audit engine'}
              </span>
            </div>
          </div>
          <div style={{ borderLeft: `1px solid ${PDS.hairline}`, paddingLeft: PDS.s6 }}>
            <VerdictDial ecfPct={ecfPct} riskLevel={data.risk_level} />
          </div>
        </div>
      </Act>

      {/* ══════════════════════════════════════════════════════════════
          ACT II — FINANCIAL IMPACT
          · Executive Question   How much value are we losing or protecting?
          · Purpose              Quantify the situation: the loss, what was
                                 protected, and what is winnable — with the
                                 recorded cost of waiting.
          · Required API fields  total_gap_usd, edv_actual_total,
                                 gap_attribution.{execution_gap,forecast_gap},
                                 recoverable_execution_gap, edv_optimal_total,
                                 currency.
          · Why it exists        Money is the platform's native language; the
                                 briefing's single dominant numeral lives here.
          · Decision supported   "Is the stake large enough to command my
                                 attention now?"
          · Why before Act III   The magnitude justifies the analysis; a board
                                 asks 'how much' before 'why'.
          · Instrument           IN-04 Economic Allocation (one bar: where the
                                 period's value went).
          · Never inside it      Capture % or risk verdict (Act I), causes
                                 (Act III), recommendations (Act IV).
      ══════════════════════════════════════════════════════════════ */}
      <Act n="II" title="Financial Impact" question="How much value are we losing or protecting?">
        <Panel pad="clamp(28px, 3vw, 44px)" style={{ boxShadow: 'var(--pds-glow-loss), var(--pds-shadow-1)' }}>
          <div className="pds-kicker" style={{ marginBottom: 14 }}>Value left unrealized · {period}</div>
          {/* SPEC-MI · PrimeCounter — the audited figure MOUNTS with spring
              physics (stiffness 45 / damping 18) instead of jumping. MI-0:
              target is the real total_gap_usd, nothing invented. */}
          {leakage != null ? (
            <PrimeCounter
              value={Math.abs(leakage)} mode="currency" intent="leak" currency={currency}
              numStyle={{ fontSize: 'clamp(48px, 5vw, 80px)', letterSpacing: '-0.025em', lineHeight: 1.02 }}
            />
          ) : (
            <div className="pds-num" style={{ fontSize: 'clamp(48px, 5vw, 80px)', fontWeight: 800, color: PDS.loss }}>—</div>
          )}
          <div style={{ fontSize: 15, color: PDS.text2, lineHeight: 1.75, marginTop: 16, maxWidth: 'var(--pds-prose-max)' }}>
            Of this,{' '}
            <span className="pds-num" style={{ color: PDS.recover, fontWeight: 800 }}>
              {recoverable != null ? fmtMoney(Math.abs(recoverable), currency) : '—'}
            </span>
            {recPct != null && <> ({fmtPct(recPct)})</>} was winnable with the information available at
            decision time
            {forecastGap != null && forecastGap > 0 && (
              <span style={{ color: PDS.text3 }}> — the remaining {fmtMoney(forecastGap, currency)} required
              perfect price foresight and is not operator-attributable</span>
            )}.
          </div>
          <AllocationBar captured={captured} recoverable={recoverable}
            forecastGap={forecastGap} leakage={leakage} ceiling={ceiling} currency={currency} />
          {/* Q9 — the recorded cost of waiting. */}
          {recoverable != null && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 14 }}>
              Recorded recoverable value for {period}: {fmtMoney(Math.abs(recoverable), currency)}.
              Basis: recorded period only — no forward projection.
            </div>
          )}
        </Panel>
      </Act>

      {/* ══════════════════════════════════════════════════════════════
          ACT III — DECISION ANALYSIS
          · Executive Question   Why is this happening?
          · Purpose              Attribute the loss to recorded causes so the
                                 coming decision targets truth, not symptoms.
          · Required API fields  root_causes[] {category, loss_usd,
                                 contribution_pct}.
          · Why it exists        A recommendation without attribution is an
                                 opinion; this act is the causal bridge.
          · Decision supported   "Which failure mode am I about to fix?"
          · Why before Act IV    Cause precedes prescription — the diagnosis
                                 legitimizes the treatment.
          · Instrument           IN-06 Leakage Flow (attribution bars).
          · Never inside it      Totals from Act II, actions, evidence
                                 artifacts, confidence grades.
      ══════════════════════════════════════════════════════════════ */}
      <Act n="III" title="Decision Analysis" question="Why is this happening?">
        {/* Open ranked exhibit — a board report's attribution list, not a
            grid of widgets. One column, rank numerals, full-width bars. */}
        {(!rcs || rcs.length === 0) ? (
          <div style={{ fontSize: 12, color: PDS.text3 }}>No root-cause decomposition recorded for this audit.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 860 }}>
            {rcs.slice(0, 4).map((rc, i) => (
              <div key={rc.category} style={{ display: 'flex', gap: 18, alignItems: 'baseline' }}>
                <span className="pds-num" style={{ fontSize: 12, color: PDS.text3, width: 22, flexShrink: 0 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                                gap: 12, marginBottom: 7 }}>
                    <span style={{ fontSize: 14, color: PDS.text, fontWeight: i === 0 ? 700 : 500 }}>
                      {rc.category}
                    </span>
                    <span className="pds-num" style={{ fontSize: 13, color: PDS.loss, fontWeight: 700, flexShrink: 0 }}>
                      {fmtMoney(rc.loss_usd, currency)}
                      <span style={{ color: PDS.text3, fontWeight: 400 }}> · {fmtPct(rc.contribution_pct, 0)}</span>
                    </span>
                  </div>
                  <div style={{ height: 3, background: PDS.hairline, borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ width: '100%', height: '100%',
                                  background: PDS.loss, borderRadius: 2, opacity: i === 0 ? 0.9 : 0.55,
                                  transform: `scaleX(${Math.min(100, rc.contribution_pct || 0) / 100})`,
                                  transformOrigin: 'left',
                                  transition: 'transform var(--pds-dur-slow) var(--pds-ease)' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Act>

      {/* ══════════════════════════════════════════════════════════════
          ACT IV — RECOMMENDED DECISION
          · Executive Question   What should we do now?
          · Purpose              Present the governed decision: designation,
                                 the action, its reasoning, and the ranked
                                 alternatives (SPEC-AI rules 2–3).
          · Required API fields  opportunities[] {name, description,
                                 experimental}, root_causes (fallback).
          · Why it exists        The briefing exists to improve decisions
                                 (FM-10); this is the decision.
          · Decision supported   The decision itself — accept, defer, or
                                 choose an alternative.
          · Why before Act V     The proposal precedes its valuation and
                                 proof — a board hears the motion, then the
                                 case for it.
          · Instrument           None — a decision is text, not a chart.
          · Never inside it      Money (the expected outcome belongs to
                                 Act V), confidence grades, hashes.
      ══════════════════════════════════════════════════════════════ */}
      <Act n="IV" title="Recommended Decision" question="What should we do now?">
        <DecisionPanel primary={primary} alternatives={alternatives} fallbackRc={rcs[0]} currency={currency} />
      </Act>

      {/* ══════════════════════════════════════════════════════════════
          ACT V — EXPECTED OUTCOME & EVIDENCE
          · Executive Question   Why should we trust this recommendation?
          · Purpose              Value the decision in recorded terms and
                                 chain it to verifiable artifacts: ledger
                                 evidence, method, confidence, dataset hash.
          · Required API fields  primary opportunity {period_gain, evidence,
                                 derivation, intervals_observed,
                                 confidence_pct}, audit_confidence,
                                 data_quality_index, manifest hashes.
          · Why it exists        Trust is shown, never asserted (SPEC-TM);
                                 every figure must sit near its proof (P7).
          · Decision supported   "Do I sign off on Act IV?"
          · Why before Act VI    Proof closes the case before attention
                                 returns to the running plant.
          · Instrument           Evidence ledger rows (SPEC-ID evidence-as-
                                 jewelry); mono numerals.
          · Never inside it      The recommendation text (Act IV), situation
                                 verdicts (Act I), loss totals (Act II).
      ══════════════════════════════════════════════════════════════ */}
      <Act n="V" title="Expected Outcome & Evidence" question="Why should we trust this recommendation?">
        <Zone row="primary">
          <OutcomePanel primary={primary} currency={currency}
            acGrade={acGrade} acPct={acPct} dqiPct={dqiPct} />
          <EvidencePanel datasetHash={datasetHash} dqi={dqi} ac={ac} />
        </Zone>
      </Act>

      {/* ══════════════════════════════════════════════════════════════
          ACT VI — LIVE OPERATIONAL CONTEXT
          · Executive Question   What is happening right now while we decide?
          · Purpose              Ground the decision in the operating record:
                                 the step-by-step economics of the period, and
                                 the doorway to the live stream.
          · Required API fields  decision_log[] {hour, price,
                                 edv_actual_step}; dataSource (live flag).
          · Why it exists        Decisions age; the executive leaves the
                                 briefing knowing what the plant is doing.
          · Decision supported   "Does current operation change my sign-off?"
          · Why it closes        The story returns from judgment to reality —
                                 the last word belongs to the machine.
          · Instrument           IN-13 Financial Timeline (lazy chunk).
          · Never inside it      Recommendations, totals, verdicts, evidence
                                 artifacts — context only.
      ══════════════════════════════════════════════════════════════ */}
      <Act n="VI" title="Live Operational Context"
           question={isLive ? 'What is happening right now?' : 'What is happening while we decide?'}>
        <Panel pad={PDS.s5}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                        marginBottom: 10, gap: 12, flexWrap: 'wrap' }}>
            {/* Period lives in Acts I–II; it does not echo here. */}
            <span style={{ fontSize: 12, color: PDS.text3 }}>
              Market price against per-step captured value
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
      </Act>
    </div>
  );
}

/* IN-01 Economic Dial — Act I verdict form. */
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

/* IN-04 Economic Allocation — Act II: where the period's value went.
   Ceiling is context, never a value class (SPEC-EV rule 2). */
function AllocationBar({ captured, recoverable, forecastGap, leakage, ceiling, currency }) {
  const segs = [];
  if (captured != null) segs.push({ k: 'Protected (captured)', v: Math.max(0, captured), c: PDS.recover });
  if (recoverable != null) segs.push({ k: 'Recoverable Opportunity', v: Math.abs(recoverable), c: PDS.loss });
  if (forecastGap != null && forecastGap > 0) segs.push({ k: 'Forecast-unreachable', v: forecastGap, c: PDS.text3 });
  if (segs.length < 2 && leakage != null && captured != null) {
    segs.length = 0;
    segs.push({ k: 'Protected (captured)', v: Math.max(0, captured), c: PDS.recover });
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
      <div style={{ display: 'flex', gap: PDS.s5, marginTop: 10, flexWrap: 'wrap' }}>
        {segs.map((s) => (
          <span key={s.k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: PDS.text3 }}>
            <StatusDot color={s.c} size={6} />
            {s.k} <span className="pds-num" style={{ color: PDS.text2, fontWeight: 700 }}>{fmtMoney(s.v, currency)}</span>
          </span>
        ))}
      </div>
      {/* Benchmark caption on its own quiet line — never fights the legend. */}
      {ceiling != null && (
        <div style={{ fontSize: 10, color: PDS.text3, opacity: 0.85, marginTop: 7, textAlign: 'right' }}>
          Maximum theoretical savings <span className="pds-num">{fmtMoney(ceiling, currency)}</span> — perfect-foresight upper bound, not an achievable target
        </div>
      )}
    </div>
  );
}

/* Act IV — the decision itself. Money and proof live in Act V; together the
   two acts form the complete SPEC-AI Recommendation anatomy on one screen. */
function DecisionPanel({ primary, alternatives, fallbackRc, currency }) {
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
    name: fallbackRc.category,
    description: 'Largest recorded economic-loss bucket in this audit period.',
    experimental: false,
  };
  return (
    <Panel pad="clamp(28px, 3vw, 44px)" accent>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span className="pds-kicker" style={{ color: PDS.accent }}>PREDAIOT Recommendation</span>
        {p.experimental && (
          <span className="pds-num" style={{ fontSize: 9, letterSpacing: '0.1em', color: PDS.text3,
            border: `1px solid ${PDS.border}`, borderRadius: PDS.rPill, padding: '2px 8px' }}>
            EXPERIMENTAL
          </span>
        )}
      </div>
      <div style={{ fontSize: 'clamp(22px, 2vw, 30px)', fontWeight: 800, color: PDS.text,
                    marginBottom: 10, letterSpacing: '-0.015em', lineHeight: 1.2 }}>
        {p.name}
      </div>
      <div style={{ fontSize: 15, color: PDS.text2, lineHeight: 1.75, maxWidth: 'var(--pds-prose-max)' }}>
        {p.description}
      </div>
      {alternatives && alternatives.length > 0 && (
        <div style={{ marginTop: PDS.s6, paddingTop: PDS.s5, borderTop: `1px solid ${PDS.hairline}` }}>
          <div className="pds-kicker" style={{ marginBottom: 12 }}>Alternative Decisions</div>
          <div style={{ display: 'flex', gap: PDS.s6, rowGap: 12, flexWrap: 'wrap' }}>
            {alternatives.map((a) => {
              const gain = num(a.period_gain);
              return (
                <div key={a.name} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <StatusDot color={opportunityColor(a.experimental)} size={6} />
                  <span style={{ fontSize: 13, color: PDS.text2 }}>{a.name}</span>
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

/* Act V left — the decision's worth, in recorded terms, with its case. */
function OutcomePanel({ primary, currency, acGrade, acPct, dqiPct }) {
  const gain = primary ? num(primary.period_gain) : null;
  const confidenceLine = primary && primary.confidence_pct != null
    ? `Opportunity confidence ${fmtPct(primary.confidence_pct, 0)}`
    : acGrade
      ? `Audit confidence ${acGrade}${acPct != null ? ` · ${acPct.toFixed(0)}%` : ''}`
      : dqiPct != null
        ? `Data quality ${dqiPct.toFixed(0)}%`
        : 'INDETERMINATE — data-quality index not computed on this audit path';
  return (
    <Panel pad={PDS.s5}>
      <div className="pds-kicker" style={{ marginBottom: 12 }}>Expected Outcome</div>
      <div style={{ fontSize: 'clamp(34px, 3vw, 44px)', fontWeight: 800, color: PDS.recover,
                    lineHeight: 1, letterSpacing: '-0.02em' }}>
        <span className="pds-num">{gain != null ? fmtMoney(Math.abs(gain), currency) : '—'}</span>
      </div>
      <div style={{ fontSize: 11, color: PDS.text3, marginTop: 10 }}>
        recorded this period — no forward projection
        {primary && primary.intervals_observed != null && (
          <span className="pds-num"> · {primary.intervals_observed} intervals observed</span>
        )}
      </div>
      {/* The case — a ledger of two lines, generously spaced. */}
      <div style={{ marginTop: PDS.s5, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {primary && primary.evidence && (
          <div style={{ fontSize: 12, color: PDS.text3, lineHeight: 1.65 }}>
            <span style={{ color: PDS.text2, fontWeight: 700 }}>Evidence · </span>{primary.evidence}
          </div>
        )}
        <div style={{ fontSize: 12, color: PDS.text3, lineHeight: 1.65 }}>
          <span style={{ color: PDS.text2, fontWeight: 700 }}>Confidence · </span>{confidenceLine}
        </div>
      </div>
      {/* Method — footnote treatment: fine print below its own rule. */}
      {primary && primary.derivation && (
        <div style={{ fontSize: 10, color: PDS.text3, opacity: 0.75, lineHeight: 1.6,
                      marginTop: PDS.s4, paddingTop: 10, borderTop: `1px solid ${PDS.hairline}` }}>
          <span style={{ fontWeight: 700 }}>Method · </span>{primary.derivation}
        </div>
      )}
    </Panel>
  );
}

/* Act V right — the artifact ledger. Only what exists renders; provenance
   and period live in Act I and never repeat here (no-duplication law). */
function EvidencePanel({ datasetHash, dqi, ac }) {
  const rows = [
    datasetHash && { k: 'Dataset SHA-256', v: `${String(datasetHash).slice(0, 18)}…`, mono: true, full: datasetHash },
    dqi.grade && { k: 'Data quality', v: `Grade ${dqi.grade}${dqi.value_pct != null ? ` · ${dqi.value_pct}%` : ''}`, c: gradeColor(dqi.grade) },
    dqi.version && { k: 'DQI methodology', v: dqi.version, mono: true },
    ac.grade && { k: 'Audit confidence', v: `${ac.grade}${ac.value_pct != null ? ` · ${ac.value_pct}%` : ''}`, c: gradeColor(ac.grade) },
    ac.version && { k: 'Confidence methodology', v: ac.version, mono: true },
    !datasetHash && { k: 'Input manifest', v: 'None — JSON audit input (no file manifest)' },
  ].filter(Boolean);
  return (
    <Panel pad={PDS.s5}>
      <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 12 }}>Evidence Chain</div>
      {rows.length === 0 ? (
        <div style={{ fontSize: 11, color: PDS.text3 }}>No additional artifacts on this audit path.</div>
      ) : rows.map((r, i) => (
        <div key={r.k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12,
                                padding: '9px 0',
                                borderBottom: i < rows.length - 1 ? `1px solid ${PDS.hairline}` : 'none' }}>
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
