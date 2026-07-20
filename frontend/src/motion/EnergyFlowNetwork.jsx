// SPEC-MI atomic: EnergyFlowNetwork ("Digital Twin Pulse") — pure SVG energy
// topology GRID ↔ BESS ↔ LOAD with continuously moving stroke-dash flows.
// MI-0: `hasLeak` and `leakEdge` must come from real audit facts (e.g.
// risk_level, gap_step distribution) — the component renders state, never
// decides it. Optimal = green + fast; leak edge = red + slow + pulsing dot.
import React from 'react';

const NODE = { r: 26, fill: 'var(--pdm-panel)', stroke: 'var(--pds-border-strong, #2A384E)' };
const LABEL = { fontSize: 10, letterSpacing: '0.18em', fontWeight: 700, fill: 'var(--pds-text-2, #97A6BC)' };

const Edge = ({ d, leaking }) => (
  <g>
    <path d={d} fill="none" stroke="var(--pds-border, #1B2536)" strokeWidth="1.5" />
    <path d={d} fill="none" strokeWidth="2.5" strokeLinecap="round"
          className={leaking ? 'pdm-flow-slow' : 'pdm-flow-fast'}
          stroke={leaking ? 'var(--pdm-leak)' : 'var(--pdm-optimal)'}
          style={{ filter: `drop-shadow(0 0 6px ${leaking ? 'var(--pdm-leak-glow)' : 'var(--pdm-optimal-glow)'})` }} />
  </g>
);

const Node = ({ x, y, label }) => (
  <g>
    <circle cx={x} cy={y} r={NODE.r} fill={NODE.fill} stroke={NODE.stroke} strokeWidth="1.5" />
    <text x={x} y={y + 4} textAnchor="middle" style={LABEL} className="pdm-mono">{label}</text>
  </g>
);

export default function EnergyFlowNetwork({ hasLeak = false, leakEdge = 'bess-load',
                                            width = 520, height = 150, caption }) {
  const leakOn = (edge) => hasLeak && leakEdge === edge;
  // midpoint of the leaking edge for the pulse indicator
  const mid = leakEdge === 'grid-bess' ? { x: 175, y: 62 } : { x: 345, y: 62 };
  return (
    <div style={{ background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '14px 18px 8px' }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="auto" role="img"
           aria-label={hasLeak ? 'Energy network with an active economic leak' : 'Energy network at optimal flow'}>
        <Edge d="M 96 75 C 150 40, 200 40, 234 75" leaking={leakOn('grid-bess')} />
        <Edge d="M 286 75 C 330 40, 380 40, 424 75" leaking={leakOn('bess-load')} />
        <Node x={70} y={75} label="GRID" />
        <Node x={260} y={75} label="BESS" />
        <Node x={450} y={75} label="LOAD" />
        {hasLeak && (
          <circle cx={mid.x} cy={mid.y} r="4" fill="var(--pdm-leak)" className="pdm-leak-dot"
                  style={{ filter: 'drop-shadow(0 0 8px var(--pdm-leak-glow))' }} />
        )}
      </svg>
      {caption && (
        <div className="pdm-mono" style={{ fontSize: 10, color: hasLeak ? 'var(--pdm-leak)' : 'var(--pdm-optimal)',
                        letterSpacing: '0.12em', textAlign: 'center', paddingBottom: 6 }}>
          {caption}
        </div>
      )}
    </div>
  );
}
