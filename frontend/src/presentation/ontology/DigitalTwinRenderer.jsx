// ============================================================================
// PREDAIOT — Ontology Digital-Twin Renderer (Phase 5)
// Draws WHATEVER node chain `facility_profile.topology` contains. No hardcoded
// GRID→BESS→LOAD. Storage, steel, cement, solar, hydro all render from the same
// code — only the ontology (backend) differs. Adding an industry = pack change.
// ============================================================================
import React from 'react';
import { MC } from '../../design/ds';

const KIND_COLOR = {
  source: 'var(--pds-info, #5AA9FF)',
  equipment: 'var(--pds-accent, #34E0C8)',
  sink: 'var(--pds-text-2, #97A6BC)',
  node: 'var(--pds-text-2, #97A6BC)',
};

export default function DigitalTwinRenderer({ topology = [], hasLeak = false, caption }) {
  if (!topology.length) return null;
  const n = topology.length;
  const W = 640, H = 150, top = 60;
  const slot = W / n;
  const nodes = topology.map((nd, i) => ({ ...nd, x: slot * i + slot / 2, y: top }));
  const leakEdge = hasLeak ? n - 2 : -1; // last edge carries the economic leak

  return (
    <div style={{ background: MC.void, border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '14px 12px 10px' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="auto" role="img"
           aria-label={`Facility topology: ${topology.map((t) => t.label).join(' to ')}`}>
        {/* edges (animated flow between consecutive nodes) */}
        {nodes.slice(0, -1).map((a, i) => {
          const b = nodes[i + 1];
          const leaking = i === leakEdge;
          return (
            <g key={`e${i}`}>
              <line x1={a.x + 28} y1={a.y} x2={b.x - 28} y2={b.y}
                    stroke="var(--pds-border, #1B2536)" strokeWidth="1.5" />
              <line x1={a.x + 28} y1={a.y} x2={b.x - 28} y2={b.y} strokeWidth="2.5" strokeLinecap="round"
                    className={leaking ? 'pdm-flow-slow' : 'pdm-flow-fast'}
                    stroke={leaking ? 'var(--pdm-leak)' : 'var(--pdm-optimal)'}
                    style={{ filter: `drop-shadow(0 0 6px ${leaking ? 'var(--pdm-leak-glow)' : 'var(--pdm-optimal-glow)'})` }} />
            </g>
          );
        })}
        {/* nodes */}
        {nodes.map((nd) => (
          <g key={nd.id}>
            <circle cx={nd.x} cy={nd.y} r="24" fill="var(--pdm-panel)"
                    stroke={KIND_COLOR[nd.kind] || KIND_COLOR.node} strokeWidth="1.5" />
            <text x={nd.x} y={nd.y + 44} textAnchor="middle" className="mission-num"
                  style={{ fontSize: 10.5, fill: 'var(--pds-text, #EAF1F8)', fontWeight: 700 }}>
              {nd.label}
            </text>
            <text x={nd.x} y={nd.y + 4} textAnchor="middle" className="mission-num"
                  style={{ fontSize: 8, letterSpacing: '0.12em', fill: 'var(--pds-text-3, #7A89A3)' }}>
              {(nd.kind || '').toUpperCase()}
            </text>
          </g>
        ))}
      </svg>
      {caption && (
        <div className="mission-num" style={{ fontSize: 10, textAlign: 'center', paddingTop: 4,
                        color: hasLeak ? 'var(--pdm-leak)' : 'var(--pdm-optimal)', letterSpacing: '0.12em' }}>
          {caption}
        </div>
      )}
    </div>
  );
}
