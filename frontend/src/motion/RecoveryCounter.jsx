// SPEC-MI atomic: RecoveryCounter (MI-3) — the recovered-value figure does not
// jump: it accrues CAUSE BY CAUSE. Each increment is one real ledger bucket
// (opportunities[].period_gain, the exact positive-gap partition), so the
// animation IS the attribution: segments sum to the audited total by
// construction (MI-0 No-Fabrication Motion). Pure UI — props from the data layer.
import React, { useEffect, useRef, useState } from 'react';
import { useMotionValue, animate, useReducedMotion } from 'framer-motion';

const money = (v, cur) =>
  `${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;

export default function RecoveryCounter({ items = [], currency = 'USD',
                                          title = 'Recorded recoverable value' }) {
  const reduced = useReducedMotion();
  const total = items.reduce((s, it) => s + (it.gain || 0), 0);
  const mv = useMotionValue(0);
  const [display, setDisplay] = useState(reduced ? money(total, currency) : money(0, currency));
  const [stage, setStage] = useState(reduced ? items.length : -1);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    const unsub = mv.on('change', (v) => setDisplay(money(v, currency)));
    if (reduced || items.length === 0) { mv.set(total); setStage(items.length); return () => { alive.current = false; unsub(); }; }
    let cum = 0;
    const run = (i) => {
      if (!alive.current || i >= items.length) { setStage(items.length); return; }
      setStage(i);
      cum += items[i].gain || 0;
      animate(mv, cum, {
        type: 'spring', stiffness: 45, damping: 18,
        onComplete: () => run(i + 1),
      });
    };
    mv.set(0); run(0);
    return () => { alive.current = false; unsub(); };
  }, [items.map((i) => i.gain).join(','), reduced]);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '20px 24px' }}>
      <div style={{ fontSize: 10, letterSpacing: '0.2em', textTransform: 'uppercase',
                    color: 'var(--pds-text-3, #7A89A3)', fontWeight: 700, marginBottom: 8 }}>
        {title} · {items.length} governed cause{items.length === 1 ? '' : 's'}
      </div>
      <div className="pdm-mono"
           style={{ fontSize: 40, fontWeight: 800, lineHeight: 1, color: 'var(--pdm-optimal)',
                    textShadow: '0 0 24px var(--pdm-optimal-glow)', marginBottom: 16 }}>
        {display}
      </div>
      <div style={{ display: 'grid', gap: 7 }}>
        {items.map((it, i) => {
          const done = i < stage || stage >= items.length;
          const active = i === stage && stage < items.length;
          return (
            <div key={it.name} style={{ display: 'flex', gap: 10, alignItems: 'baseline',
                                        opacity: done || active ? 1 : 0.28,
                                        transition: 'opacity 320ms ease' }}>
              <span className="pdm-mono" style={{ fontSize: 11, minWidth: 14, fontWeight: 700,
                     color: done ? 'var(--pdm-optimal)' : active ? 'var(--pds-accent, #34E0C8)' : 'var(--pds-text-3, #7A89A3)' }}>
                {done ? '✓' : active ? '▸' : '·'}
              </span>
              <span style={{ fontSize: 13, color: 'var(--pds-text, #EAF1F8)', fontWeight: 600, flex: 1 }}>
                {it.name}
              </span>
              <span className="pdm-mono" style={{ fontSize: 12, fontWeight: 700, color: 'var(--pdm-optimal)' }}>
                +{money(it.gain || 0, currency)}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--pds-text-3, #7A89A3)', marginTop: 14, lineHeight: 1.6 }}>
        Each increment is one ledger bucket (exact positive-gap partition) — segments sum to the
        audited total by construction. Recorded period only; no forward projection.
      </div>
    </div>
  );
}
