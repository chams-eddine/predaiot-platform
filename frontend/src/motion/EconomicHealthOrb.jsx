// SPEC-MI atomic: EconomicHealthOrb (MI-5, HONEST repurpose).
// The requested "asset health orb" (battery SoH / PCS / thermal) has NO backing
// data — PREDAIOT audits ECONOMIC decision quality, not hardware telemetry
// (see MOTION_DATA_MAP.md). Fabricating physical-health scores would violate
// MI-0, so this orb renders THREE REAL economic-health rings instead:
//   Data Quality (data_quality_index.value) · Audit Confidence
//   (audit_confidence.value) · Economic Efficiency
//   (eda_metrics.economic_decision_efficiency).
// CSS transforms + SVG only. No Three.js.
import React from 'react';

const RINGS = [
  { key: 'dq',   label: 'DATA QUALITY',        color: 'var(--pds-accent, #34E0C8)', r: 78, spin: 26 },
  { key: 'conf', label: 'AUDIT CONFIDENCE',    color: 'var(--pds-info, #5AA9FF)',   r: 60, spin: 18 },
  { key: 'eff',  label: 'ECONOMIC EFFICIENCY', color: 'var(--pdm-optimal)',         r: 42, spin: 12 },
];

const Ring = ({ r, color, pct, spin, reduced }) => {
  const C = 2 * Math.PI * r;
  const on = C * Math.max(0, Math.min(1, pct));
  return (
    <g style={reduced ? undefined : { transformOrigin: '100px 100px', animation: `pdmSpin ${spin}s linear infinite` }}>
      <circle cx="100" cy="100" r={r} fill="none" stroke="var(--pds-border, #1B2536)" strokeWidth="6" />
      <circle cx="100" cy="100" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${on} ${C - on}`} transform={`rotate(-90 100 100)`}
              style={{ opacity: 0.4 + 0.6 * Math.max(0, Math.min(1, pct)),   // ring opacity = health
                       filter: `drop-shadow(0 0 6px ${color})` }} />
    </g>
  );
};

export default function EconomicHealthOrb({ dq, confidence, efficiency, overall, size = 220 }) {
  const reduced = typeof window !== 'undefined'
    && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const vals = { dq: dq ?? 0, conf: confidence ?? 0, eff: efficiency ?? 0 };
  const center = overall != null ? Math.round(overall) : Math.round(((vals.dq + vals.conf + vals.eff) / 3) * 100) / 1;
  const centerColor = center >= 85 ? 'var(--pdm-optimal)' : center >= 60 ? 'var(--pds-warn, #F3B24C)' : 'var(--pdm-leak)';
  return (
    <div style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
      <style>{`@keyframes pdmSpin { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) { .pdm-orb g { animation: none !important; } }`}</style>
      <svg className="pdm-orb" width={size} height={size} viewBox="0 0 200 200" role="img"
           aria-label={`Economic health ${center} of 100`}>
        <defs>
          <radialGradient id="pdmOrbCore" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={centerColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={centerColor} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="100" cy="100" r="34" fill="url(#pdmOrbCore)" />
        <Ring r={78} color={RINGS[0].color} pct={vals.dq} spin={26} reduced={reduced} />
        <Ring r={60} color={RINGS[1].color} pct={vals.conf} spin={18} reduced={reduced} />
        <Ring r={42} color={RINGS[2].color} pct={vals.eff} spin={12} reduced={reduced} />
        <text x="100" y="98" textAnchor="middle" className="pdm-mono"
              style={{ fontSize: 34, fontWeight: 800, fill: centerColor }}>{center}</text>
        <text x="100" y="118" textAnchor="middle"
              style={{ fontSize: 9, letterSpacing: '0.18em', fill: 'var(--pds-text-3, #7A89A3)', fontWeight: 700 }}>
          ECON HEALTH
        </text>
      </svg>
      <div>
        {RINGS.map((ring) => (
          <div key={ring.key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: ring.color,
                           boxShadow: `0 0 8px ${ring.color}` }} />
            <span style={{ fontSize: 11, letterSpacing: '0.12em', color: 'var(--pds-text-2, #97A6BC)',
                           fontWeight: 600, minWidth: 168 }}>{ring.label}</span>
            <span className="pdm-mono" style={{ fontSize: 14, fontWeight: 700, color: ring.color }}>
              {Math.round((ring.key === 'dq' ? vals.dq : ring.key === 'conf' ? vals.conf : vals.eff) * 100)}
            </span>
          </div>
        ))}
        <div style={{ fontSize: 10.5, color: 'var(--pds-text-3, #7A89A3)', marginTop: 6, maxWidth: 240, lineHeight: 1.6 }}>
          Economic-decision health — not physical asset telemetry. Rings: DQI · Audit Confidence ·
          Economic Efficiency, all from the audit response.
        </div>
      </div>
    </div>
  );
}
