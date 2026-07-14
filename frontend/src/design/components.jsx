// ============================================================================
// PREDAIOT DESIGN SYSTEM — reusable premium components.
// Pure presentational; consume real data only. No backend, no fake data.
// ============================================================================
import React, { useEffect, useRef, useState } from 'react';
import { PDS, gradeColor, fmtMoney } from './ds';

/* Premium surface with a hairline top-accent and soft depth. */
export function Panel({ children, accent, style, pad = PDS.s6, className = '' }) {
  return (
    <div className={`pds-rise ${className}`} style={{
      position: 'relative', background: `linear-gradient(180deg, ${PDS.panel2}, ${PDS.panel})`,
      border: `1px solid ${PDS.border}`, borderRadius: PDS.rLg, padding: pad,
      boxShadow: PDS.shadow1, overflow: 'hidden', ...style,
    }}>
      {accent !== false && <div className="pds-accent-line" />}
      {children}
    </div>
  );
}

/* Count-up number with easing; respects reduced-motion. */
export function AnimatedNumber({ value, decimals = 0, prefix = '', suffix = '', style }) {
  const [disp, setDisp] = useState(value ?? 0);
  const fromRef = useRef(value ?? 0);
  const rafRef = useRef(null);
  useEffect(() => {
    const target = Number(value);
    if (Number.isNaN(target)) { setDisp(value); return; }
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { setDisp(target); fromRef.current = target; return; }
    const from = Number(fromRef.current) || 0;
    const t0 = performance.now(); const dur = 520;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      setDisp(from + (target - from) * ease(p));
      if (p < 1) rafRef.current = requestAnimationFrame(step);
      else fromRef.current = target;
    };
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value]);
  const text = (typeof disp === 'number' && !Number.isNaN(disp))
    ? Number(disp).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    : '—';
  return <span className="pds-num" style={style}>{prefix}{text}{suffix}</span>;
}

/* Executive KPI card — large money, semantic color, live/trend/confidence. */
export function KpiCard({ label, value, currency = '', color = PDS.text, decimals = 0,
                         sub, trend, live, grade, big, minWidth = 220 }) {
  const numColor = color;
  return (
    <Panel pad={PDS.s5} style={{ flex: 1, minWidth, display: 'flex', flexDirection: 'column', gap: PDS.s3 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="pds-kicker">{label}</span>
        {live && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 9, color: PDS.recover, letterSpacing: '0.14em' }}>
          <span className="pds-live-dot" style={{ background: PDS.recover }} />LIVE</span>}
        {grade && <GradeBadge grade={grade} />}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap', minWidth: 0 }}>
        <span style={{ fontSize: big ? 'clamp(30px, 3.4vw, 46px)' : 'clamp(24px, 2.4vw, 34px)',
                       fontWeight: 800, color: numColor, lineHeight: 1,
                       whiteSpace: 'nowrap', letterSpacing: '-0.01em',
                       textShadow: `0 0 30px ${numColor}22` }}>
          {typeof value === 'number'
            ? <AnimatedNumber value={value} decimals={decimals} />
            : <span className="pds-num">{value ?? '—'}</span>}
        </span>
        {currency && <span style={{ fontSize: big ? 16 : 13, color: PDS.text2, fontWeight: 600 }}>{currency}</span>}
      </div>
      {(sub || trend != null) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: PDS.text3 }}>
          {trend != null && <Trend value={trend} />}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </Panel>
  );
}

export function GradeBadge({ grade }) {
  const c = gradeColor(grade);
  return (
    <span className="pds-num" style={{
      fontSize: 11, fontWeight: 800, color: c, background: `${c}1A`,
      border: `1px solid ${c}44`, borderRadius: PDS.rPill, padding: '2px 10px', letterSpacing: '0.04em',
    }}>{grade || 'N/A'}</span>
  );
}

export function Trend({ value }) {
  const up = value >= 0;
  const c = up ? PDS.loss : PDS.recover; // rising leakage = bad; falling = good
  return (
    <span className="pds-num" style={{ color: c, display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 700 }}>
      {up ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function StatusDot({ color = PDS.recover, pulse = false, size = 8 }) {
  return <span className={pulse ? 'pds-live-dot' : ''} style={{
    width: size, height: size, borderRadius: '50%', background: color,
    display: 'inline-block', boxShadow: `0 0 10px ${color}` }} />;
}

/* Evidence chip — provisional (amber) vs certified/verified (green). */
export function EvidenceBadge({ provisional, hash, status }) {
  const verified = provisional === false;
  const c = verified ? PDS.verified : PDS.provisional;
  const label = status || (verified ? 'CERTIFIED' : 'PROVISIONAL');
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8,
      border: `1px solid ${c}44`, background: `${c}12`, color: c,
      borderRadius: PDS.rPill, padding: '5px 12px', fontSize: 10, letterSpacing: '0.14em', fontWeight: 700 }}>
      <StatusDot color={c} pulse={!verified} size={7} />
      {label}
      {hash && <span className="pds-num" style={{ color: PDS.text3, letterSpacing: 0, fontWeight: 500 }}>
        {String(hash).slice(0, 10)}…</span>}
    </span>
  );
}

export function SectionTitle({ tag, title, sub, right }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: PDS.s5 }}>
      <div>
        {tag && <div className="pds-kicker" style={{ color: PDS.accent, marginBottom: 6 }}>{tag}</div>}
        <div style={{ fontSize: 22, fontWeight: 800, color: PDS.text, letterSpacing: '-0.01em' }}>{title}</div>
        {sub && <div style={{ fontSize: 12, color: PDS.text3, marginTop: 4 }}>{sub}</div>}
      </div>
      {right}
    </div>
  );
}

/* Lightweight SVG sparkline — no chart lib, PREDAIOT line language. */
export function Sparkline({ points = [], color = PDS.accent, height = 44, width = 160, fill = true }) {
  if (!points || points.length < 2) return <div style={{ height }} />;
  const min = Math.min(...points), max = Math.max(...points);
  const span = (max - min) || 1;
  const step = width / (points.length - 1);
  const xy = points.map((p, i) => [i * step, height - ((p - min) / span) * (height - 6) - 3]);
  const d = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${d} L${width},${height} L0,${height} Z`;
  const gid = 'spk' + Math.random().toString(36).slice(2, 7);
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${gid})`} />}
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${color}66)` }} />
      <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r="3" fill={color}
              style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
    </svg>
  );
}

export function Divider() {
  return <div style={{ height: 1, background: PDS.hairline, margin: `${PDS.s5} 0` }} />;
}
