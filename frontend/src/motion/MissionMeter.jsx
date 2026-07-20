// SPEC-MI atomic: MissionMeter — the "value grows like ████" bar language.
// The one primitive the library lacked: a segmented economic meter whose FILL
// is a real ratio (value / max), the number rolls, and color carries economic
// meaning (optimal / leak / warning / verified). Motion is causal (SPEC-MI §6):
// segments light left→right with a per-segment delay so the value visibly grows,
// and the glow intensifies with fill. Pure presentational — the caller passes
// real backend numbers; this fabricates nothing (MI-0). Reduced-motion safe.
import React from 'react';
import { MC } from '../design/ds';
import { AnimatedNumber } from '../design/components';

const TONE = { optimal: MC.optimal, leak: MC.leak, warning: MC.warning, verified: MC.verified };

export default function MissionMeter({
  value, max, label, sublabel, currency = '', tone = 'optimal',
  decimals = 0, segments = 28, height = 12, prefix = '', showPct = true,
}) {
  const color = TONE[tone] || MC.optimal;
  const v = Number(value);
  const m = Number(max);
  const ratio = m > 0 && Number.isFinite(v) ? Math.max(0, Math.min(1, v / m)) : 0;
  const filled = Math.round(ratio * segments);
  const reduced = typeof window !== 'undefined' && window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
                       color: 'var(--pds-text-3)', fontWeight: 700 }}>{label}</span>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span className="pdm-mono" style={{ fontSize: 20, fontWeight: 800, color, letterSpacing: '-0.01em',
                                              textShadow: `0 0 22px ${color}55` }}>
            {prefix}<AnimatedNumber value={v} decimals={decimals} />
          </span>
          {currency && <span style={{ fontSize: 11, color: 'var(--pds-text-2)', fontWeight: 600 }}>{currency}</span>}
        </span>
      </div>

      {/* Segmented track — filled cells = real ratio; each lights with a stagger. */}
      <div role="meter" aria-valuenow={Math.round(ratio * 100)} aria-valuemin={0} aria-valuemax={100}
           aria-label={label}
           style={{ display: 'flex', gap: 3, alignItems: 'stretch' }}>
        {Array.from({ length: segments }).map((_, i) => {
          const on = i < filled;
          return (
            <span key={i} style={{
              flex: 1, height, borderRadius: 2,
              background: on ? color : 'var(--pds-border)',
              boxShadow: on ? `0 0 8px ${color}` : 'none',
              opacity: on ? 1 : 0.45,
              transition: reduced ? 'none'
                : `background 420ms ${i * 16}ms ease-out, opacity 420ms ${i * 16}ms ease-out, box-shadow 420ms ${i * 16}ms ease-out`,
            }} />
          );
        })}
      </div>

      {(sublabel || showPct) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12,
                      fontSize: 10.5, color: 'var(--pds-text-3)', lineHeight: 1.5 }}>
          <span>{sublabel}</span>
          {showPct && <span className="pdm-mono" style={{ color }}>{(ratio * 100).toFixed(1)}%</span>}
        </div>
      )}
    </div>
  );
}
