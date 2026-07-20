// SPEC-MI atomic: PredictiveTimeline (MI-6, HONEST). Two REAL cumulative curves
// over the audited window: what was CAPTURED (Σ edv_actual_step) vs the OPTIMAL
// counterfactual (Σ edv_optimal_step). Drawn with stroke-dashoffset. MI-0: the
// "Future" segment is NOT a fabricated projection — the audit is evidence-only
// (recorded period), so it is marked, never drawn as data (see MOTION_DATA_MAP).
import React, { useMemo } from 'react';

export default function PredictiveTimeline({ log = [], currency = 'USD', width = 640, height = 220 }) {
  const { optPath, actPath, optEnd, actEnd, len } = useMemo(() => {
    const n = log.length;
    if (!n) return { optPath: '', actPath: '', optEnd: 0, actEnd: 0, len: 0 };
    let co = 0, ca = 0; const opt = [], act = [];
    for (const d of log) { co += (d.edv_optimal_step || 0); ca += (d.edv_actual_step || 0); opt.push(co); act.push(ca); }
    const maxY = Math.max(co, ca, 1), padL = 8, padR = 8, top = 16, bot = 40;
    const W = width - padL - padR, H = height - top - bot;
    const x = (i) => padL + (W * i) / (n - 1 || 1);
    const y = (v) => top + H - (H * v) / maxY;
    const toPath = (arr) => arr.map((v, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
    return { optPath: toPath(opt), actPath: toPath(act), optEnd: co, actEnd: ca, len: (n) };
  }, [log, width, height]);

  if (!log.length) return null;
  const money = (v) => `${v.toLocaleString('en-US', { maximumFractionDigits: 0 })} ${currency}`;
  const presentX = width - 16;

  return (
    <div style={{ background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '16px 20px 10px' }}>
      <style>{`@keyframes pdmDraw { to { stroke-dashoffset: 0; } }
        @media (prefers-reduced-motion: reduce){ .pdm-draw{ animation:none!important; stroke-dashoffset:0!important; } }`}</style>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img"
           aria-label="Captured vs optimal cumulative economic value">
        {/* Present marker + future (not projected) zone */}
        <line x1={presentX} y1="10" x2={presentX} y2={height - 34} stroke="var(--pds-border-strong,#2A384E)" strokeDasharray="3 4" />
        <text x={presentX - 6} y="20" textAnchor="end" style={{ fontSize: 9, fill: 'var(--pds-text-3,#7A89A3)', letterSpacing: '0.12em' }}>PRESENT</text>
        {/* Optimal counterfactual */}
        <path d={optPath} fill="none" stroke="var(--pds-warn, #F3B24C)" strokeWidth="2" strokeDasharray="4 4" opacity="0.85"
              className="pdm-draw" style={{ strokeDashoffset: 0 }} pathLength="1000" />
        {/* Captured (actual) */}
        <path d={actPath} fill="none" stroke="var(--pdm-optimal)" strokeWidth="2.5" strokeLinecap="round"
              className="pdm-draw" pathLength="1000"
              style={{ strokeDasharray: 1000, strokeDashoffset: 1000, animation: 'pdmDraw 1.6s ease-out forwards',
                       filter: 'drop-shadow(0 0 5px var(--pdm-optimal-glow))' }} />
        {/* labels */}
        <text x="12" y={height - 20} style={{ fontSize: 10, fill: 'var(--pdm-optimal)', fontWeight: 700 }} className="pdm-mono">
          CAPTURED {money(actEnd)}
        </text>
        <text x={width / 2} y={height - 20} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--pds-warn,#F3B24C)', fontWeight: 700 }} className="pdm-mono">
          OPTIMAL {money(optEnd)}
        </text>
        <text x={width - 12} y={height - 20} textAnchor="end" style={{ fontSize: 9.5, fill: 'var(--pds-text-3,#7A89A3)' }}>
          FUTURE — not projected (evidence-only audit)
        </text>
      </svg>
      <div style={{ fontSize: 10.5, color: 'var(--pds-text-3, #7A89A3)', marginTop: 4, lineHeight: 1.6 }}>
        Real cumulative curves over the audited window. The gap between them is the recorded economic
        leakage. No forward line is drawn — PREDAIOT reports evidence, not forecast.
      </div>
    </div>
  );
}
