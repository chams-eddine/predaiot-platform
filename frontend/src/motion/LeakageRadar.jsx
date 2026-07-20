// SPEC-MI atomic: LeakageRadar (MI-7) — radial beams, one per REAL loss category
// (root_causes[]). Beam length = that cause's share of positive gap; the largest
// beam pulses. MI-0: no beam without a root_causes entry. Hover reveals exact USD.
import React, { useState } from 'react';

const money = (v, cur) => `${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;

export default function LeakageRadar({ causes = [], currency = 'USD', size = 320 }) {
  const [hover, setHover] = useState(null);
  if (!causes.length) return null;
  const cx = size / 2, cy = size / 2, rMax = size / 2 - 46;
  const maxPct = Math.max(...causes.map((c) => Math.abs(c.contribution_pct || 0)), 1);
  const biggest = causes.reduce((a, b) => (Math.abs(b.contribution_pct || 0) > Math.abs(a.contribution_pct || 0) ? b : a), causes[0]);
  const N = causes.length;

  return (
    <div style={{ background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '16px 20px', display: 'flex', gap: 20,
                  alignItems: 'center', flexWrap: 'wrap' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
           aria-label="Value-leakage radar by root cause">
        {[0.33, 0.66, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={rMax * f} fill="none"
                  stroke="var(--pds-border, #1B2536)" strokeWidth="1" />
        ))}
        {causes.map((c, i) => {
          const ang = (-90 + (360 / N) * i) * (Math.PI / 180);
          const len = rMax * (Math.abs(c.contribution_pct || 0) / maxPct);
          const x2 = cx + Math.cos(ang) * len, y2 = cy + Math.sin(ang) * len;
          const isMax = c === biggest;
          const on = hover === i;
          return (
            <g key={c.category} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
               style={{ cursor: 'default' }}>
              <line x1={cx} y1={cy} x2={cx + Math.cos(ang) * rMax} y2={cy + Math.sin(ang) * rMax}
                    stroke="var(--pds-border, #1B2536)" strokeWidth="1" />
              <line x1={cx} y1={cy} x2={x2} y2={y2}
                    stroke="var(--pdm-leak)" strokeWidth={on ? 6 : 4} strokeLinecap="round"
                    style={{ filter: `drop-shadow(0 0 ${isMax ? 8 : 4}px var(--pdm-leak-glow))`,
                             opacity: on || !hover ? 1 : 0.5, transition: 'all 160ms ease' }} />
              <circle cx={x2} cy={y2} r={isMax ? 5 : 3.5} fill="var(--pdm-leak)"
                      className={isMax ? 'pdm-leak-dot' : ''}
                      style={{ filter: 'drop-shadow(0 0 6px var(--pdm-leak-glow))' }} />
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r="3" fill="var(--pds-text-3, #7A89A3)" />
      </svg>
      <div style={{ minWidth: 200, flex: 1 }}>
        <div style={{ fontSize: 10, letterSpacing: '0.2em', color: 'var(--pds-text-3, #7A89A3)',
                      fontWeight: 700, marginBottom: 10 }}>LEAKAGE BY ROOT CAUSE</div>
        {causes.map((c, i) => (
          <div key={c.category} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
               style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '6px 8px',
                        borderRadius: 6, background: hover === i ? 'var(--pdm-leak-glow)' : 'transparent',
                        transition: 'background 140ms ease' }}>
            <span style={{ fontSize: 12.5, color: 'var(--pds-text, #EAF1F8)', fontWeight: 600 }}>
              {c.category}
            </span>
            <span className="pdm-mono" style={{ fontSize: 12, color: 'var(--pdm-leak)', fontWeight: 700 }}>
              {hover === i ? money(c.loss_usd || 0, currency) : `${(c.contribution_pct || 0).toFixed(1)}%`}
            </span>
          </div>
        ))}
        <div style={{ fontSize: 10.5, color: 'var(--pds-text-3, #7A89A3)', marginTop: 8 }}>
          Hover a beam for exact {currency}. Shares are the exact positive-gap partition.
        </div>
      </div>
    </div>
  );
}
