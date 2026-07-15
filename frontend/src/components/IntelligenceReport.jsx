// ============================================================================
// PREDAIOT — Economic Intelligence Report (S10). Answers Q5/Q6: why is this
// happening, and can we prove it? Rebuilt in the briefing voice (PL-1.0,
// SPEC-ST, SPEC-AI): money-first standfirst, a compact assessment header,
// and the report as an editorial document with a real evidence chain.
// Evidence is recorded artifacts only (fabricated constants already removed).
// Consumes ONLY the existing audit response + the engine's report text.
// ============================================================================
import React from 'react';
import { PDS, riskColor, gradeColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, SectionShell, StatusDot, EvidenceBadge } from '../design/components';

const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));

export default function IntelligenceReport({ data, m, captureRate, aiText, aiLoading, onGenerate, onReset }) {
  const currency = data.currency || 'USD';
  const report = aiText || data.ai_commentary;
  const recoverable = num((data.gap_attribution || {}).execution_gap) ?? num(data.recoverable_execution_gap);
  const datasetHash = (data.audit_manifest || {}).input_sha256
    || (data.data_quality_manifest || {}).dataset_sha256 || null;

  // Compact assessment facts — recorded values only, no equal-weight card grid.
  const facts = [
    { l: 'Risk band', v: (data.risk_level || '—'), c: riskColor(data.risk_level), strong: true },
    { l: 'Ceiling capture', v: fmtPct(captureRate), c: PDS.text2 },
    recoverable != null && { l: 'Recoverable execution gap', v: fmtMoney(Math.abs(recoverable), currency), c: PDS.recover },
    m && m.dispatch_accuracy != null && { l: 'Dispatch accuracy', v: `${m.dispatch_accuracy.toFixed(1)}%`, c: PDS.text2 },
    m && m.forecast_utilization_index != null && { l: 'Forecast coverage', v: `${m.forecast_utilization_index.toFixed(0)}%`, c: PDS.text2 },
  ].filter(Boolean);

  const lead = (
    <>
      An independent assessment of this asset's economic decisions, validated against the
      mathematically optimal dispatch. The audit operated at{' '}
      <span style={{ color: riskColor(data.risk_level), fontWeight: 700 }}>{fmtPct(captureRate)}</span>{' '}
      of the economic optimum
      {recoverable != null && <> — <span className="pds-num" style={{ color: PDS.recover, fontWeight: 700 }}>{fmtMoney(Math.abs(recoverable), currency)}</span> of it recoverable</>}.
    </>
  );

  return (
    <SectionShell kicker="Economic Intelligence Report" title="Independent Assessment"
      question="Why is this happening — and can we prove it?" lead={lead}
      right={data.risk_level && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700,
                       color: riskColor(data.risk_level) }}>
          <StatusDot color={riskColor(data.risk_level)} size={8} /> {data.risk_level} risk
        </span>
      )}>
      {/* Assessment facts — one quiet line, not a widget grid. */}
      <div style={{ display: 'flex', gap: PDS.s6, rowGap: PDS.s3, flexWrap: 'wrap', marginBottom: PDS.s5 }}>
        {facts.map((f) => (
          <div key={f.l}>
            <div className="pds-kicker" style={{ marginBottom: 4 }}>{f.l}</div>
            <div className="pds-num" style={{ fontSize: f.strong ? 18 : 16, fontWeight: 800, color: f.c }}>{f.v}</div>
          </div>
        ))}
      </div>

      {/* The action + the report document. */}
      <div style={{ display: 'flex', gap: 10, marginBottom: PDS.s5, flexWrap: 'wrap' }}>
        <button onClick={onGenerate} disabled={aiLoading} className="pds-report-btn"
          style={{ padding: '9px 18px', background: 'transparent', color: aiLoading ? PDS.text3 : PDS.accent,
                   border: `1px solid ${aiLoading ? PDS.border : PDS.accent}`, borderRadius: PDS.rSm,
                   cursor: aiLoading ? 'wait' : 'pointer', fontSize: 11, letterSpacing: '0.1em', fontWeight: 700 }}>
          {aiLoading ? 'GENERATING…' : (report ? 'REGENERATE ASSESSMENT' : 'GENERATE DEEP ASSESSMENT')}
        </button>
        {report && aiText && (
          <button onClick={onReset}
            style={{ padding: '9px 18px', background: 'transparent', color: PDS.text3,
                     border: `1px solid ${PDS.border}`, borderRadius: PDS.rSm, cursor: 'pointer',
                     fontSize: 11, letterSpacing: '0.1em', fontWeight: 700 }}>
            RESET
          </button>
        )}
      </div>

      {report ? (
        <Panel pad="clamp(24px, 2.6vw, 40px)" accent>
          {/* Document masthead */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                        gap: 16, flexWrap: 'wrap', paddingBottom: PDS.s4, marginBottom: PDS.s5,
                        borderBottom: `1px solid ${PDS.hairline}` }}>
            <div>
              <div className="pds-kicker" style={{ color: PDS.accent }}>PREDAIOT Economic Intelligence Report</div>
              <div style={{ fontSize: 12, color: PDS.text3, marginTop: 4 }}>Independent economic decision assessment · {data.audit_period_label || 'audited period'}</div>
            </div>
            <EvidenceBadge provisional={false} hash={datasetHash} status="CERTIFIED" />
          </div>

          {/* Evidence chain — recorded artifacts only. */}
          <div style={{ display: 'flex', gap: PDS.s6, rowGap: PDS.s3, flexWrap: 'wrap', marginBottom: PDS.s5 }}>
            {[
              { l: 'Dispatch records analysed', v: (data.decision_log || []).length },
              m && m.forecast_utilization_index != null && { l: 'Forecast availability', v: `${m.forecast_utilization_index.toFixed(0)}%` },
              data.data_quality_index?.grade && { l: 'Data quality', v: `Grade ${data.data_quality_index.grade}`, c: gradeColor(data.data_quality_index.grade) },
              data.audit_confidence?.grade && data.audit_confidence.grade !== 'INDETERMINATE'
                && { l: 'Audit confidence', v: `Grade ${data.audit_confidence.grade}`, c: gradeColor(data.audit_confidence.grade) },
            ].filter(Boolean).map((e) => (
              <div key={e.l}>
                <div className="pds-kicker" style={{ marginBottom: 4 }}>{e.l}</div>
                <div className="pds-num" style={{ fontSize: 12, fontWeight: 700, color: e.c || PDS.text2 }}>{e.v}</div>
              </div>
            ))}
          </div>

          {/* The assessment — editorial prose, not a monospace dump. */}
          <div style={{ color: PDS.text, fontSize: 14, lineHeight: 1.8, fontFamily: PDS.sans,
                        whiteSpace: 'pre-wrap', maxWidth: 'var(--pds-prose-max)' }}>
            {report}
          </div>

          <div style={{ marginTop: PDS.s5, paddingTop: PDS.s4, borderTop: `1px solid ${PDS.hairline}`,
                        display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap',
                        fontSize: 10, color: PDS.text3 }}>
            <span style={{ maxWidth: 'var(--pds-prose-max)' }}>
              Generated with the PREDAIOT Economic Decision Audit™ methodology, validated against the
              mathematically optimal dispatch solution.
            </span>
            <span style={{ flexShrink: 0 }}>{aiText ? 'Enhanced analysis' : 'PREDAIOT engine'}</span>
          </div>
        </Panel>
      ) : (
        <div style={{ fontSize: 14, color: PDS.text2, maxWidth: 'var(--pds-prose-max)' }}>
          Generate the deep assessment to read the independent economic decision report — its
          findings, root-cause analysis, and recommended actions, all traced to the audited ledger.
        </div>
      )}
    </SectionShell>
  );
}
