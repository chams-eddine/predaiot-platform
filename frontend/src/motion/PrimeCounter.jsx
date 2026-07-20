// SPEC-MI atomic: PrimeCounter — a financial/percentage figure that MOUNTS with
// spring physics instead of jumping. MI-0: animates only to a real audited value
// passed in via props; the component never invents or extrapolates.
// Drop-in pure UI: no fetching, no state management — props from the data layer.
import React, { useEffect, useRef, useState } from 'react';
import { useMotionValue, useTransform, animate, useReducedMotion } from 'framer-motion';

const fmt = (v, mode, currency) => {
  if (mode === 'percentage') return `${v.toFixed(1)}%`;
  const abs = Math.abs(v);
  const s = abs >= 1000
    ? abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : abs.toFixed(2);
  return currency ? `${s} ${currency}` : s;
};

export default function PrimeCounter({ value, mode = 'currency', title, intent = 'leak',
                                       currency = 'USD', size = 44, numStyle }) {
  const reduced = useReducedMotion();
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => fmt(v, mode, mode === 'currency' ? currency : null));
  const [display, setDisplay] = useState(() => fmt(reduced ? (value || 0) : 0, mode,
    mode === 'currency' ? currency : null));
  const ref = useRef(null);

  useEffect(() => {
    const unsub = text.on('change', setDisplay);
    if (reduced) { mv.set(value || 0); return unsub; }
    const ctrl = animate(mv, value || 0, { type: 'spring', stiffness: 45, damping: 18 });
    return () => { ctrl.stop(); unsub(); };
  }, [value, reduced]);  // eslint-disable-line react-hooks/exhaustive-deps

  const color = intent === 'optimal' ? 'var(--pdm-optimal)' : 'var(--pdm-leak)';
  const glow = intent === 'optimal' ? 'var(--pdm-optimal-glow)' : 'var(--pdm-leak-glow)';
  return (
    <div ref={ref} style={{ display: 'inline-block' }}>
      {title && (
        <div style={{ fontSize: 10, letterSpacing: '0.2em', textTransform: 'uppercase',
                      color: 'var(--pds-text-3, #7A89A3)', fontWeight: 600, marginBottom: 6 }}>
          {title}
        </div>
      )}
      <div className="pdm-mono"
           style={{ fontSize: size, fontWeight: 800, lineHeight: 1, color,
                    textShadow: `0 0 24px ${glow}`, ...numStyle }}>
        {display}
      </div>
    </div>
  );
}
