// ============================================================================
// PREDAIOT — Economic Action Plan (S09). Answers Q4: what should we do, and
// what is it worth? Rebuilt in the briefing voice (PL-1.0, SPEC-ST, SPEC-AI):
// money-first standfirst, a ranked exhibit of governed recommendations, each
// with recorded-period value + evidence + method footnote. Experimental
// actions are quarantined. Recorded period only — no forward projection.
// Consumes ONLY the existing audit response.
// ============================================================================
import React from 'react';
import { PDS, opportunityColor, fmtMoney, fmtPct } from '../design/ds';
import { Panel, SectionShell, StatusDot } from '../design/components';

const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));

export default function ActionPlan({ data }) {
  const currency = data.currency || 'USD';
  const ops = (data.opportunities || []).slice();
  const quantified = ops.filter((o) => !o.experimental && num(o.period_gain) != null)
    .sort((a, b) => (num(b.period_gain) ?? 0) - (num(a.period_gain) ?? 0));
  const experimental = ops.filter((o) => o.experimental);
  // Recorded-period value attributed across quantified actions (excludes the
  // cross-cutting governance item, which is not a summable recovery).
  const attributed = quantified
    .filter((o) => o.name !== 'Operator override governance')
    .reduce((s, o) => s + (num(o.period_gain) || 0), 0);

  if (ops.length === 0) {
    return (
      <SectionShell kicker="Economic Action Plan" title="Value Recovery Roadmap"
        question="What should we do — and what is it worth?">
        <div style={{ fontSize: 14, color: PDS.text2 }}>
          Run an audit to generate the Economic Action Plan — recovery actions are
          derived from the audited decision ledger.
        </div>
      </SectionShell>
    );
  }

  const lead = (
    <>
      This audit attributes{' '}
      <span className="pds-num" style={{ color: PDS.recover, fontWeight: 800 }}>
        {fmtMoney(attributed, currency)}
      </span>{' '}
      of recorded recoverable value across{' '}
      <span style={{ color: PDS.text, fontWeight: 700 }}>{quantified.length}</span>{' '}
      governed action{quantified.length === 1 ? '' : 's'}, ranked by recorded
      economic impact. Basis: recorded period only — no forward projection.
    </>
  );

  return (
    <SectionShell kicker="Economic Action Plan" title="Value Recovery Roadmap"
      question="What should we do — and what is it worth?" lead={lead}
      action={experimental.length > 0
        ? `${experimental.length} experimental action${experimental.length === 1 ? '' : 's'} are shown for exploration only — not part of EDA Standard v1.0 and not quantified.`
        : undefined}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--ws-card-gap)' }}>
        {quantified.map((op, i) => (
          <Recommendation key={op.name} op={op} rank={i + 1} currency={currency} lead={i === 0} />
        ))}
        {experimental.length > 0 && (
          <>
            <div className="pds-kicker" style={{ marginTop: PDS.s3 }}>Experimental — not quantified</div>
            {experimental.map((op) => (
              <Recommendation key={op.name} op={op} currency={currency} experimental />
            ))}
          </>
        )}
      </div>
    </SectionShell>
  );
}

/* One governed recommendation. The lead (rank 1) carries the accent top-rule;
   followers are quieter — the eye lands on the primary action first. */
function Recommendation({ op, rank, currency, lead, experimental }) {
  const gain = num(op.period_gain);
  const c = opportunityColor(!!experimental);
  return (
    <Panel pad={PDS.s5} accent={!!lead}
           style={experimental ? { opacity: 0.9 } : undefined}>
      <div style={{ display: 'flex', gap: PDS.s5, flexWrap: 'wrap' }}>
        <div style={{ flex: 2, minWidth: 280 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
            {rank != null && (
              <span className="pds-num" style={{ fontSize: 13, fontWeight: 800,
                color: lead ? PDS.accent : PDS.text3 }}>{String(rank).padStart(2, '0')}</span>
            )}
            <span style={{ fontSize: lead ? 18 : 16, fontWeight: 800, color: PDS.text, letterSpacing: '-0.01em' }}>
              {op.name}
            </span>
            {experimental && (
              <span className="pds-num" style={{ fontSize: 9, letterSpacing: '0.1em', color: PDS.text3,
                border: `1px solid ${PDS.border}`, borderRadius: PDS.rPill, padding: '2px 8px' }}>
                EXPERIMENTAL
              </span>
            )}
          </div>
          {op.description && (
            <div style={{ fontSize: 13, color: PDS.text2, lineHeight: 1.65, maxWidth: 'var(--pds-prose-max)' }}>
              {op.description}
            </div>
          )}
          {/* Meta — recorded evidence counts only. */}
          {!experimental && (op.intervals_observed != null || op.share_of_positive_gap_pct != null) && (
            <div style={{ display: 'flex', gap: PDS.s5, marginTop: 12, flexWrap: 'wrap', fontSize: 11, color: PDS.text3 }}>
              {op.intervals_observed != null && (
                <span><span className="pds-num" style={{ color: PDS.text2, fontWeight: 700 }}>{op.intervals_observed}</span> ledger intervals</span>
              )}
              {op.share_of_positive_gap_pct != null && (
                <span><span className="pds-num" style={{ color: PDS.text2, fontWeight: 700 }}>{fmtPct(op.share_of_positive_gap_pct, 0)}</span> of positive gap</span>
              )}
            </div>
          )}
          {op.evidence && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 10, lineHeight: 1.55, maxWidth: 'var(--pds-prose-max)' }}>
              <span style={{ color: PDS.text2, fontWeight: 700 }}>Evidence · </span>{op.evidence}
            </div>
          )}
          {op.experimental_note && (
            <div style={{ fontSize: 11, color: PDS.text3, marginTop: 8, lineHeight: 1.55 }}>{op.experimental_note}</div>
          )}
          {op.derivation && (
            <div style={{ fontSize: 10, color: PDS.text3, opacity: 0.75, marginTop: 10, paddingTop: 8,
                          borderTop: `1px solid ${PDS.hairline}`, lineHeight: 1.55, maxWidth: 'var(--pds-prose-max)' }}>
              <span style={{ fontWeight: 700 }}>Method · </span>{op.derivation}
            </div>
          )}
        </div>
        {/* Value at stake — recorded period only. */}
        {gain != null && (
          <div style={{ textAlign: 'right', minWidth: 160, flex: 1 }}>
            <div className="pds-kicker" style={{ marginBottom: 8 }}>Value at Stake</div>
            <div className="pds-num" style={{ fontSize: 28, fontWeight: 800, color: PDS.recover, lineHeight: 1 }}>
              {fmtMoney(Math.abs(gain), currency)}
            </div>
            <div style={{ fontSize: 10, color: PDS.text3, marginTop: 8 }}>recorded this period — no forward projection</div>
          </div>
        )}
        {experimental && (
          <div style={{ textAlign: 'right', minWidth: 120, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
            <StatusDot color={c} size={6} />
            <span style={{ fontSize: 11, color: PDS.text3 }}>no recorded gain</span>
          </div>
        )}
      </div>
    </Panel>
  );
}
