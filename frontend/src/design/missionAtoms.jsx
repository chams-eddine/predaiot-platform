// ============================================================================
// MISSION ATOMS (Phase 3.5) — the primitives the library lacked.
// Built on the Mission token language (3.2) + Typography DNA (3.3). Pure
// presentational; consume real values only (MI-0). Everything else the user
// listed (Panel/Card/Badge/Counter/Section/Divider/Status) already exists and is
// re-exported from design/mission.js — these are the two that did not.
// ============================================================================
import React from 'react';
import { MC } from './ds';

const TONES = {
  optimal:  MC.optimal, leak: MC.leak, warning: MC.warning, verified: MC.verified,
  neutral: 'var(--mission-text)', accent: 'var(--mission-accent)', dim: 'var(--mission-text-dim)',
};
const toneColor = (t) => TONES[t] || t || 'var(--mission-text)';

/* MissionLabel — the small uppercase kicker voice. One label atom, everywhere. */
export function MissionLabel({ children, color, style }) {
  return (
    <span className="mission-kicker" style={{ color: color || 'var(--mission-text-dim)', ...style }}>
      {children}
    </span>
  );
}

/* MissionMetric — the atomic "one number with its name": label + figure + unit,
   colored by economic meaning. Engineering (tabular mono) figures by default so
   they never reflow mid-motion. `value` is pre-formatted by the caller. */
export function MissionMetric({
  label, value, unit, sub, tone = 'neutral', size = 26, mono = true, align = 'left',
}) {
  const color = toneColor(tone);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4,
                  alignItems: align === 'right' ? 'flex-end' : 'flex-start' }}>
      <MissionLabel>{label}</MissionLabel>
      <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span className={mono ? 'mission-num' : 'mission-text'}
              style={{ fontSize: size, fontWeight: 'var(--mission-fw-figure)', color, lineHeight: 1,
                       textShadow: `0 0 22px ${color}44` }}>
          {value ?? '—'}
        </span>
        {unit && <span style={{ fontSize: 12, color: 'var(--mission-text-2)', fontWeight: 600 }}>{unit}</span>}
      </span>
      {sub && <span style={{ fontSize: 'var(--mission-fs-micro)', color: 'var(--mission-text-dim)',
                             lineHeight: 1.5 }}>{sub}</span>}
    </div>
  );
}
