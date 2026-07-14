// ============================================================================
// PREDAIOT — Executive Command Center (SPEC-EX, the reference dashboard).
// Answers Q1–Q4 in under five seconds, without scroll at T2 (1440×900):
//   Q1 How much are we losing?      → Financial Leakage   (money lost)
//   Q2 How much can we recover?     → Recoverable Value   (money recoverable)
//   Q3 How healthy are decisions?   → Decision Health     (ECF + risk band)
//   Q4 What should we do next?      → PREDAIOT Recommendation (SPEC-AI block)
// T3+ adds Z5 Reasoning (65%) + Z6 Evidence (35%) per the WS matrix.
// Consumes ONLY the existing audit response. Absent data renders as absent —
// never fabricated (SPEC-TR; FM-1/FM-3). Annualized figures are banned from
// display (SPEC-AI rule 5) even where the API provides them.
// ============================================================================
import React from 'react';
import { PDS, gradeColor, riskColor, opportunityColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, KpiCard, GradeBadge, EvidenceBadge, StatusDot } from '../design/components';
import { Zone } from '../workspace/Workspace';
import { useWorkspaceTier, tierAtLeast } from '../workspace/tier';

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
  // Audit-confidence grade only exists on the file-upload path (rich DQI) —
  // shown when present, never fabricated when absent (SPEC-QA Q3 acceptance).
  const acGrade = (ac.grade && ac.grade !== 'INDETERMINATE') ? ac.grade : null;
  const acPct = num(ac.value_pct);
  const dqiPct = num(dqi.value_pct);

  // Decision health — the Economic Capture Fraction (dq_score = captured ÷
  // optimal, Reference Manual Ch 6.1). Always present on every audit.
  const ecf = num(data.dq_score);
  const ecfPct = ecf != null ? Math.max(0, Math.min(100, ecf * 100)) : null;

  // Q4 — recommendations. Primary = top non-experimental recorded gain;
  // experimental entries are quarantined (SPEC-AI rule 2). Alternatives are
  // ALWAYS visible where a primary renders (rule 3) — including those with
  // no recorded gain, which display honest absence, never a number (FM-3).
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

  return (
    <div className="pds-rise" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--ws-card-gap)' }}>
      {/* ── Z1 · Command header ────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
                    flexWrap: 'wrap', gap: PDS.s4 }}>
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
        <EvidenceBadge provisional={isLive} hash={datasetHash}
          status={isLive ? 'PROVISIONAL' : 'CERTIFIED'} />
      </div>

      {/* ── Z2 · The three money answers (Q1/Q2/Q3) ────────────────── */}
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

      {/* ── Z3 · Q4: the PREDAIOT Recommendation (SPEC-AI anatomy) ──── */}
      <RecommendationBlock primary={primary} alternatives={alternatives}
        currency={currency} acGrade={acGrade} acPct={acPct} dqiPct={dqiPct}
        fallbackRc={rcs[0]} />

      {/* ── Z5 + Z6 · T3+: Reasoning (65%) + Evidence (35%) ─────────── */}
      {tierAtLeast(tier, 'T3') && (
        <Zone row="primary">
          <ReasoningPanel rcs={rcs} leakage={leakage} currency={currency} />
          <EvidencePanel isLive={isLive} datasetHash={datasetHash}
            dqi={dqi} ac={ac} data={data} />
        </Zone>
      )}
    </div>
  );
}

/* ── Q3 card: circular gauge on the ECF, colored by the backend risk band. */
function DecisionHealthCard({ ecfPct, riskLevel, acGrade, acPct, dqiPct }) {
  const c = riskColor(riskLevel);
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

/* ── Q4: the PREDAIOT Recommendation Block — minimum lawful anatomy per
   SPEC-AI rule 1: Designation + Reasoning + Evidence + Confidence +
   Economic Impact (+ Alternatives). A bare recommendation never renders.
   Annualized gains are never displayed (SPEC-AI rule 5). */
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
        {/* Designation + Reasoning */}
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
          {/* Evidence — recorded ledger basis, verbatim from the engine. */}
          {p.evidence && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 10, lineHeight: 1.55,
                          maxWidth: 'var(--pds-prose-max)' }}>
              <span style={{ color: PDS.text2, fontWeight: 700 }}>Evidence · </span>{p.evidence}
            </div>
          )}
          {/* Confidence + assumptions */}
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
        {/* Economic impact — recorded basis only. */}
        <div style={{ textAlign: 'right', minWidth: 180, flex: 1 }}>
          <div className="pds-kicker" style={{ marginBottom: 8 }}>Value at Stake</div>
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
      {/* Alternatives — visible wherever a primary renders (SPEC-AI rule 3). */}
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

/* ── Z5 (T3+): why value leaked — recorded root-cause attribution. */
function ReasoningPanel({ rcs, leakage, currency }) {
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
            <div style={{ width: `${Math.min(100, rc.contribution_pct || 0)}%`, height: '100%',
                          background: PDS.loss, borderRadius: 2, opacity: 0.8,
                          transition: 'width var(--pds-dur-slow) var(--pds-ease)' }} />
          </div>
        </div>
      ))}
    </Panel>
  );
}

/* ── Z6 (T3+): evidence — only artifacts that actually exist render. */
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
