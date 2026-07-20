// SPEC-MI atomic: DecisionEngine (MI-2) — the audited decisions STREAM in, one
// dot per REAL ledger row, colored by the row's actual verdict (gap_step), and
// converge to a verdict line with REAL counts. MI-0: nothing synthetic — the
// dot count, colors, order and totals all come from decision_log[]. The MILP
// genuinely computed the optimal counterfactual for every interval; the closing
// line states exactly that. Pure UI.
import React from 'react';
import { useReducedMotion } from 'framer-motion';

const PER_DOT_MS = 6;      // stream cadence
const DOT_IN_MS = 260;     // single dot entrance

export default function DecisionEngine({ log = [], currency = 'USD' }) {
  const reduced = useReducedMotion();
  const n = log.length;
  const leaked = log.filter((d) => (d.gap_step || 0) > 0).length;
  const streamMs = n * PER_DOT_MS + DOT_IN_MS;
  if (n === 0) return null;
  return (
    <div style={{ background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '18px 20px 14px' }}>
      <style>{`
        @keyframes pdmDot { from { opacity: 0; transform: scale(0.2); } to { opacity: 1; transform: scale(1); } }
        @keyframes pdmVerdict { from { opacity: 0; } to { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) {
          .pdm-dot, .pdm-verdict { animation: none !important; opacity: 1 !important; transform: none !important; }
        }
      `}</style>
      <div style={{ fontSize: 10, letterSpacing: '0.2em', textTransform: 'uppercase',
                    color: 'var(--pds-text-3, #7A89A3)', fontWeight: 700, marginBottom: 12 }}>
        DECISION ENGINE · {n} intervals streamed through the certified optimizer
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(48, 1fr)', gap: 3, marginBottom: 14 }}>
        {log.map((d, i) => {
          const leak = (d.gap_step || 0) > 0;
          return (
            <div key={i} className="pdm-dot" title={`step ${d.hour ?? i} · gap ${d.gap_step}`}
                 style={{ aspectRatio: '1', borderRadius: '50%',
                          background: leak ? 'var(--pdm-leak)' : 'var(--pdm-optimal)',
                          opacity: 0,
                          boxShadow: leak ? '0 0 4px var(--pdm-leak-glow)' : 'none',
                          animation: reduced ? 'none' : `pdmDot ${DOT_IN_MS}ms ease-out both`,
                          animationDelay: reduced ? '0ms' : `${i * PER_DOT_MS}ms`,
                          ...(reduced ? { opacity: 1 } : {}) }} />
          );
        })}
      </div>
      <div className="pdm-verdict pdm-mono"
           style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
                    fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', opacity: 0,
                    animation: reduced ? 'none' : `pdmVerdict 500ms ease-out both`,
                    animationDelay: reduced ? '0ms' : `${streamMs}ms`,
                    ...(reduced ? { opacity: 1 } : {}) }}>
        <span style={{ color: 'var(--pdm-optimal)' }}>
          OPTIMAL DISPATCH FOUND — {n}/{n} INTERVALS BENCHMARKED
        </span>
        <span style={{ color: leaked > 0 ? 'var(--pdm-leak)' : 'var(--pdm-optimal)' }}>
          {leaked} LEAKED · {n - leaked} AT OPTIMUM
        </span>
      </div>
    </div>
  );
}
