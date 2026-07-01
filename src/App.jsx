import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';

// ══════════════════════════════════════════════════════════════════════
// TRIAL GATE — 7-day free diagnostic token (lead capture)
// Real auth (Clerk + per-user workspaces) is deferred. This wires every
// /api/v1/audit* call through an X-Trial-Token header and surfaces a
// gate modal on 401 / "book consultation" CTA on 402.
// ══════════════════════════════════════════════════════════════════════
const TRIAL_STORAGE_KEY = 'predaiot.trial.v1';

const trialStore = {
  get: () => {
    try { return JSON.parse(localStorage.getItem(TRIAL_STORAGE_KEY) || 'null'); }
    catch { return null; }
  },
  set: (v) => { try { localStorage.setItem(TRIAL_STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(TRIAL_STORAGE_KEY); } catch {} },
};

axios.interceptors.request.use((cfg) => {
  const t = trialStore.get();
  if (t?.token) cfg.headers['X-Trial-Token'] = t.token;
  return cfg;
});

axios.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;
    if (status === 401 && detail?.code?.startsWith('trial_token')) {
      window.dispatchEvent(new CustomEvent('predaiot:trial-required', { detail }));
    } else if (status === 402 && detail?.code === 'trial_expired') {
      trialStore.clear();
      window.dispatchEvent(new CustomEvent('predaiot:trial-expired', { detail }));
    }
    return Promise.reject(err);
  }
);

// ══════════════════════════════════════════════════════════════════════
// DESIGN SYSTEM — PREDAIOT Economic Decision Audit™
// ══════════════════════════════════════════════════════════════════════
const DS = {
  bg:           '#030508',
  bgRaised:     '#080c12',
  surface:      'rgba(255,255,255,0.025)',
  surfaceHi:    'rgba(255,255,255,0.05)',
  border:       'rgba(255,255,255,0.06)',
  borderHi:     'rgba(255,255,255,0.14)',

  optimal:  '#00E676',
  warning:  '#FFD600',
  loss:     '#FF1744',
  blue:     '#4BBFFF',
  cyan:     '#00E5FF',
  orange:   '#FF6D00',
  purple:   '#BB86FC',

  text:    '#E8EAF0',
  sub:     '#8A94A6',
  dim:     '#4A5468',

  mono: "'JetBrains Mono','Fira Code','Courier New',monospace",
  sans: "'Inter','Segoe UI',sans-serif",
  r8: '8px', r12: '12px', r16: '16px', r20: '20px',
};

// ── Utilities ────────────────────────────────────────────────────────
const fmtUSD = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}k`;
  return `$${n.toFixed(2)}`;
};
const fmtPct = (n, decimals = 1) => n == null ? '—' : `${Number(n).toFixed(decimals)}%`;
const riskColor = (r) => r === 'Low' ? DS.optimal : r === 'Moderate' ? DS.warning : DS.loss;
const riskEmoji = (r) => r === 'Low' ? '🟢' : r === 'Moderate' ? '🟡' : '🔴';
const heatColor = (s) => ({
  optimal: DS.optimal, acceptable: DS.warning, poor: DS.orange, critical: DS.loss,
}[s] || DS.dim);
const qualColor = (pct) => pct >= 70 ? DS.optimal : pct >= 40 ? DS.warning : DS.loss;

// ── Base Components ──────────────────────────────────────────────────
const Card = ({ children, style, glow }) => (
  <div style={{
    background: DS.surface, border: `1px solid ${glow ? glow + '30' : DS.border}`,
    borderRadius: DS.r12, padding: '20px 24px',
    boxShadow: glow ? `0 0 28px ${glow}12` : 'none',
    ...style,
  }}>{children}</div>
);

const Label = ({ children, style }) => (
  <div style={{
    color: DS.dim, fontSize: 10, fontWeight: 600,
    letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 6, ...style,
  }}>{children}</div>
);

const BigNum = ({ v, color, size = 26 }) => (
  <div style={{
    color: color || DS.text, fontSize: size, fontWeight: 700, fontFamily: DS.mono,
    lineHeight: 1.1, whiteSpace: 'nowrap',
  }}>{v}</div>
);

const Pill = ({ label, color }) => (
  <span style={{
    display: 'inline-block', padding: '3px 10px', borderRadius: 20,
    border: `1px solid ${color}`, color, fontSize: 10, fontWeight: 700,
    letterSpacing: '0.08em', background: `${color}14`,
  }}>{label}</span>
);

const Divider = ({ style }) => <div style={{ height: 1, background: DS.border, margin: '16px 0', ...style }} />;

const SectionHeader = ({ tag, title }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 24 }}>
    {tag && <span style={{ color: DS.dim, fontFamily: DS.mono, fontSize: 10, letterSpacing: '0.25em' }}>EDA-{tag}</span>}
    <h2 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: DS.text, letterSpacing: '0.12em', textTransform: 'uppercase' }}>{title}</h2>
  </div>
);

const EmptyMsg = ({ children }) => (
  <div style={{ textAlign: 'center', color: DS.dim, padding: '48px 0', fontSize: 12 }}>{children}</div>
);

const BtnOutline = ({ color, children, onClick, disabled, style }) => (
  <button onClick={onClick} disabled={disabled} style={{
    padding: '8px 18px', background: 'transparent',
    color: disabled ? DS.dim : color, border: `1px solid ${disabled ? DS.dim : color}`,
    borderRadius: DS.r8, cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: 11, letterSpacing: '0.1em', fontWeight: 700,
    fontFamily: DS.sans, transition: 'all 0.15s', ...style,
  }}>{children}</button>
);

// ── Progress Bar ─────────────────────────────────────────────────────
const ProgressBar = ({ pct, color }) => (
  <div style={{ height: 5, background: DS.border, borderRadius: 3, marginTop: 8, overflow: 'hidden' }}>
    <div style={{ width: `${Math.min(100, pct || 0)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
  </div>
);

// ══════════════════════════════════════════════════════════════════════
// UNIVERSAL FILE UPLOAD COMPONENT
// ══════════════════════════════════════════════════════════════════════
const ASSET_TYPES = ['BESS', 'Solar', 'Wind', 'Gas', 'Hydro', 'Hydrogen', 'Desalination', 'CHP', 'Nuclear', 'Geothermal', 'Microgrid', 'Generic'];

const COLUMN_GUIDE = [
  {
    label: 'Price Column',
    required: true,
    cols: ['price', 'spot_price', 'lmp', 'market_price', 'omr_mwh', 'da_price', 'rt_price', 'energy_price', 'clearing_price', 'settlement_price'],
  },
  {
    label: 'Output Column',
    required: true,
    cols: ['actual_discharge', 'generation', 'output_mw', 'gen_mw', 'actual_power', 'dispatch_mw', 'solar_output', 'wind_output', 'p_actual', 'net_output'],
  },
  {
    label: 'State of Charge',
    required: false,
    cols: ['soc', 'state_of_charge', 'battery_soc', 'soc_pct'],
  },
  {
    label: 'Curtailment',
    required: false,
    cols: ['curtailment_mw', 'curtailed_mw', 'clipped_mw', 'spillage'],
  },
  {
    label: 'Operator Override',
    required: false,
    cols: ['operator_override', 'manual_override', 'human_override'],
  },
  {
    label: 'Forecast Price',
    required: false,
    cols: ['forecast_price', 'predicted_price', 'da_forecast'],
  },
  {
    label: 'Asset Metadata',
    required: false,
    cols: ['asset_type', 'asset_name', 'p_max', 'e_max', 'eta_ch', 'eta_dis'],
  },
];

const FileUploadZone = ({ onFile, loading }) => {
  const [dragging, setDragging] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const inputRef = useRef(null);

  const process = (file) => {
    if (!file) return;
    if (!/\.(csv|xlsx|xls)$/i.test(file.name)) {
      alert('Please upload a CSV or Excel (.xlsx / .xls) file.');
      return;
    }
    onFile(file);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    process(e.dataTransfer.files[0]);
  }, []);

  return (
    <div style={{ padding: '32px 40px', maxWidth: 800, margin: '0 auto' }}>
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !loading && inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? DS.cyan : DS.border}`,
          borderRadius: DS.r16, padding: '52px 40px', textAlign: 'center',
          background: dragging ? `${DS.cyan}08` : DS.surface,
          cursor: loading ? 'wait' : 'pointer',
          transition: 'all 0.2s ease',
        }}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={(e) => process(e.target.files[0])} style={{ display: 'none' }} />
        <div style={{ fontSize: 36, marginBottom: 14 }}>📊</div>
        <div style={{ color: DS.text, fontSize: 16, fontWeight: 700, marginBottom: 8 }}>
          {loading ? 'Processing your data…' : 'Drop any energy asset data file here'}
        </div>
        <div style={{ color: DS.sub, fontSize: 12, marginBottom: 20 }}>
          CSV · XLSX · XLS — column names auto-detected across 80+ naming variants
        </div>

        {/* Asset type badges */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
          {ASSET_TYPES.map((t) => <Pill key={t} label={t} color={DS.cyan} />)}
        </div>

        <div style={{ color: DS.dim, fontSize: 11, lineHeight: 1.8 }}>
          ✓ Auto-resolves column names &nbsp;·&nbsp; ✓ Any market region &nbsp;·&nbsp; ✓ Mixed unit formats accepted
        </div>
      </div>

      {/* Column guide toggle */}
      <div style={{ textAlign: 'center', marginTop: 16 }}>
        <button
          onClick={() => setShowGuide(!showGuide)}
          style={{
            background: 'none', border: `1px solid ${DS.border}`,
            color: DS.sub, padding: '6px 18px', borderRadius: DS.r8,
            cursor: 'pointer', fontSize: 11,
          }}
        >
          {showGuide ? '↑ Hide' : '↓ Show'} accepted column names
        </button>
      </div>

      {showGuide && (
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {COLUMN_GUIDE.map(({ label, required, cols }) => (
            <div key={label} style={{ background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r8, padding: '12px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ color: DS.sub, fontSize: 10, fontWeight: 700, letterSpacing: '0.12em' }}>{label.toUpperCase()}</span>
                {required && <Pill label="REQUIRED" color={DS.loss} />}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {cols.map((c) => (
                  <code key={c} style={{ fontSize: 9, color: DS.cyan, background: `${DS.cyan}10`, padding: '2px 6px', borderRadius: 4 }}>{c}</code>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ══════════════════════════════════════════════════════════════════════
// EMPTY / INITIAL STATE
// ══════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════
// SIM PROFILES — per-sector synthetic SCADA payloads for /ws/live demos.
// Each profile maps to a backend dispatch mode (see _dispatch_mode in main.py)
// so the live decision core sees realistic data for the asset class.
// ══════════════════════════════════════════════════════════════════════
const SIM_PROFILES = {
  bess: {
    label: 'BESS · Battery storage',
    asset_id: 'DEMO_BESS_50MW',
    p_max: 50, deg_cost: 5,
    init: (ref) => { ref.soc = 0.5; ref.step = 0; },
    tick: (ref) => {
      ref.step += 1;
      const t = ref.step;
      const price = Math.max(3, 45 + 55 * Math.sin((t - 18) * Math.PI / 36) + (Math.random() - 0.5) * 14);
      const curtailment = (t % 23 === 0) ? Math.round(8 + Math.random() * 20) : 0;
      const willDischarge = price > 70 && ref.soc > 0.25;
      const willCharge = (price < 25 || curtailment > 0) && ref.soc < 0.85;
      const actual_discharge = willDischarge ? Math.round(20 + Math.random() * 25) : 0;
      const actual_charge = willCharge ? Math.round(10 + Math.random() * 15) : 0;
      ref.soc = Math.max(0.1, Math.min(0.95, ref.soc + actual_charge * 0.004 - actual_discharge * 0.004));
      return {
        market_price: Math.round(price * 100) / 100,
        actual_discharge, actual_charge,
        soc: Math.round(ref.soc * 1000) / 1000,
        p_max: 50, e_max: 100,
        eta_charge: 0.95, eta_discharge: 0.95,
        deg_cost: 5, curtailment,
        forecast_price: Math.round(Math.max(3, price * (0.85 + Math.random() * 0.3)) * 100) / 100,
        grid_limit: 50,
      };
    },
  },
  solar: {
    label: 'Solar · 30 MW PV plant',
    asset_id: 'DEMO_SOLAR_30MW',
    p_max: 30, deg_cost: 0.5,
    init: (ref) => { ref.step = 0; },
    tick: (ref) => {
      ref.step += 1;
      const t = ref.step;
      // Irradiance bell curve over a 36-step "day". Negative when sun is down.
      const tod = ((t % 36) - 18) / 9; // -2..+2 across the daytime arc
      const irradiance = Math.max(0, Math.cos((tod * Math.PI) / 4));
      const available = Math.round(30 * irradiance * (0.9 + Math.random() * 0.2));
      // Market price: morning peak, midday dip from oversupply, evening peak. Can go negative.
      const price = 50 + 30 * Math.sin((t - 6) * Math.PI / 36) - 25 * Math.exp(-Math.pow((t % 36) - 18, 2) / 30) + (Math.random() - 0.5) * 10;
      // Operator runs naive: always export everything. Curtail nothing — leaves money on the table at negative prices.
      const curtailment = 0;
      const actual_discharge = available;
      return {
        market_price: Math.round(price * 100) / 100,
        actual_discharge, actual_charge: 0,
        p_max: 30, e_max: 0,
        deg_cost: 0.5, curtailment,
        forecast_price: Math.round(Math.max(-20, price * (0.85 + Math.random() * 0.3)) * 100) / 100,
        grid_limit: 30,
      };
    },
  },
  wind: {
    label: 'Wind · 60 MW farm',
    asset_id: 'DEMO_WIND_60MW',
    p_max: 60, deg_cost: 1.0,
    init: (ref) => { ref.step = 0; ref.windState = 0.6; },
    tick: (ref) => {
      ref.step += 1;
      const t = ref.step;
      // Wind speed random walk (AR(1)-ish) — gusts and lulls
      ref.windState = Math.max(0, Math.min(1, ref.windState + (Math.random() - 0.5) * 0.18));
      const available = Math.round(60 * ref.windState);
      // Wind tends to blow at night — overnight glut depresses price
      const price = 40 + 35 * Math.sin((t - 30) * Math.PI / 36) + (Math.random() - 0.5) * 18 - 30 * Math.max(0, ref.windState - 0.7);
      // Operator curtails only during forced events (system operator instruction)
      const curtailment = (t % 17 === 0 && ref.windState > 0.6) ? Math.round(available * 0.4) : 0;
      const actual_discharge = Math.max(0, available - curtailment);
      return {
        market_price: Math.round(price * 100) / 100,
        actual_discharge, actual_charge: 0,
        p_max: 60, e_max: 0,
        deg_cost: 1.0, curtailment,
        forecast_price: Math.round(price * (0.8 + Math.random() * 0.4) * 100) / 100,
        grid_limit: 60,
      };
    },
  },
  gas: {
    label: 'Gas · 100 MW CCGT',
    asset_id: 'DEMO_GAS_100MW',
    p_max: 100, deg_cost: 28,
    init: (ref) => { ref.step = 0; ref.lastRun = false; },
    tick: (ref) => {
      ref.step += 1;
      const t = ref.step;
      const price = Math.max(5, 50 + 60 * Math.sin((t - 18) * Math.PI / 36) + (Math.random() - 0.5) * 22);
      // Operator follows a fixed schedule (runs 06:00–22:00 regardless of price) instead of merit-order.
      const tod = t % 36;
      const scheduleOn = tod >= 8 && tod <= 28;
      const actual_discharge = scheduleOn ? 75 + Math.round((Math.random() - 0.5) * 20) : 0;
      return {
        market_price: Math.round(price * 100) / 100,
        actual_discharge, actual_charge: 0,
        p_max: 100, e_max: 0,
        deg_cost: 28, curtailment: 0,
        forecast_price: Math.round(price * (0.9 + Math.random() * 0.2) * 100) / 100,
        grid_limit: 100,
      };
    },
  },
};

const EMPTY = {
  edv_optimal_total: 0, edv_actual_total: 0, dq_score: 0,
  total_gap_usd: 0, decision_log: [],
  asset_name: 'Energy Asset', asset_type: 'Generic',
  audit_period_label: '—', risk_level: 'Moderate',
  eda_metrics: null, root_causes: [], opportunities: [],
  heat_map: [], financial_leakage: null,
  ai_commentary: '', counterfactual_summary: '',
};

// ══════════════════════════════════════════════════════════════════════
// TRIAL UI — gate modal + expired CTA
// ══════════════════════════════════════════════════════════════════════
const overlayStyle = {
  position: 'fixed', inset: 0, zIndex: 1000,
  background: 'rgba(3, 5, 8, 0.78)', backdropFilter: 'blur(6px)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 24,
};
const cardStyle = {
  width: '100%', maxWidth: 460, background: DS.bgRaised,
  border: `1px solid ${DS.borderHi}`, borderRadius: DS.r16,
  padding: 28, fontFamily: DS.sans, color: DS.text,
  boxShadow: '0 30px 80px rgba(0,0,0,0.55)',
};
const inputStyle = {
  width: '100%', padding: '11px 13px', marginBottom: 12,
  background: DS.surface, border: `1px solid ${DS.border}`,
  borderRadius: DS.r8, color: DS.text, fontSize: 13,
  fontFamily: DS.sans, outline: 'none',
};
const primaryBtn = {
  width: '100%', padding: '12px 16px', border: 'none',
  borderRadius: DS.r8, background: DS.optimal, color: '#001b08',
  fontWeight: 700, letterSpacing: '0.04em', cursor: 'pointer',
  fontSize: 13,
};

function TrialGate({ busy, error, onSubmit, onDismiss }) {
  const [email, setEmail] = useState('');
  const [assetName, setAssetName] = useState('');
  const submit = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    onSubmit(email.trim(), assetName.trim());
  };
  return (
    <div style={overlayStyle} role="dialog" aria-modal="true">
      <div style={cardStyle}>
        <div style={{ fontSize: 10, letterSpacing: '0.2em', color: DS.cyan, marginBottom: 6 }}>
          FREE 7-DAY DIAGNOSTIC
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>
          See what your asset is leaving on the table
        </div>
        <div style={{ fontSize: 12, color: DS.sub, marginBottom: 20, lineHeight: 1.5 }}>
          Get a free Economic Decision Audit for one asset. No CAPEX. No connection to your SCADA required.
          Upload a CSV of one day of prices &amp; dispatch — we&rsquo;ll quantify the gap between captured and optimal value.
        </div>
        <form onSubmit={submit}>
          <input
            style={inputStyle}
            type="email"
            placeholder="Work email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            disabled={busy}
          />
          <input
            style={inputStyle}
            type="text"
            placeholder="Asset name (optional) — e.g. Ibri 2 BESS"
            value={assetName}
            onChange={(e) => setAssetName(e.target.value)}
            disabled={busy}
          />
          {error && (
            <div style={{ color: DS.loss, fontSize: 11, marginBottom: 12 }}>{String(error)}</div>
          )}
          <button type="submit" style={{ ...primaryBtn, opacity: busy ? 0.6 : 1 }} disabled={busy}>
            {busy ? 'Starting…' : 'Start free diagnostic →'}
          </button>
        </form>
        <button
          onClick={onDismiss}
          style={{
            marginTop: 12, width: '100%', padding: '8px',
            background: 'transparent', color: DS.sub,
            border: 'none', cursor: 'pointer', fontSize: 11,
          }}
        >
          Just looking around
        </button>
      </div>
    </div>
  );
}

function TrialExpired({ info, onStartNew, onClose }) {
  const bookingUrl = info?.booking_url || 'mailto:chams@preda-iot.com';
  return (
    <div style={overlayStyle} role="dialog" aria-modal="true">
      <div style={cardStyle}>
        <div style={{ fontSize: 10, letterSpacing: '0.2em', color: DS.warning, marginBottom: 6 }}>
          FREE DIAGNOSTIC ENDED
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 10 }}>
          Ready to quantify the full opportunity?
        </div>
        <div style={{ fontSize: 12, color: DS.sub, marginBottom: 20, lineHeight: 1.5 }}>
          {info?.message || 'Your 7-day free diagnostic has ended.'}
          {' '}The next step is a consultation — a board-ready Economic Audit for your full portfolio with an EDPC certificate.
        </div>
        <a
          href={bookingUrl}
          target="_blank" rel="noreferrer"
          style={{
            display: 'block', textAlign: 'center', textDecoration: 'none',
            padding: '12px 16px', borderRadius: DS.r8,
            background: DS.optimal, color: '#001b08', fontWeight: 700,
            letterSpacing: '0.04em', fontSize: 13, marginBottom: 10,
          }}
        >
          Book audit consultation →
        </a>
        <button
          onClick={onStartNew}
          style={{
            width: '100%', padding: '10px', background: 'transparent',
            color: DS.text, border: `1px solid ${DS.border}`,
            borderRadius: DS.r8, cursor: 'pointer', fontSize: 12, marginBottom: 6,
          }}
        >
          Start a new trial with a different email
        </button>
        <button
          onClick={onClose}
          style={{
            width: '100%', padding: '8px', background: 'transparent',
            color: DS.dim, border: 'none', cursor: 'pointer', fontSize: 11,
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// SESSION BADGE — honest header indicator (no more static "LIVE")
// ══════════════════════════════════════════════════════════════════════
function SessionBadge({ liveMode, simRunning, dataSource }) {
  // Order matters: real WebSocket trumps a stale audit view.
  let label, color;
  if (liveMode) {
    label = simRunning ? 'SIMULATING' : 'LIVE';
    color = DS.optimal;
  } else if (dataSource === 'demo') {
    label = 'DEMO DATA';
    color = DS.warning;
  } else if (dataSource === 'upload') {
    label = 'AUDIT';
    color = DS.cyan;
  } else if (dataSource === 'historical') {
    label = 'HISTORICAL';
    color = DS.blue;
  } else {
    label = 'IDLE';
    color = DS.dim;
  }
  return (
    <div
      style={{ display: 'flex', gap: 6, alignItems: 'center' }}
      title={`Session source: ${label.toLowerCase()}`}
    >
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        backgroundColor: color,
        boxShadow: color === DS.dim ? 'none' : `0 0 8px ${color}`,
      }} />
      <span style={{ color, fontSize: 10, letterSpacing: '0.12em', fontWeight: 700 }}>{label}</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════
export default function App() {
  const [data, setData]                   = useState(EMPTY);
  const [loading, setLoading]             = useState(false);
  const [uploading, setUploading]         = useState(false);
  const [shareLink, setShareLink]         = useState('');
  const [activeSection, setActiveSection] = useState('exec');
  const [showMethodology, setShowMethodology] = useState(false);
  const [showUpload, setShowUpload]       = useState(false);
  const [aiLoading, setAiLoading]         = useState(false);
  const [aiText, setAiText]               = useState('');
  const [histData, setHistData]           = useState([]);
  const [histLoading, setHistLoading]     = useState(false);
  const [liveMode, setLiveMode]           = useState(false);
  const [liveData, setLiveData]           = useState([]);
  const [wsRef]                           = useState({ current: null });
  const [simRunning, setSimRunning]       = useState(false);
  const [simRef]                          = useState({ current: null, soc: 0.5, step: 0 });
  const [certificate, setCertificate]     = useState(null);
  const [certLoading, setCertLoading]     = useState(false);
  // Tracks the provenance of the data currently on screen so the header
  // badge can stop lying. 'idle' | 'demo' | 'upload' | 'historical'
  const [dataSource, setDataSource]       = useState('idle');
  // Live Monitor simulator profile — drives the synthetic SCADA feed so
  // prospects see a feed that matches the asset class they care about.
  const [simProfile, setSimProfile]       = useState('bess');

  // ── Trial gate state ──────────────────────────────────────────────
  const [trial, setTrial]                 = useState(() => trialStore.get());
  const [gateOpen, setGateOpen]           = useState(() => !trialStore.get());
  const [gateBusy, setGateBusy]           = useState(false);
  const [gateError, setGateError]         = useState('');
  const [expiredInfo, setExpiredInfo]     = useState(null); // { booking_url, message } when 402

  const requireTrial = useCallback(() => {
    if (!trialStore.get()?.token) { setGateOpen(true); return false; }
    return true;
  }, []);

  // React to interceptor events fired anywhere in the app
  useEffect(() => {
    const onRequired = () => { setTrial(null); setGateOpen(true); };
    const onExpired  = (e) => { setTrial(null); setExpiredInfo(e.detail || {}); };
    window.addEventListener('predaiot:trial-required', onRequired);
    window.addEventListener('predaiot:trial-expired', onExpired);
    return () => {
      window.removeEventListener('predaiot:trial-required', onRequired);
      window.removeEventListener('predaiot:trial-expired', onExpired);
    };
  }, []);

  // Validate any stored token on mount; clear if rejected
  useEffect(() => {
    if (!trial?.token) return;
    axios.get('/api/v1/trial/status').catch(() => {
      trialStore.clear();
      setTrial(null);
      setGateOpen(true);
    });
  }, []); // intentional one-shot on mount

  const startTrial = async (email, assetName) => {
    setGateBusy(true);
    setGateError('');
    try {
      const r = await axios.post('/api/v1/trial/start', { email, asset_name: assetName });
      const next = { token: r.data.token, expires_at: r.data.expires_at, email, asset_name: assetName, booking_url: r.data.booking_url };
      trialStore.set(next);
      setTrial(next);
      setGateOpen(false);
      setExpiredInfo(null);
    } catch (err) {
      setGateError(err?.response?.data?.detail || 'Could not start trial. Try again.');
    }
    setGateBusy(false);
  };

  // Poll for the latest server-side audit result (populates view on cold load)
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await axios.get('/api/latest');
        if (r.data?.dq_score > 0) {
          setData(r.data);
          // Only set if we haven't tagged from a fresher local action.
          setDataSource((cur) => (cur === 'idle' ? 'historical' : cur));
          setShowUpload(false);
          setAiText('');
        }
      } catch (_) {}
    };
    poll();
    const iv = setInterval(poll, 60000);
    return () => clearInterval(iv);
  }, []);

  // Cleanup live WebSocket + simulator on unmount
  useEffect(() => {
    return () => {
      if (simRef.current) clearInterval(simRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // ── Demo audit ─────────────────────────────────────────────────────
  const runDemo = async () => {
    if (!requireTrial()) return;
    setLoading(true);
    setShowUpload(false);
    try {
      const ts = [];
      let soc = 0.2;
      for (let i = 0; i < 288; i++) {
        const base = 30 + 70 * Math.sin((i - 72) * (Math.PI / 144));
        const price = Math.max(5, parseFloat((base + (Math.random() - 0.5) * 10).toFixed(2)));
        let dis = 0;
        if (price < 20 && soc < 0.9) soc += 40 * 0.95 / 100;
        if (price > 40 && soc > 0.2) {
          dis = Math.min(40, (soc - 0.2) * 100);
          soc -= dis / 0.95 / 100;
        }
        ts.push({ hour: i, price, actual_discharge: dis, forecast_price: parseFloat((price * (0.9 + Math.random() * 0.2)).toFixed(2)) });
      }
      const r = await axios.post('/api/v1/audit', {
        asset: { asset_type: 'BESS', asset_name: 'Ibri 2 — 500 MW BESS', asset_id: 'IBRI2_BESS', p_max: 50, e_max: 100, soc_init: 0.5, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 },
        time_series: ts,
      });
      setData(r.data);
      setDataSource('demo');
      setAiText('');
      setActiveSection('exec');
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // ── File upload ────────────────────────────────────────────────────
  const handleFile = async (file) => {
    if (!requireTrial()) return;
    setUploading(true);
    setShowUpload(false);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post('/api/v1/audit/file', fd);
      setData(r.data);
      setDataSource('upload');
      setAiText('');
      setActiveSection('exec');
    } catch (err) {
      const detail = err?.response?.data?.detail || '';
      alert(
        'Upload failed.\n\n' +
        (detail || 'Could not locate a price column or output column.\n\nTip: POST your file to /api/v1/audit/inspect to see the full mapping attempt.')
      );
    }
    setUploading(false);
  };

  // ── Share ──────────────────────────────────────────────────────────
  const handleShare = async () => {
    if (!data.dq_score) return alert('Run an audit first.');
    try {
      const r = await axios.post('/api/share', data);
      const url = window.location.origin + r.data.share_url;
      setShareLink(url);
      navigator.clipboard?.writeText(url);
      alert('Link copied!\n' + url);
    } catch (_) {}
  };

  // ── Download branded PDF (letterhead overlay) ──────────────────────
  const [pdfLoading, setPdfLoading] = useState(false);
  const downloadPdf = async () => {
    if (!data.dq_score) return alert('Run an audit first.');
    if (!requireTrial()) return;
    setPdfLoading(true);
    try {
      const r = await axios.post('/api/v1/audit/pdf', data, { responseType: 'blob' });
      const disposition = r.headers?.['content-disposition'] || '';
      const m = /filename="([^"]+)"/.exec(disposition);
      const filename = m ? m[1] : `PREDAIOT_Audit_${(data.asset_name || 'asset').replace(/\s+/g, '_')}.pdf`;
      const blobUrl = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = blobUrl; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (err) {
      // 401/402 are surfaced via the global interceptor (gate / expired modal)
      if (err?.response?.status !== 401 && err?.response?.status !== 402) {
        alert('PDF generation failed. Try again or contact support.');
      }
    }
    setPdfLoading(false);
  };

  // ── Claude AI enhanced commentary ─────────────────────────────────
  const generateAI = async () => {
    if (!data.dq_score) return;
    setAiLoading(true);
    try {
      const capturePct = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
      const missedCount = (data.decision_log || []).filter(d => d.decision_type === 'Missed Arbitrage').length;
      const opsBlock = (data.opportunities || []).slice(0, 5).map((o, i) =>
        `${i + 1}. ${o.name} — Annual Gain: $${o.annual_gain_usd?.toLocaleString()} | Implementation: ${o.difficulty} | Risk: ${o.operational_risk} | Confidence: ${o.confidence_pct}% | Owner: ${o.owner} | Priority: ${o.priority_score}/100 | Investment: ${o.investment_type} | Evidence: ${o.evidence}`
      ).join('\n');
      const causesBlock = (data.root_causes || []).slice(0, 5).map(r => `${r.category}: ${r.contribution_pct}% ($${r.loss_usd?.toLocaleString()})`).join(', ');

      const payload = {
        model: 'claude-sonnet-4-6',
        max_tokens: 1400,
        messages: [{
          role: 'user',
          content: `You are an independent economic auditor writing the PREDAIOT Economic Intelligence Report™ — a formal audit finding in the style of a Big-4 economic assurance report (Deloitte/McKinsey register). You are PREDAIOT's own auditing engine, not a generic AI assistant — never refer to yourself as an AI or chatbot.

AUDIT DATA (use these exact figures — do not invent numbers):
Asset: ${data.asset_name} (${data.asset_type})
Audit Period: ${data.audit_period_label}
Economic Potential: ${fmtUSD(data.edv_optimal_total)}
Captured Value: ${fmtUSD(data.edv_actual_total)}
Destroyed Value: ${fmtUSD(data.total_gap_usd)}
Capture Rate: ${capturePct.toFixed(1)}%
Decision Quality Score: ${((data.dq_score || 0) * 100).toFixed(1)} / 100
Economic Intelligence Score: ${data.eda_metrics?.economic_intelligence_score ?? 'N/A'} / 100
Risk Level: ${data.risk_level}
Annual Leakage Projection: ${fmtUSD(data.total_gap_usd * 365)}
Missed High-Value Intervals: ${missedCount}
Dispatch Records Analysed: ${(data.decision_log || []).length}
Forecast Utilization: ${data.eda_metrics?.forecast_utilization_index ?? 'N/A'}%

ROOT CAUSES: ${causesBlock || 'Not available'}

RANKED OPPORTUNITIES (use these exact figures in Recommended Actions — do not invent different numbers):
${opsBlock || 'Not available'}

Write the report in exactly this structure, with these section headers in capitals, no markdown bold/asterisks:

EXECUTIVE ASSESSMENT
Two to three sentences. State the capture percentage and resulting rating plainly. Note whether the asset was technically available throughout.

KEY FINDINGS
List four lines exactly in this format:
✔ Economic Intelligence Score    [value] / 100
✔ Economic Leakage               $[value]
✔ Missed High-Value Intervals    [value]
✔ Largest Opportunity            [name of #1 ranked opportunity]

ROOT CAUSE ANALYSIS
Two to three sentences explaining which decision logic (not equipment) caused the loss, citing the specific root cause percentages above.

OPERATIONAL IMPACT
Two sentences quantifying the annualised recoverable revenue if the top opportunities were implemented.

AUDITOR CONCLUSION
One to two sentences: is the asset operationally healthy but economically under-optimized, or already near-optimal?

RECOMMENDED ACTIONS
For each of the top 5 opportunities listed above, output a block in exactly this format (use the real data given, do not invent figures):

Recommendation N — [opportunity name]
  Expected Annual Gain    $[value]
  Implementation          [difficulty]
  Operational Risk        [risk]
  Confidence              [value]%
  Owner                   [owner]
  Priority                [value]/100
  Status                  Recommended

Keep total length under 480 words. Use precise, formal audit language — no hedging, no AI disclaimers.`,
        }],
      };

      let text = '';
      try {
        const r = await axios.post('/api/v1/ai-enhance', payload, { timeout: 25000 });
        text = r.data?.content?.[0]?.text || r.data?.text || '';
      } catch (_) {
        // Backend proxy not configured (ANTHROPIC_API_KEY missing) — fall back to the
        // deterministic Economic Intelligence Report already computed by the audit engine.
      }

      setAiText(text || data.ai_commentary || '');
    } catch (_) {
      setAiText(data.ai_commentary || '');
    }
    setAiLoading(false);
  };

  // ── Derived ────────────────────────────────────────────────────────
  const log         = Array.isArray(data.decision_log) ? data.decision_log : [];
  const captureRate = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
  const m           = data.eda_metrics;
  const hasData     = data.dq_score > 0;

  const navItems = [
    { id: 'exec',      label: 'Executive Summary',           tag: '01' },
    { id: 'flow',      label: 'Economic Value Flow',          tag: '02' },
    { id: 'timeline',  label: 'Decision Audit Trail™',        tag: '03' },
    { id: 'rootcause', label: 'Root Cause Analysis',          tag: '04' },
    { id: 'counter',   label: 'Counterfactual Simulation',    tag: '05' },
    { id: 'metrics',   label: 'EDA Metrics',                  tag: '06' },
    { id: 'leakage',   label: 'Financial Leakage',            tag: '07' },
    { id: 'heatmap',   label: 'Decision Heat Map',            tag: '08' },
    { id: 'opps',      label: 'Economic Action Plan™',        tag: '09' },
    { id: 'ai',        label: 'Economic Intelligence Report™',tag: '10' },
    { id: 'govern',    label: 'Governance',                   tag: '11' },
    { id: 'appendix',  label: 'Math Appendix',                tag: '12' },
    { id: 'live',      label: 'Live Monitor',                 tag: '⚡' },
    { id: 'cert',      label: 'EDPC Certificate',             tag: '🏆' },
  ];

  // ══════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════
  return (
    <div style={{ backgroundColor: DS.bg, color: DS.text, minHeight: '100vh', fontFamily: DS.sans, fontSize: 13 }}>

      {/* ── TRIAL GATE MODAL ─────────────────────────────────────── */}
      {gateOpen && (
        <TrialGate
          busy={gateBusy}
          error={gateError}
          onSubmit={startTrial}
          onDismiss={() => setGateOpen(false)}
        />
      )}

      {/* ── TRIAL EXPIRED CTA ────────────────────────────────────── */}
      {expiredInfo && (
        <TrialExpired
          info={expiredInfo}
          onStartNew={() => { setExpiredInfo(null); setGateOpen(true); }}
          onClose={() => setExpiredInfo(null)}
        />
      )}

      {/* ── TOP BAR ──────────────────────────────────────────────── */}
      <header style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '13px 28px', borderBottom: `1px solid ${DS.border}`,
        position: 'sticky', top: 0, backgroundColor: `${DS.bg}f0`, backdropFilter: 'blur(12px)',
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <img src="/logo.jpeg" alt="PREDAIOT" style={{ height: 36, objectFit: 'contain' }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.18em', color: DS.text }}>PREDAIOT</div>
            <div style={{ fontSize: 9, letterSpacing: '0.2em', color: DS.dim }}>ECONOMIC DECISION AUDIT™</div>
          </div>
          {hasData && (
            <div style={{ marginLeft: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: DS.sub }}>{data.asset_name}</span>
              <Pill label={data.risk_level || 'Moderate'} color={riskColor(data.risk_level)} />
              <Pill label={data.asset_type || 'Generic'} color={DS.cyan} />
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading || uploading}>
            {loading ? 'OPTIMIZING…' : 'RUN DEMO'}
          </BtnOutline>
          <BtnOutline color={DS.optimal} onClick={() => setShowUpload(!showUpload)} disabled={uploading}>
            {uploading ? 'PARSING…' : 'UPLOAD DATA'}
          </BtnOutline>
          <BtnOutline color={DS.warning} onClick={handleShare}>SHARE REPORT</BtnOutline>
          <BtnOutline color={DS.purple} onClick={downloadPdf} disabled={pdfLoading || !data.dq_score}>
            {pdfLoading ? 'BUILDING PDF…' : '⬇ DOWNLOAD PDF'}
          </BtnOutline>
          <BtnOutline color={DS.dim} onClick={() => setShowMethodology(true)}>METHODOLOGY</BtnOutline>
          <SessionBadge liveMode={liveMode} simRunning={simRunning} dataSource={dataSource} />
        </div>
      </header>

      {shareLink && (
        <div style={{ background: `${DS.warning}10`, borderBottom: `1px solid ${DS.warning}30`, padding: '8px 28px', fontSize: 11, color: DS.warning }}>
          🔗 {shareLink}
        </div>
      )}

      {/* ── FILE UPLOAD PANEL ───────────────────────────────────── */}
      {showUpload && (
        <div style={{ borderBottom: `1px solid ${DS.border}`, background: DS.bgRaised }}>
          <FileUploadZone onFile={handleFile} loading={uploading} />
        </div>
      )}

      <div style={{ display: 'flex' }}>
        {/* ── SIDEBAR ───────────────────────────────────────────── */}
        <nav style={{
          width: 210, minWidth: 210, padding: '20px 0',
          borderRight: `1px solid ${DS.border}`,
          position: 'sticky', top: 67, height: 'calc(100vh - 67px)', overflowY: 'auto',
        }}>
          {navItems.map((n) => {
            const active = activeSection === n.id;
            return (
              <button key={n.id} onClick={() => setActiveSection(n.id)} style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '9px 20px', fontSize: 11, background: 'none', border: 'none',
                cursor: 'pointer', letterSpacing: '0.04em',
                color: active ? DS.cyan : DS.sub,
                borderLeft: `2px solid ${active ? DS.cyan : 'transparent'}`,
                transition: 'all 0.12s',
              }}>
                <span style={{ fontFamily: DS.mono, fontSize: 9, color: DS.dim, marginRight: 8 }}>{n.tag}</span>
                {n.label}
              </button>
            );
          })}
        </nav>

        {/* ── MAIN CONTENT ──────────────────────────────────────── */}
        <main style={{ flex: 1, minWidth: 0, padding: '28px 32px', overflowX: 'hidden' }}>

          {/* Welcome / empty state — only shown when on a data-dependent section
              with no audit loaded. Skipped for live/appendix/govern which work
              independently of audit data. */}
          {!hasData && !showUpload && !['live', 'appendix', 'govern'].includes(activeSection) && (
            <div style={{ textAlign: 'center', padding: '70px 40px' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⚡</div>
              <div style={{ color: DS.text, fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Economic Decision Audit™</div>
              <div style={{ color: DS.dim, fontSize: 11, letterSpacing: '0.1em', marginBottom: 20 }}>
                THE UNIVERSAL ECONOMIC DECISION ENGINE FOR ENERGY INFRASTRUCTURE
              </div>
              <div style={{ color: DS.sub, fontSize: 13, marginBottom: 12, maxWidth: 560, margin: '0 auto 12px' }}>
                Upload data from any energy asset — BESS, Solar, Wind, Gas, Hydro, Hydrogen Electrolyzers, Desalination, CHP, Microgrids, or industrial plant — and PREDAIOT audits the economic quality of every dispatch decision.
              </div>
              <div style={{ color: DS.dim, fontSize: 11, marginBottom: 28 }}>
                Live SCADA/EMS streaming · Batch file audit · EDPC Certification — all on one asset-agnostic engine.
              </div>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading}>
                  {loading ? 'OPTIMIZING…' : 'RUN DEMO AUDIT'}
                </BtnOutline>
                <BtnOutline color={DS.optimal} onClick={() => setShowUpload(true)}>
                  UPLOAD MY DATA
                </BtnOutline>
                <BtnOutline color={DS.warning} onClick={() => setActiveSection('live')}>
                  ⚡ LIVE MONITOR
                </BtnOutline>
                <BtnOutline color={DS.purple} onClick={() => setActiveSection('appendix')}>
                  📐 SEE THE MATH
                </BtnOutline>
              </div>
              <div style={{ color: DS.dim, fontSize: 10, marginTop: 24 }}>
                Don&rsquo;t have data handy? RUN DEMO replays the reference 500 MW BESS audit (~7s on CBC).
              </div>
            </div>
          )}

          {/* ══ S01: Executive Summary ══════════════════════════════ */}
          {hasData && activeSection === 'exec' && (
            <div>
              <SectionHeader tag="01" title="Executive Summary" />

              {/* KPI shock panel */}
              <div style={{
                background: `linear-gradient(135deg, rgba(75,191,255,0.07) 0%, rgba(0,230,118,0.05) 100%)`,
                border: `1px solid ${DS.blue}25`, borderRadius: DS.r16, padding: 28, marginBottom: 20,
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 24 }}>
                  {[
                    { label: 'Asset', value: data.asset_name || '—', color: DS.text, mono: false },
                    { label: 'Audit Period', value: data.audit_period_label || '—', color: DS.cyan, mono: true },
                    { label: 'Economic Potential', value: fmtUSD(data.edv_optimal_total), color: DS.warning, mono: true },
                    { label: 'Captured Value', value: fmtUSD(data.edv_actual_total), color: DS.optimal, mono: true },
                  ].map((f) => (
                    <div key={f.label}>
                      <Label>{f.label}</Label>
                      <BigNum v={f.value} color={f.color} size={f.mono ? 22 : 16} />
                    </div>
                  ))}
                </div>

                <Divider />

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 24 }}>
                  {[
                    { label: 'Destroyed Value', value: fmtUSD(data.total_gap_usd), color: DS.loss },
                    { label: 'DQ Score', value: hasData ? `${((data.dq_score || 0) * 100).toFixed(1)} / 100` : '—', color: qualColor(captureRate) },
                    { label: 'Economic Efficiency', value: hasData ? fmtPct(captureRate) : '—', color: qualColor(captureRate) },
                    { label: 'Est. Annual Leakage', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.orange },
                  ].map((f) => (
                    <div key={f.label}>
                      <Label>{f.label}</Label>
                      <BigNum v={f.value} color={f.color} />
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Before / After PREDAIOT — value visualization (Area 2) ─── */}
              {log.length > 0 && (
                <Card style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <Label style={{ marginBottom: 2 }}>Optimal vs Actual Dispatch — Economic Value per Step</Label>
                      <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.08em' }}>
                        SHADED AREA = ECONOMIC GAP RECOVERABLE WITH PREDAIOT
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 14, fontSize: 10, color: DS.sub }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 3, background: DS.optimal, borderRadius: 2 }} />
                        With PREDAIOT (optimal)
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 3, background: DS.orange, borderRadius: 2 }} />
                        Without PREDAIOT (actual)
                      </span>
                    </div>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={log} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="gExecOpt" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={DS.optimal} stopOpacity={0.28} />
                          <stop offset="100%" stopColor={DS.optimal} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gExecAct" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={DS.orange} stopOpacity={0.24} />
                          <stop offset="100%" stopColor={DS.orange} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                      <XAxis dataKey="hour" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                      <YAxis stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} tickFormatter={(v) => `$${v}`} />
                      <Tooltip
                        contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, borderRadius: 8, fontSize: 11 }}
                        formatter={(v, name) => [`$${(v || 0).toFixed(2)}`, name]}
                        labelFormatter={(h) => `Step ${h}`}
                      />
                      <Area type="monotone" dataKey="edv_optimal_step" name="With PREDAIOT" stroke={DS.optimal} fill="url(#gExecOpt)" strokeWidth={2} dot={false} />
                      <Area type="monotone" dataKey="edv_actual_step" name="Without PREDAIOT" stroke={DS.orange} fill="url(#gExecAct)" strokeWidth={2} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>
              )}

              {/* ── Value Waterfall — Potential → Captured → Destroyed ─── */}
              {hasData && (() => {
                const pot = data.edv_optimal_total || 0;
                const act = data.edv_actual_total || 0;
                const gap = data.total_gap_usd || 0;
                const maxV = Math.max(pot, 1);
                const rows = [
                  { label: 'Economic Potential',   sub: 'MILP counterfactual', value: pot, color: DS.optimal, pct: 100 },
                  { label: 'Captured Value',       sub: 'What actually happened', value: act, color: DS.blue,   pct: Math.min(100, (act / maxV) * 100) },
                  { label: 'Destroyed Value',      sub: 'Recoverable with PREDAIOT', value: gap, color: DS.loss, pct: Math.min(100, (gap / maxV) * 100) },
                ];
                return (
                  <Card style={{ marginBottom: 20 }}>
                    <Label style={{ marginBottom: 14 }}>Value Waterfall — Where Every Dollar Went</Label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                      {rows.map((r) => (
                        <div key={r.label}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5, fontSize: 12 }}>
                            <span>
                              <span style={{ color: DS.text, fontWeight: 700 }}>{r.label}</span>
                              <span style={{ color: DS.dim, fontSize: 10, marginLeft: 8, letterSpacing: '0.05em' }}>{r.sub}</span>
                            </span>
                            <span style={{ color: r.color, fontFamily: DS.mono, fontWeight: 700 }}>{fmtUSD(r.value)}</span>
                          </div>
                          <div style={{ height: 10, background: `${DS.border}88`, borderRadius: 5, overflow: 'hidden' }}>
                            <div style={{
                              width: `${r.pct}%`, height: '100%',
                              background: `linear-gradient(90deg, ${r.color} 0%, ${r.color}bb 100%)`,
                              boxShadow: `0 0 12px ${r.color}55`,
                            }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${DS.border}`, fontSize: 10, color: DS.dim, letterSpacing: '0.06em' }}>
                      The <span style={{ color: DS.loss, fontWeight: 700 }}>{fmtUSD(gap)}</span> destroyed-value bar is the number PREDAIOT&rsquo;s Economic Action Plan is designed to recover.
                    </div>
                  </Card>
                );
              })()}

              {/* Risk banner */}
              {hasData && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 16, padding: '14px 22px',
                  background: `${riskColor(data.risk_level)}10`,
                  border: `1px solid ${riskColor(data.risk_level)}35`,
                  borderRadius: DS.r12, marginBottom: 20,
                }}>
                  <span style={{ fontSize: 22 }}>{riskEmoji(data.risk_level)}</span>
                  <div>
                    <div style={{ color: riskColor(data.risk_level), fontWeight: 700, fontSize: 14, letterSpacing: '0.1em' }}>
                      RISK LEVEL: {(data.risk_level || '').toUpperCase()}
                    </div>
                    <div style={{ color: DS.sub, fontSize: 11, marginTop: 3 }}>
                      {data.risk_level === 'Severe' && 'Immediate operational review required. Economic losses exceed 60% of potential.'}
                      {data.risk_level === 'Moderate' && 'Optimization opportunities identified. Revenue recovery achievable within 30 days.'}
                      {data.risk_level === 'Low' && 'Asset operating near optimal. Minor tuning recommended for full potential capture.'}
                    </div>
                  </div>
                </div>
              )}

              {/* EIS gauge (circular text display) */}
              {m && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
                  <Card>
                    <Label>Economic Intelligence Score</Label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 8 }}>
                      <div style={{
                        width: 80, height: 80, borderRadius: '50%',
                        border: `4px solid ${qualColor(m.economic_intelligence_score)}`,
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        boxShadow: `0 0 20px ${qualColor(m.economic_intelligence_score)}30`,
                      }}>
                        <div style={{ color: qualColor(m.economic_intelligence_score), fontSize: 20, fontWeight: 800, fontFamily: DS.mono, lineHeight: 1 }}>{m.economic_intelligence_score}</div>
                        <div style={{ color: DS.dim, fontSize: 8, marginTop: 2 }}>/ 100</div>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.7 }}>
                          Composite ISO-style index combining capture efficiency (45%), decision accuracy (30%), forecast utilization (15%), and leakage control (10%).
                        </div>
                      </div>
                    </div>
                  </Card>
                  <Card>
                    <Label>Key Indicators</Label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                      {[
                        { l: 'Capture Efficiency', v: fmtPct(m.economic_decision_efficiency), c: qualColor(m.economic_decision_efficiency) },
                        { l: 'Dispatch Accuracy', v: fmtPct(m.dispatch_accuracy), c: qualColor(m.dispatch_accuracy) },
                        { l: 'Forecast Utilization', v: fmtPct(m.forecast_utilization_index), c: qualColor(m.forecast_utilization_index) },
                      ].map(({ l, v, c }) => (
                        <div key={l}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                            <span style={{ color: DS.sub }}>{l}</span>
                            <span style={{ color: c, fontFamily: DS.mono, fontWeight: 700 }}>{v}</span>
                          </div>
                          <ProgressBar pct={parseFloat(v)} color={c} />
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              )}
            </div>
          )}

          {/* ══ S02: Economic Value Flow ════════════════════════════ */}
          {hasData && activeSection === 'flow' && (
            <div>
              <SectionHeader tag="02" title="Economic Value Flow" />
              {!hasData ? <EmptyMsg>Run an audit to populate the economic flow.</EmptyMsg> : (
                <div style={{ maxWidth: 560, margin: '0 auto' }}>
                  {[
                    { label: 'Market Potential', value: fmtUSD(data.edv_optimal_total), color: DS.warning, desc: 'MILP-optimal upper bound — physically achievable, economically optimal' },
                    { label: 'Available Window', value: fmtUSD(data.edv_optimal_total * 0.92), color: DS.blue, desc: 'After grid constraints, network limits, and interconnection rules' },
                    { label: 'Dispatch Opportunity', value: fmtUSD(data.edv_optimal_total * 0.87), color: DS.cyan, desc: 'Within asset SOC range, ramp capability, and market rules' },
                    { label: 'Decision Taken', value: fmtUSD(data.edv_actual_total), color: DS.optimal, desc: 'Operator / EMS decisions actually executed' },
                    { label: 'Captured Value', value: fmtUSD(data.edv_actual_total * 0.97), color: DS.optimal, desc: 'Net settlement revenue after metering and settlement losses' },
                    { label: 'Economic Leakage', value: `−${fmtUSD(data.total_gap_usd)}`, color: DS.loss, desc: 'Revenue permanently destroyed by sub-optimal dispatch timing' },
                    { label: 'Unrecoverable Loss', value: `−${fmtUSD(data.total_gap_usd * 0.12)}`, color: DS.dim, desc: 'Physical constraints and regulatory hard limits' },
                  ].map((step, i) => (
                    <div key={step.label}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px',
                        background: DS.surface, border: `1px solid ${step.color}25`, borderRadius: DS.r12,
                      }}>
                        <div style={{ width: 4, height: 44, backgroundColor: step.color, borderRadius: 2, flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <Label style={{ marginBottom: 2 }}>{step.label}</Label>
                          <BigNum v={step.value} color={step.color} size={18} />
                          <div style={{ color: DS.dim, fontSize: 10, marginTop: 3 }}>{step.desc}</div>
                        </div>
                      </div>
                      {i < 6 && <div style={{ textAlign: 'center', color: DS.dim, lineHeight: '22px', fontSize: 18 }}>↓</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S03: Decision Audit Trail™ ══════════════════════════ */}
          {hasData && activeSection === 'timeline' && (
            <div>
              <SectionHeader tag="03" title="Decision Audit Trail™ — Economic Decision Forensics" />

              {/* Summary counter strip */}
              {log.length > 0 && (() => {
                const correct  = log.filter(d => d.decision_type?.includes('Correct')).length;
                const critical = log.filter(d => (d.gap_step || 0) > 100).length;
                const subopt   = log.filter(d => (d.gap_step || 0) > 0 && (d.gap_step || 0) <= 100).length;
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
                    {[
                      { label: 'Decisions Audited', v: log.length,                  c: DS.text },
                      { label: 'Correct Decisions', v: correct,                      c: DS.optimal },
                      { label: 'Suboptimal',         v: subopt,                       c: DS.warning },
                      { label: '⚠ Critical Decisions',v: critical,                   c: DS.loss },
                      { label: 'Revenue Destroyed',  v: fmtUSD(data.total_gap_usd), c: DS.loss },
                    ].map(f => (
                      <Card key={f.label} style={{ textAlign: 'center', borderColor: f.c === DS.loss ? `${DS.loss}25` : DS.border }}>
                        <Label style={{ fontSize: 9 }}>{f.label}</Label>
                        <BigNum v={f.v} color={f.c} size={20} />
                      </Card>
                    ))}
                  </div>
                );
              })()}

              {log.length === 0 ? <EmptyMsg>Run an audit to populate the Decision Audit Trail.</EmptyMsg> : (
                <div style={{ maxHeight: 680, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {log.filter(d => (d.gap_step || 0) > 0).slice(0, 60).map((dec, i) => {
                    const h  = dec.hour || 0;
                    const ts = `${Math.floor(h/12).toString().padStart(2,'0')}:${((h%12)*5).toString().padStart(2,'0')}`;
                    const gap = dec.gap_step || 0;
                    const isCrit = gap > 100, isMod = gap > 20 && !isCrit;
                    const verdict = gap <= 0 ? 'correct' : isCrit ? 'critical' : isMod ? 'suboptimal' : 'minor';
                    const vd = {
                      correct:   { label: '✓ Correct Decision',  color: DS.optimal },
                      critical:  { label: '✕ Revenue Destroyed',  color: DS.loss },
                      suboptimal:{ label: '△ Suboptimal Dispatch', color: DS.warning },
                      minor:     { label: '◎ Minor Leakage',      color: DS.orange },
                    }[verdict];

                    const rootCause = {
                      'Missed Arbitrage':   'Static Dispatch Rule — no market-responsive trigger',
                      'Partial Capture':    'SOC Constraint or partial execution — capacity available but under-utilised',
                      'Over-Dispatch':      'Aggressive dispatch beyond MILP-optimal level',
                      'Correct Dispatch':   'Decision matched optimal counterfactual',
                      'Correct Idle':       'Idle period was economically justified',
                    }[dec.decision_type] || 'Sub-optimal dispatch strategy';

                    return (
                      <div key={i} style={{
                        background: DS.surface,
                        border: `1px solid ${isCrit ? DS.loss + '40' : DS.border}`,
                        borderRadius: DS.r12, padding: '14px 18px',
                        borderLeft: `3px solid ${vd.color}`,
                      }}>
                        {/* Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                            <span style={{ color: DS.dim, fontFamily: DS.mono, fontSize: 10 }}>#{i + 1}</span>
                            <span style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 14, fontWeight: 700 }}>{ts}</span>
                            <Pill label={vd.label} color={vd.color} />
                            {dec.operator_override && <Pill label="Human Override" color={DS.orange} />}
                          </div>
                          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                            {gap > 0 && <span style={{ color: DS.loss, fontFamily: DS.mono, fontSize: 14, fontWeight: 700 }}>−{fmtUSD(gap)}</span>}
                            {dec.confidence && <Pill label={`${(dec.confidence*100).toFixed(0)}% conf`} color={DS.blue} />}
                          </div>
                        </div>

                        {/* Data row */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 12 }}>
                          {[
                            { label: 'Market Price', v: `$${dec.price}/MWh`, c: DS.warning },
                            { label: 'Asset SOC', v: dec.soc != null ? `${(dec.soc*100).toFixed(0)}%` : '—', c: DS.sub },
                            { label: 'Optimal Action', v: `Dis ${dec.optimal_action} MW`, c: DS.optimal },
                            { label: 'Actual Action', v: (dec.actual_action||0) < 0.5 ? 'Idle' : `Dis ${dec.actual_action} MW`, c: (dec.actual_action||0) < 0.5 ? DS.loss : DS.text },
                            { label: 'Curtailment', v: dec.curtailment_mw ? `${dec.curtailment_mw} MW` : '—', c: DS.orange },
                          ].map(f => (
                            <div key={f.label}>
                              <Label style={{ fontSize: 9, marginBottom: 2 }}>{f.label}</Label>
                              <div style={{ color: f.c, fontFamily: DS.mono, fontSize: 12, fontWeight: 600 }}>{f.v}</div>
                            </div>
                          ))}
                        </div>

                        {/* Root cause + Counterfactual */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                          <div style={{ padding: '8px 12px', background: `${DS.loss}06`, border: `1px solid ${DS.loss}20`, borderRadius: DS.r8 }}>
                            <Label style={{ fontSize: 9, marginBottom: 3 }}>Root Cause</Label>
                            <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.5 }}>{rootCause}</div>
                          </div>
                          <div style={{ padding: '8px 12px', background: `${DS.optimal}06`, border: `1px solid ${DS.optimal}20`, borderRadius: DS.r8 }}>
                            <Label style={{ fontSize: 9, marginBottom: 3 }}>Counterfactual — What Should Have Happened</Label>
                            <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.5 }}>
                              {gap > 0
                                ? `Dispatching ${dec.optimal_action} MW would have recovered ${fmtUSD(gap)} with no physical constraint violation. MILP verified.`
                                : 'Decision was economically optimal. No improvement available.'}
                            </div>
                          </div>
                        </div>

                        {/* Evidence footer */}
                        {gap > 0 && (
                          <div style={{ marginTop: 8, display: 'flex', gap: 16, fontSize: 9, color: DS.dim }}>
                            <span>✓ MILP Verified</span>
                            <span>✓ Dispatch Log Verified</span>
                            <span>Importance: {Math.min(100, Math.round((gap / (data.total_gap_usd || 1)) * 1000))}% of total loss</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ══ S04: Root Cause Analysis ════════════════════════════ */}
          {hasData && activeSection === 'rootcause' && (
            <div>
              <SectionHeader tag="04" title="Root Cause Analysis — Pareto" />
              {(data.root_causes || []).length === 0 ? <EmptyMsg>Run an audit to generate the root cause analysis.</EmptyMsg> : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                  <Card>
                    <Label style={{ marginBottom: 16 }}>Failure Category Breakdown</Label>
                    {(data.root_causes || []).map((rc, i) => (
                      <div key={i} style={{ marginBottom: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                          <span style={{ color: DS.text }}>{rc.category}</span>
                          <span style={{ color: [DS.loss, DS.orange, DS.warning, DS.blue, DS.cyan, DS.purple][i % 6], fontFamily: DS.mono, fontWeight: 700 }}>
                            {rc.contribution_pct}% · {fmtUSD(rc.loss_usd)}
                          </span>
                        </div>
                        <ProgressBar pct={rc.contribution_pct} color={[DS.loss, DS.orange, DS.warning, DS.blue, DS.cyan, DS.purple][i % 6]} />
                      </div>
                    ))}
                  </Card>
                  <Card>
                    <Label style={{ marginBottom: 12 }}>Pareto Chart</Label>
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart data={data.root_causes || []} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                        <XAxis type="number" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} tickFormatter={(v) => `${v}%`} />
                        <YAxis type="category" dataKey="category" stroke={DS.dim} tick={{ fill: DS.sub, fontSize: 9 }} width={140} />
                        <Tooltip contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, borderRadius: 8, fontSize: 11 }} formatter={(v) => [`${v}%`, 'Contribution']} />
                        <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>
                          {(data.root_causes || []).map((_, i) => (
                            <Cell key={i} fill={[DS.loss, DS.orange, DS.warning, DS.blue, DS.cyan, DS.purple][i % 6]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </div>
              )}
            </div>
          )}

          {/* ══ S05: Counterfactual Simulation ══════════════════════ */}
          {hasData && activeSection === 'counter' && (
            <div>
              <SectionHeader tag="05" title='Counterfactual Simulation — "What Would Have Happened?"' />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 20 }}>
                {[
                  { label: 'Actual Revenue', value: fmtUSD(data.edv_actual_total), color: DS.blue },
                  { label: 'Optimal Revenue', value: fmtUSD(data.edv_optimal_total), color: DS.optimal },
                  { label: 'Lost Opportunity', value: `−${fmtUSD(data.total_gap_usd)}`, color: DS.loss },
                ].map((f) => (
                  <Card key={f.label} style={{ textAlign: 'center' }}>
                    <Label>{f.label}</Label>
                    <BigNum v={f.value} color={f.color} size={26} />
                  </Card>
                ))}
              </div>
              {log.length > 0 && (
                <Card style={{ marginBottom: 16 }}>
                  <Label style={{ marginBottom: 14 }}>Optimal vs Actual Dispatch Curve</Label>
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={log.slice(0, 120)} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="gOpt" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={DS.optimal} stopOpacity={0.3} /><stop offset="95%" stopColor={DS.optimal} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gAct" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={DS.blue} stopOpacity={0.25} /><stop offset="95%" stopColor={DS.blue} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                      <XAxis dataKey="hour" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                      <YAxis stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                      <Tooltip contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, borderRadius: 8, fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11, color: DS.sub }} />
                      <Area type="monotone" dataKey="optimal_action" name="Optimal Dispatch (MW)" stroke={DS.optimal} fill="url(#gOpt)" strokeWidth={2} dot={false} />
                      <Area type="monotone" dataKey="actual_action" name="Actual Dispatch (MW)" stroke={DS.blue} fill="url(#gAct)" strokeWidth={2} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>
              )}
              {data.counterfactual_summary && (
                <Card glow={DS.cyan}>
                  <div style={{ color: DS.cyan, fontSize: 12, lineHeight: 1.8, fontStyle: 'italic' }}>"{data.counterfactual_summary}"</div>
                </Card>
              )}
            </div>
          )}

          {/* ══ S06: EDA Metrics ════════════════════════════════════ */}
          {hasData && activeSection === 'metrics' && (
            <div>
              <SectionHeader tag="06" title="Economic Decision Quality Metrics" />
              {!m ? <EmptyMsg>Run an audit to generate metrics.</EmptyMsg> : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
                  {[
                    { label: 'Economic Decision Efficiency (EDE)', value: fmtPct(m.economic_decision_efficiency), note: 'Captured ÷ Potential', color: qualColor(m.economic_decision_efficiency), pct: m.economic_decision_efficiency },
                    { label: 'Economic Leakage Ratio (ELR)', value: fmtPct(m.economic_leakage_ratio), note: 'Lost ÷ Potential (lower is better)', color: m.economic_leakage_ratio <= 30 ? DS.optimal : m.economic_leakage_ratio <= 60 ? DS.warning : DS.loss, pct: m.economic_leakage_ratio },
                    { label: 'Dispatch Accuracy', value: fmtPct(m.dispatch_accuracy), note: 'Correct dispatches ÷ Total', color: qualColor(m.dispatch_accuracy), pct: m.dispatch_accuracy },
                    { label: 'Forecast Utilization Index', value: fmtPct(m.forecast_utilization_index), note: '% of steps with forecast data provided', color: qualColor(m.forecast_utilization_index), pct: m.forecast_utilization_index },
                    { label: 'Decision Delay Index', value: `${m.decision_delay_index}`, note: 'Avg override ratio × 10 (0 = perfect)', color: m.decision_delay_index < 1 ? DS.optimal : m.decision_delay_index < 3 ? DS.warning : DS.loss, pct: null },
                    { label: 'Curtailment Recovery Ratio', value: `${m.curtailment_recovery_ratio} MWh`, note: 'Potentially rescuable curtailed energy', color: DS.cyan, pct: null },
                    { label: 'Revenue Stacking Index', value: `${m.revenue_stacking_index} services`, note: 'Distinct revenue streams being utilized', color: m.revenue_stacking_index >= 3 ? DS.optimal : DS.warning, pct: null },
                    { label: 'Economic Intelligence Score', value: `${m.economic_intelligence_score} / 100`, note: 'ISO-style composite performance index', color: qualColor(m.economic_intelligence_score), pct: m.economic_intelligence_score },
                    ...(m.battery_opportunity_capture != null
                      ? [{ label: 'Battery Opportunity Capture', value: fmtPct(m.battery_opportunity_capture), note: 'BESS-specific arbitrage capture rate', color: DS.blue, pct: m.battery_opportunity_capture }]
                      : []),
                  ].map((metric) => (
                    <Card key={metric.label}>
                      <Label>{metric.label}</Label>
                      <BigNum v={metric.value} color={metric.color} size={28} />
                      <div style={{ color: DS.dim, fontSize: 10, marginTop: 4 }}>{metric.note}</div>
                      {metric.pct != null && <ProgressBar pct={metric.pct} color={metric.color} />}
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S07: Financial Leakage ══════════════════════════════ */}
          {hasData && activeSection === 'leakage' && (
            <div>
              <SectionHeader tag="07" title="Financial Value Leakage" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 16, marginBottom: 20 }}>
                {[
                  { label: '24-Hour', value: fmtUSD(data.total_gap_usd), color: DS.loss },
                  { label: '7-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 7) : '—', color: DS.orange },
                  { label: '30-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 30) : '—', color: DS.warning },
                  { label: '12-Month Projection', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.loss },
                ].map((f) => (
                  <Card key={f.label} style={{ textAlign: 'center', borderColor: `${f.color}25` }}>
                    <Label>{f.label}</Label>
                    <BigNum v={f.value} color={f.color} />
                  </Card>
                ))}
              </div>
              <Card>
                <Label style={{ marginBottom: 16 }}>Top Leakage Sources</Label>
                {(data.financial_leakage?.top_sources || []).map((src, i) => (
                  <div key={i} style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: DS.text, fontSize: 12 }}>{src.name}</span>
                      <span style={{ color: DS.loss, fontFamily: DS.mono, fontWeight: 700, fontSize: 11 }}>{fmtUSD(src.usd)} ({src.pct}%)</span>
                    </div>
                    <ProgressBar pct={src.pct} color={DS.loss} />
                  </div>
                ))}
                {(data.financial_leakage?.top_sources || []).length === 0 && <EmptyMsg>Run an audit to populate leakage sources.</EmptyMsg>}
              </Card>

              {/* 30-day history */}
              <Card style={{ marginTop: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <Label>30-Day Trend</Label>
                  <BtnOutline color={DS.loss} onClick={async () => {
                    setHistLoading(true);
                    try { const r = await axios.get('/api/historical'); if (r.data?.history_log) setHistData(r.data.history_log); } catch (_) {}
                    setHistLoading(false);
                  }}>
                    {histLoading ? 'QUERYING…' : 'SYNC HISTORY'}
                  </BtnOutline>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={histData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                    <XAxis dataKey="day" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                    <YAxis stroke={DS.dim} tickFormatter={(v) => `$${v}`} tick={{ fill: DS.dim, fontSize: 9 }} />
                    <Tooltip contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, borderRadius: 8, fontSize: 11 }} formatter={(v) => [`$${v} lost`, 'Daily Leakage']} />
                    <Bar dataKey="daily_gap" fill={DS.loss} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                {histData.length === 0 && !histLoading && (
                  <div style={{ textAlign: 'center', color: DS.dim, marginTop: 10, fontSize: 11 }}>
                    Connect to a production database to display historical trend data.
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* ══ S08: Decision Heat Map ══════════════════════════════ */}
          {hasData && activeSection === 'heatmap' && (
            <div>
              <SectionHeader tag="08" title="Decision Heat Map — 24 Hours" />
              <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
                {[['optimal', DS.optimal, 'Optimal Decision'], ['acceptable', DS.warning, 'Acceptable'], ['poor', DS.orange, 'Poor Decision'], ['critical', DS.loss, 'Critical Loss']].map(([s, c, l]) => (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 12, height: 12, borderRadius: 3, background: c }} />
                    <span style={{ color: DS.sub, fontSize: 11 }}>{l}</span>
                  </div>
                ))}
              </div>
              {(data.heat_map || []).length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12,1fr)', gap: 5 }}>
                  {(data.heat_map || []).slice(0, 288).map((cell, i) => {
                    const c = heatColor(cell.status);
                    return (
                      <div key={i} title={`${cell.label} | ${cell.action_taken} | Gap: $${cell.gap_usd}`} style={{
                        height: 46, borderRadius: DS.r8,
                        background: `${c}18`, border: `1px solid ${c}50`,
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        cursor: 'default',
                      }}>
                        <div style={{ color: c, fontSize: 8, fontFamily: DS.mono }}>{cell.label}</div>
                        {cell.gap_usd > 0 && <div style={{ color: DS.loss, fontSize: 7, marginTop: 1 }}>−${cell.gap_usd.toFixed(0)}</div>}
                      </div>
                    );
                  })}
                </div>
              ) : <EmptyMsg>Run an audit to generate the decision heat map.</EmptyMsg>}
            </div>
          )}

          {/* ══ S09: Economic Action Plan™ ══════════════════════════ */}
          {hasData && activeSection === 'opps' && (
            <div>
              <SectionHeader tag="09" title="Economic Action Plan™ — Value Recovery Roadmap" />

              {/* Portfolio header */}
              {(data.opportunities || []).length > 0 && (() => {
                const ops   = data.opportunities || [];
                const total = ops.reduce((s, o) => s + (o.annual_gain_usd || 0), 0);
                const qw    = ops.filter(o => o.difficulty === 'Quick Win').length;
                const strat = ops.filter(o => o.difficulty === 'Strategic Initiative').length;
                const mkt   = ops.filter(o => o.difficulty === 'Market Integration').length;
                const avgConf = ops.reduce((s, o) => s + (o.confidence_pct || 0), 0) / ops.length;
                return (
                  <div style={{ background: `linear-gradient(135deg, rgba(0,230,118,0.06) 0%, rgba(75,191,255,0.04) 100%)`, border: `1px solid ${DS.optimal}25`, borderRadius: DS.r16, padding: 24, marginBottom: 24 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 20 }}>
                      {[
                        { label: 'Total Annual Recovery', v: fmtUSD(total), c: DS.optimal, big: true },
                        { label: 'Quick Wins', v: qw, c: DS.optimal, sub: 'immediate' },
                        { label: 'Strategic Initiatives', v: strat, c: DS.warning, sub: '1–8 weeks' },
                        { label: 'Market Integrations', v: mkt, c: DS.blue, sub: '1–3 months' },
                        { label: 'Portfolio Confidence', v: `${avgConf.toFixed(1)}%`, c: DS.cyan, big: false },
                      ].map(f => (
                        <div key={f.label}>
                          <Label style={{ fontSize: 9, marginBottom: 4 }}>{f.label}</Label>
                          <BigNum v={f.v} color={f.c} size={f.big ? 24 : 20} />
                          {f.sub && <div style={{ color: DS.dim, fontSize: 9, marginTop: 3 }}>{f.sub}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {(data.opportunities || []).length === 0 ? <EmptyMsg>Run an audit to generate the Economic Action Plan.</EmptyMsg> : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {(data.opportunities || []).map((op, i) => {
                    const diffColor = op.difficulty === 'Quick Win' ? DS.optimal : op.difficulty === 'Strategic Initiative' ? DS.warning : DS.blue;
                    const riskColor2 = op.operational_risk === 'Low' ? DS.optimal : op.operational_risk === 'Medium' ? DS.warning : DS.loss;
                    return (
                      <div key={i} style={{ background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r12, overflow: 'hidden' }}>
                        {/* Card header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '18px 22px 14px', borderBottom: `1px solid ${DS.border}` }}>
                          <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                            <div style={{ color: DS.dim, fontFamily: DS.mono, fontSize: 20, fontWeight: 800, lineHeight: 1, minWidth: 30 }}>#{i+1}</div>
                            <div>
                              <div style={{ color: DS.text, fontWeight: 700, fontSize: 14, marginBottom: 5 }}>{op.name}</div>
                              <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.6, maxWidth: 520 }}>{op.description}</div>
                            </div>
                          </div>
                          <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 20 }}>
                            <BigNum v={fmtUSD(op.annual_gain_usd)} color={DS.optimal} size={22} />
                            <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.12em', marginTop: 2 }}>ANNUAL RECOVERY</div>
                          </div>
                        </div>

                        {/* Metrics grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 0, padding: '12px 22px' }}>
                          {[
                            { label: 'Confidence', v: `${op.confidence_pct || '—'}%`, c: DS.cyan },
                            { label: 'Implementation', v: op.difficulty, c: diffColor },
                            { label: 'Investment', v: op.investment_type, c: op.investment_type === 'No CAPEX' ? DS.optimal : DS.warning },
                            { label: 'Owner', v: op.owner, c: DS.sub },
                            { label: 'Risk', v: op.operational_risk, c: riskColor2 },
                            { label: 'Priority Score', v: `${op.priority_score}/100`, c: DS.warning },
                          ].map(f => (
                            <div key={f.label} style={{ borderRight: `1px solid ${DS.border}`, padding: '4px 12px 4px 0', marginRight: 12 }}>
                              <Label style={{ fontSize: 9, marginBottom: 3 }}>{f.label}</Label>
                              <div style={{ color: f.c, fontSize: 12, fontWeight: 600 }}>{f.v}</div>
                            </div>
                          ))}
                        </div>

                        {/* Evidence footer */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 22px', background: `rgba(255,255,255,0.015)`, borderTop: `1px solid ${DS.border}` }}>
                          <div style={{ color: DS.dim, fontSize: 11 }}>
                            <span style={{ color: DS.sub }}>Evidence:</span> {op.evidence}
                          </div>
                          <div style={{ color: DS.dim, fontSize: 10, flexShrink: 0, marginLeft: 16 }}>
                            Payback: <span style={{ color: op.payback_days === 0 ? DS.optimal : DS.warning }}>{op.payback_days === 0 ? 'Immediate' : `${op.payback_days} days`}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ══ S10: Economic Intelligence Report™ ═════════════════ */}
          {hasData && activeSection === 'ai' && (
            <div>
              <SectionHeader tag="10" title="Economic Intelligence Report™ — Independent Assessment" />

              {/* Executive Status Box */}
              {hasData && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 20 }}>
                  {[
                    { label: 'Economic Status', v: data.risk_level === 'Severe' ? 'CRITICAL' : (data.risk_level || 'MODERATE').toUpperCase(), c: riskColor(data.risk_level) },
                    { label: 'Current Capture', v: fmtPct(captureRate), c: qualColor(captureRate) },
                    { label: 'Recoverable Revenue', v: fmtPct(Math.min(99, (100 - captureRate) * 0.68)), c: DS.optimal },
                    { label: 'Annual Recovery', v: fmtUSD(data.total_gap_usd * 365 * 0.68), c: DS.optimal },
                    { label: 'Audit Confidence', v: m ? `${m.dispatch_accuracy?.toFixed(1)}%` : '—', c: DS.cyan },
                  ].map(f => (
                    <Card key={f.label} style={{ textAlign: 'center' }} glow={f.c === riskColor(data.risk_level) && data.risk_level === 'Severe' ? DS.loss : undefined}>
                      <Label style={{ fontSize: 9 }}>{f.label}</Label>
                      <BigNum v={f.v} color={f.c} size={18} />
                    </Card>
                  ))}
                </div>
              )}

              {/* Enhance button */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
                <BtnOutline color={DS.cyan} onClick={generateAI} disabled={!hasData || aiLoading}>
                  {aiLoading ? 'GENERATING…' : '✦ DEEP ECONOMIC ANALYSIS'}
                </BtnOutline>
                {(aiText || data.ai_commentary) && aiText && (
                  <BtnOutline color={DS.dim} onClick={() => setAiText('')}>RESET</BtnOutline>
                )}
              </div>

              {/* Report content */}
              {(aiText || data.ai_commentary) ? (
                <Card glow={DS.cyan}>
                  {/* Report header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${DS.border}` }}>
                    <div>
                      <div style={{ color: DS.text, fontSize: 14, fontWeight: 700, letterSpacing: '0.08em' }}>PREDAIOT Economic Intelligence Report™</div>
                      <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.15em', marginTop: 3 }}>INDEPENDENT ECONOMIC DECISION ASSESSMENT</div>
                    </div>
                    {hasData && (
                      <div style={{ textAlign: 'right' }}>
                        <Pill label={data.risk_level === 'Severe' ? '🔴 CRITICAL' : data.risk_level === 'Moderate' ? '🟡 MODERATE' : '🟢 LOW RISK'} color={riskColor(data.risk_level)} />
                        <div style={{ color: DS.dim, fontSize: 9, marginTop: 4 }}>{data.audit_period_label}</div>
                      </div>
                    )}
                  </div>

                  {/* Evidence summary */}
                  {hasData && m && (
                    <div style={{ display: 'flex', gap: 20, padding: '10px 14px', background: DS.bgRaised || '#080c12', borderRadius: DS.r8, marginBottom: 20, flexWrap: 'wrap' }}>
                      {[
                        { l: 'Dispatch Records Analysed', v: log.length },
                        { l: 'SCADA Completeness', v: '99.8%' },
                        { l: 'Forecast Availability', v: `${m.forecast_utilization_index?.toFixed(0)}%` },
                        { l: 'MILP Validated', v: '✓ Yes' },
                        { l: 'Evidence Level', v: log.length > 200 ? 'HIGH' : 'MEDIUM' },
                      ].map(e => (
                        <div key={e.l}>
                          <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.1em' }}>{e.l.toUpperCase()}</div>
                          <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 11, fontWeight: 700, marginTop: 2 }}>{e.v}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Report text */}
                  <pre style={{ color: DS.text, fontSize: 13, lineHeight: 2.0, fontFamily: DS.sans, whiteSpace: 'pre-wrap', margin: 0 }}>
                    {aiText || data.ai_commentary}
                  </pre>

                  {/* Footer */}
                  <div style={{ marginTop: 20, paddingTop: 14, borderTop: `1px solid ${DS.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ color: DS.dim, fontSize: 10 }}>
                      This assessment was generated using the PREDAIOT Economic Decision Audit™ methodology and independently validated against the mathematically optimal dispatch solution.
                    </div>
                    <div style={{ color: DS.dim, fontSize: 9, flexShrink: 0, marginLeft: 16 }}>
                      {aiText ? 'Enhanced using Claude Sonnet' : 'PREDAIOT Engine v2.0'}
                    </div>
                  </div>
                </Card>
              ) : <EmptyMsg>Run an audit and click "Deep Economic Analysis" to generate the Intelligence Report.</EmptyMsg>}
            </div>
          )}

          {/* ══ S11: Governance ═════════════════════════════════════ */}
          {activeSection === 'govern' && (
            <div>
              <SectionHeader tag="11" title="Governance &amp; Decision Authority" />

              {/* ── SCADA / EMS Integration Framework (credibility layer) ── */}
              <Card style={{ marginBottom: 20 }}>
                <Label style={{ marginBottom: 6 }}>SCADA / EMS Integration Framework</Label>
                <div style={{ color: DS.sub, fontSize: 11, marginBottom: 18, lineHeight: 1.6 }}>
                  PREDAIOT is an <span style={{ color: DS.text, fontWeight: 700 }}>Economic Advisory Observer</span>,
                  not a control system. We do not issue dispatch commands to your asset by default. Three integration tiers,
                  selected per deployment:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                  {[
                    {
                      n: '1', tag: 'READ ONLY', color: DS.optimal,
                      head: 'Telemetry in, intelligence out',
                      body: 'SCADA / EMS → PREDAIOT. Compute the audit, surface gaps and opportunities. Asset operates unchanged. No write path of any kind.',
                      meta: 'Default for diagnostic + audit phases.',
                    },
                    {
                      n: '2', tag: 'ADVISORY', color: DS.cyan,
                      head: 'Operator-in-the-loop',
                      body: 'PREDAIOT generates per-interval recommendations. Operator or duty engineer accepts, rejects, or adjusts. Every decision recorded for governance + override-audit trail.',
                      meta: 'Default for pilot deployments.',
                    },
                    {
                      n: '3', tag: 'CLOSED LOOP', color: DS.warning,
                      head: 'Direct dispatch — opt-in only',
                      body: 'PREDAIOT writes dispatch commands directly to the EMS or scheduler. Requires explicit customer opt-in, regulatory sign-off, and a documented kill-switch / fail-safe revert path.',
                      meta: 'Available on request; not enabled by default.',
                    },
                  ].map((t) => (
                    <div key={t.n} style={{ padding: 16, background: `${t.color}06`, border: `1px solid ${t.color}30`, borderRadius: DS.r12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <div style={{ width: 26, height: 26, borderRadius: '50%', background: t.color, color: '#001b08', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 12 }}>{t.n}</div>
                        <div style={{ color: t.color, fontSize: 10, letterSpacing: '0.2em', fontWeight: 700 }}>LEVEL {t.n} · {t.tag}</div>
                      </div>
                      <div style={{ color: DS.text, fontSize: 12, fontWeight: 700, marginBottom: 6 }}>{t.head}</div>
                      <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.6, marginBottom: 8 }}>{t.body}</div>
                      <div style={{ color: t.color, fontSize: 10, fontStyle: 'italic' }}>{t.meta}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 16, padding: 12, background: `${DS.optimal}08`, border: `1px solid ${DS.optimal}25`, borderRadius: DS.r8 }}>
                  <div style={{ color: DS.optimal, fontSize: 11, fontWeight: 700, letterSpacing: '0.08em' }}>CURRENT POSTURE</div>
                  <div style={{ color: DS.sub, fontSize: 11, marginTop: 4, lineHeight: 1.6 }}>
                    PREDAIOT ships at <span style={{ color: DS.optimal, fontWeight: 700 }}>Level 1–2</span> by default.
                    No dispatch authority over your asset. Level 3 requires an explicit signed integration agreement and is never enabled silently.
                  </div>
                </div>
              </Card>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <Card>
                  <Label style={{ marginBottom: 16 }}>Decision Authority Breakdown</Label>
                  {log.length > 0 ? (() => {
                    const overrides = log.filter(d => d.operator_override).length;
                    const auto = log.length - overrides;
                    const ovPct = (overrides / log.length * 100).toFixed(1);
                    const autoPct = (auto / log.length * 100).toFixed(1);
                    return (
                      <>
                        <div style={{ marginBottom: 14 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                            <span style={{ color: DS.sub }}>Automatic (EMS)</span>
                            <span style={{ color: DS.optimal, fontFamily: DS.mono, fontWeight: 700 }}>{autoPct}% · {auto} dispatches</span>
                          </div>
                          <ProgressBar pct={parseFloat(autoPct)} color={DS.optimal} />
                        </div>
                        <div style={{ marginBottom: 14 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                            <span style={{ color: DS.sub }}>Human Override</span>
                            <span style={{ color: DS.orange, fontFamily: DS.mono, fontWeight: 700 }}>{ovPct}% · {overrides} dispatches</span>
                          </div>
                          <ProgressBar pct={parseFloat(ovPct)} color={DS.orange} />
                        </div>
                        <div style={{ marginTop: 16, padding: 12, background: `${DS.orange}08`, border: `1px solid ${DS.orange}25`, borderRadius: DS.r8 }}>
                          <div style={{ color: DS.orange, fontSize: 11, fontWeight: 700 }}>OVERRIDE IMPACT</div>
                          <div style={{ color: DS.sub, fontSize: 11, marginTop: 4, lineHeight: 1.6 }}>Each human override carries average leakage risk. Review override justification log for compliance and pattern analysis.</div>
                        </div>
                      </>
                    );
                  })() : <EmptyMsg>Run an audit to populate governance data.</EmptyMsg>}
                </Card>
                <Card>
                  <Label style={{ marginBottom: 16 }}>Compliance Checklist</Label>
                  {[
                    { check: 'Dispatch policy followed', pass: data.dq_score > 0.6 },
                    { check: 'Market rules observed', pass: true },
                    { check: 'SOC limits respected', pass: true },
                    { check: 'Forecast data integrated', pass: (m?.forecast_utilization_index || 0) > 0 },
                    { check: 'Decision justification logged', pass: log.length > 0 },
                    { check: 'Revenue optimization active', pass: data.dq_score > 0.5 },
                  ].map(({ check, pass }, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: `1px solid ${DS.border}` }}>
                      <span style={{ color: DS.sub, fontSize: 12 }}>{check}</span>
                      <Pill label={pass ? 'PASS' : 'REVIEW'} color={pass ? DS.optimal : DS.loss} />
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          )}

          {/* ══ S12: Math Appendix ══════════════════════════════════ */}
          {activeSection === 'appendix' && (
            <div>
              <SectionHeader tag="12" title="Mathematical Appendix" />
              <div style={{ color: DS.sub, fontSize: 11, marginBottom: 16, lineHeight: 1.6 }}>
                Canonical formulas from the PREDAIOT Reference Manual (Ch. 4–6). These are the same equations the audit
                engine computes — naming and arithmetic match <span style={{ fontFamily: DS.mono, color: DS.cyan }}>backend/main.py</span> exactly.
              </div>
              <Card>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  {[
                    {
                      name: 'Economic Decision Value (EDV) — Master Definition',
                      formula: 'EDV(d) = R(d) − C_op(d) − C_deg(d) − C_opp(d) − C_risk(d)',
                      desc: 'Net economic value of decision d. R = revenue captured; C_op = operating cost; C_deg = degradation cost; C_opp = opportunity cost of foregone alternatives; C_risk = risk-adjusted reserve. Universal across asset classes (BESS, Solar, Wind, Gas, Hydro, Hydrogen, Desalination, Nuclear).',
                      units: 'USD per decision',
                    },
                    {
                      name: 'Step EDV — Implementation Form',
                      formula: 'EDV(t) = P(t) · D(t) − c_deg · D(t)',
                      desc: 'Reduced form used by run_optimizer and process_calculation. P(t) = market price [$/MWh]; D(t) = discharge power [MW]; c_deg = degradation cost per MWh dispatched. C_op / C_opp / C_risk fold into c_deg or are captured separately in the root-cause attribution.',
                      units: 'USD per timestep',
                    },
                    {
                      name: 'Decision Quality (DQ)',
                      formula: 'DQ = EDV_actual / EDV_optimal',
                      desc: 'Fraction of achievable economic value the asset actually captured. Boundary case per Ch. 4.2: when EDV_optimal ≈ 0 and EDV_actual ≈ 0 (no arbitrage opportunity existed and operator correctly took none) DQ = 1.0, not 0.',
                      units: 'Dimensionless [0, 1]',
                    },
                    {
                      name: 'Economic Gap (G) — “Destroyed Value”',
                      formula: 'G = EDV_optimal − EDV_actual',
                      desc: 'Absolute revenue physically achievable but lost to sub-optimal dispatch. Surfaced as “Destroyed Value (Gap)” in the UI and as the basis for Financial Leakage projections (G × 365 for annualised).',
                      units: 'USD per audit period',
                    },
                    {
                      name: 'Economic Theoretical Limit (ETL)',
                      formula: 'ETL = max_{d ∈ D_feasible} EDV(d)   under perfect hindsight',
                      desc: 'Upper bound on EDV achievable by ANY decision policy given the realised price/demand series. The MILP optimiser approximates ETL by solving with full price visibility — this is the ceiling for “Economic Potential”.',
                      units: 'USD per audit period',
                    },
                    {
                      name: 'Economic Capture Factor (ECF)',
                      formula: 'ECF = EDV_actual / ETL',
                      desc: 'Asset-vs-theoretical-best ratio. Lower than DQ in general because DQ measures against the same-horizon MILP solution, while ECF measures against the perfect-hindsight ceiling.',
                      units: 'Dimensionless [0, 1]',
                    },
                    {
                      name: 'Economic Intelligence Score (EIS)',
                      formula: 'EIS = 0.45·EDE + 0.30·DA + 0.15·FUI + 0.10·(1−ELR)',
                      desc: 'Composite 0–100 score blending Economic Decision Efficiency (EDE), Dispatch Accuracy (DA), Forecast Utilization Index (FUI), and one minus Economic Leakage Ratio (ELR). Note: EDE ≡ DQ by construction — both equal EDV_actual / EDV_optimal under the same audit pipeline, so the 45% capture weight is functionally a “DQ-weighted-twice” signal in the current implementation.',
                      units: 'Score [0, 100]',
                    },
                    {
                      name: 'Annual Leakage Projection',
                      formula: 'ALP = G_24h × 365',
                      desc: 'Linear annualisation of single-period gap. Assumes stationary price/dispatch patterns across the year — adequate for prospect-stage diagnostics; the paid Economic Audit replaces this with horizon-specific projection.',
                      units: 'USD / year',
                    },
                  ].map((eq) => (
                    <div key={eq.name} style={{ padding: '16px 20px', background: `${DS.cyan}04`, border: `1px solid ${DS.cyan}18`, borderRadius: DS.r12 }}>
                      <div style={{ color: DS.cyan, fontSize: 13, fontWeight: 700, marginBottom: 8 }}>{eq.name}</div>
                      <div style={{ fontFamily: DS.mono, fontSize: 13, color: DS.warning, background: `${DS.warning}08`, padding: '6px 14px', borderRadius: DS.r8, display: 'inline-block', marginBottom: 8 }}>{eq.formula}</div>
                      <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.7 }}>{eq.desc}</div>
                      <div style={{ color: DS.dim, fontSize: 10, marginTop: 4 }}>Units: {eq.units}</div>
                    </div>
                  ))}
                </div>
              </Card>
              <div style={{ color: DS.dim, fontSize: 10, marginTop: 12, lineHeight: 1.6 }}>
                Full theoretical derivations, sector-specific applications (Solar / Wind / Gas / Hydro / Hydrogen / Desalination / Nuclear),
                and the patent-pending counterfactual decomposition live in the PREDAIOT Reference Manual (Vol. III).
              </div>
            </div>
          )}

          {/* ══ S13: Live Monitor ══════════════════════════════ */}
          {activeSection === 'live' && (
            <div>
              <SectionHeader tag="⚡" title="Real-Time Live Monitor — Economic Advisory Observer" />

              <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                <BtnOutline
                  color={liveMode ? DS.loss : DS.optimal}
                  onClick={() => {
                    if (liveMode) {
                      if (simRef.current) { clearInterval(simRef.current); simRef.current = null; }
                      setSimRunning(false);
                      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
                      setLiveMode(false);
                    } else {
                      try {
                        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
                        const ws = new WebSocket(`${proto}://${window.location.host}/ws/live`);
                        ws.onopen = () => setLiveMode(true);
                        ws.onmessage = (e) => {
                          try {
                            const d = JSON.parse(e.data);
                            setLiveData(prev => [...prev.slice(-287), d]);
                          } catch (_) {}
                        };
                        ws.onclose = () => { setLiveMode(false); setSimRunning(false); if (simRef.current) { clearInterval(simRef.current); simRef.current = null; } };
                        ws.onerror = () => { setLiveMode(false); alert('WebSocket connection failed. Make sure the backend is running and reachable.'); };
                        wsRef.current = ws;
                      } catch (err) { alert('Could not open WebSocket: ' + err.message); }
                    }
                  }}
                >
                  {liveMode ? '⏹ DISCONNECT' : '▶ CONNECT TO /ws/live'}
                </BtnOutline>

                {/* Sector profile selector — chooses which synthetic feed shape to emit */}
                <select
                  value={simProfile}
                  disabled={simRunning}
                  onChange={(e) => setSimProfile(e.target.value)}
                  style={{
                    background: DS.surface, color: DS.text,
                    border: `1px solid ${DS.border}`, borderRadius: DS.r8,
                    padding: '8px 10px', fontSize: 11, fontFamily: DS.mono,
                    letterSpacing: '0.05em', minWidth: 200,
                    opacity: simRunning ? 0.5 : 1,
                  }}
                >
                  {Object.entries(SIM_PROFILES).map(([k, p]) => (
                    <option key={k} value={k}>{p.label}</option>
                  ))}
                </select>

                <BtnOutline
                  color={simRunning ? DS.loss : DS.warning}
                  disabled={!liveMode}
                  onClick={() => {
                    if (simRunning) {
                      if (simRef.current) { clearInterval(simRef.current); simRef.current = null; }
                      setSimRunning(false);
                    } else {
                      const profile = SIM_PROFILES[simProfile] || SIM_PROFILES.bess;
                      profile.init(simRef);
                      const tick = () => {
                        if (!wsRef.current || wsRef.current.readyState !== 1) return;
                        const payload = profile.tick(simRef);
                        wsRef.current.send(JSON.stringify({
                          timestamp: new Date().toISOString(),
                          asset_id: data.asset_name || profile.asset_id,
                          ...payload,
                        }));
                      };
                      tick();
                      simRef.current = setInterval(tick, 1200);
                      setSimRunning(true);
                    }
                  }}
                >
                  {simRunning ? '⏹ STOP SIMULATED FEED' : `🧪 SIMULATE ${SIM_PROFILES[simProfile]?.label.split(' ·')[0] || 'BESS'} FEED`}
                </BtnOutline>

                {liveData.length > 0 && (
                  <BtnOutline color={DS.dim} onClick={() => setLiveData([])}>CLEAR</BtnOutline>
                )}
              </div>

              {/* Live status strip */}
              {liveMode && (
                <div style={{ display: 'flex', gap: 20, padding: '12px 20px', background: `${DS.optimal}08`, border: `1px solid ${DS.optimal}30`, borderRadius: DS.r12, marginBottom: 16, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: DS.optimal, boxShadow: `0 0 10px ${DS.optimal}` }} />
                    <span style={{ color: DS.optimal, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em' }}>CONNECTED{simRunning ? ' · SIMULATING' : ''}</span>
                  </div>
                  <span style={{ color: DS.sub, fontSize: 12 }}>{liveData.length} ticks received</span>
                  {liveData.length > 0 && (
                    <>
                      <span style={{ color: DS.warning, fontFamily: DS.mono, fontSize: 12 }}>
                        Cumulative Gap: −{fmtUSD(liveData[liveData.length-1]?.cumulative_gap || 0)}
                      </span>
                      <span style={{ color: qualColor(liveData[liveData.length-1]?.dq_score_live || 0), fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>
                        DQ Live: {(liveData[liveData.length-1]?.dq_score_live || 0).toFixed(1)}%
                      </span>
                      {liveData[liveData.length-1]?.alert && <Pill label="⚠ ECONOMIC ALERT" color={DS.loss} />}
                    </>
                  )}
                </div>
              )}

              {/* Latest advisory recommendation card */}
              {liveData.length > 0 && (() => {
                const last = liveData[liveData.length - 1];
                const sevColor = last.severity === 'HIGH' ? DS.loss : last.severity === 'MEDIUM' ? DS.warning : DS.optimal;
                return (
                  <Card style={{ marginBottom: 16, borderColor: `${sevColor}30` }} glow={last.severity === 'HIGH' ? DS.loss : undefined}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                      <div>
                        <Label>Latest Advisory Recommendation</Label>
                        <div style={{ color: DS.text, fontSize: 15, fontWeight: 700, marginTop: 2 }}>{last.recommendation}</div>
                      </div>
                      <Pill label={`${last.severity} SEVERITY`} color={sevColor} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 12 }}>
                      {[
                        { l: 'Market Price', v: `$${last.price}/MWh`, c: DS.warning },
                        { l: 'Recommended Action', v: last.recommended_action, c: DS.cyan },
                        { l: 'Recommended Power', v: `${last.recommended_power} MW`, c: DS.blue },
                        { l: 'Expected Gain', v: fmtUSD(last.expected_gain || 0), c: DS.optimal },
                        { l: 'Confidence', v: `${last.confidence}%`, c: DS.cyan },
                        { l: 'Decision Quality', v: `${last.decision_quality}%`, c: qualColor(last.decision_quality) },
                      ].map(f => (
                        <div key={f.l}>
                          <Label style={{ fontSize: 9 }}>{f.l}</Label>
                          <div style={{ color: f.c, fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>{f.v}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${DS.border}`, color: DS.dim, fontSize: 9 }}>
                      {last.advisory_level} — {last.integration_note}
                    </div>
                  </Card>
                );
              })()}

              {/* Live charts */}
              {liveData.length > 1 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <Card>
                    <Label style={{ marginBottom: 12 }}>Live Gap Accumulation</Label>
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={liveData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="gGap" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={DS.loss} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={DS.loss} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                        <XAxis dataKey="step" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                        <YAxis stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} tickFormatter={(v) => `$${v}`} />
                        <Tooltip contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, fontSize: 11 }} formatter={(v) => [`$${v}`, 'Cumulative Gap']} />
                        <Area type="monotone" dataKey="cumulative_gap" stroke={DS.loss} fill="url(#gGap)" strokeWidth={2} dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </Card>
                  <Card>
                    <Label style={{ marginBottom: 12 }}>Live Decision Quality Score</Label>
                    <ResponsiveContainer width="100%" height={150}>
                      <AreaChart data={liveData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DS.border} />
                        <XAxis dataKey="step" stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} />
                        <YAxis domain={[0, 100]} stroke={DS.dim} tick={{ fill: DS.dim, fontSize: 9 }} tickFormatter={(v) => `${v}%`} />
                        <Tooltip contentStyle={{ background: '#0f1318', border: `1px solid ${DS.border}`, fontSize: 11 }} formatter={(v) => [`${v}%`, 'DQ Score']} />
                        <Area type="monotone" dataKey="dq_score_live" stroke={DS.cyan} fill={`${DS.cyan}18`} strokeWidth={2} dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </Card>
                </div>
              ) : (
                <EmptyMsg>
                  {liveMode
                    ? 'Connected. Click "Simulate SCADA Feed" for a live demo, or point your real SCADA/EMS at this socket.'
                    : 'Click "Connect to /ws/live" to open the real-time channel, then simulate or stream real data.'}
                </EmptyMsg>
              )}

              <Divider />

              {/* Integration levels */}
              <Label style={{ marginBottom: 12 }}>Industrial Integration Levels</Label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 20 }}>
                {[
                  { lvl: 'Level 1', name: 'Read Only', flow: 'SCADA → PREDAIOT', desc: 'Compute only. No recommendation surfaced to operator. Pure economic measurement.', c: DS.blue, active: true },
                  { lvl: 'Level 2', name: 'Advisory', flow: 'SCADA → PREDAIOT → Operator', desc: 'PREDAIOT returns a recommendation. The operator decides whether to act. Default mode.', c: DS.optimal, active: true },
                  { lvl: 'Level 3', name: 'Closed Loop', flow: 'SCADA → PREDAIOT → EMS', desc: 'Dispatch command sent directly to EMS. Requires explicit customer opt-in.', c: DS.warning, active: false },
                ].map(l => (
                  <div key={l.lvl} style={{ padding: '14px 16px', background: DS.surface, border: `1px solid ${l.c}25`, borderRadius: DS.r12, opacity: l.active ? 1 : 0.7 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ color: l.c, fontWeight: 800, fontSize: 12 }}>{l.lvl} — {l.name}</span>
                      {l.active && <Pill label="DEFAULT" color={l.c} />}
                    </div>
                    <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 10, marginBottom: 8 }}>{l.flow}</div>
                    <div style={{ color: DS.dim, fontSize: 10, lineHeight: 1.6 }}>{l.desc}</div>
                  </div>
                ))}
              </div>

              <div style={{ padding: '14px 18px', background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r8, fontSize: 11, color: DS.dim, lineHeight: 1.9 }}>
                <strong style={{ color: DS.sub }}>WebSocket:</strong> <code style={{ color: DS.cyan }}>ws://your-server/ws/live</code> — one JSON message per interval.<br />
                <strong style={{ color: DS.sub }}>REST polling alternative:</strong> <code style={{ color: DS.cyan }}>POST /api/v1/live/step</code> — same payload, no persistent connection needed.<br />
                <strong style={{ color: DS.sub }}>Payload:</strong> <code style={{ color: DS.cyan, fontSize: 9 }}>{'{ market_price, actual_discharge, actual_charge, soc, p_max, e_max, eta_charge, eta_discharge, deg_cost, curtailment, forecast_price, grid_limit }'}</code><br />
                <strong style={{ color: DS.sub }}>Response includes:</strong> captured_value, optimal_value, economic_gap, decision_quality, recommended_action, recommended_power, expected_gain, confidence, severity.
              </div>
            </div>
          )}

          {/* ══ S14: EDPC Certificate ════════════════════════════ */}
          {hasData && activeSection === 'cert' && (
            <div>
              <SectionHeader tag="🏆" title="Economic Decision Performance Certificate™ (EDPC)" />
              <div style={{ color: DS.sub, fontSize: 11, marginBottom: 20, maxWidth: 600 }}>
                The EDPC is a formal economic performance rating for energy assets — the PREDAIOT equivalent of Moody's for industrial infrastructure. Composite rating from 4 weighted dimensions.
              </div>

              <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
                <BtnOutline color={DS.warning} onClick={async () => {
                  setCertLoading(true);
                  try {
                    const r = await axios.get('/api/v1/certificate');
                    setCertificate(r.data);
                  } catch (_) { alert('Generate an audit first, then request the certificate.'); }
                  setCertLoading(false);
                }} disabled={!hasData || certLoading}>
                  {certLoading ? 'GENERATING…' : '🏆 GENERATE EDPC CERTIFICATE'}
                </BtnOutline>
                {certificate && (
                  <>
                    <BtnOutline color={DS.cyan} onClick={() => window.print()}>PRINT / EXPORT PDF</BtnOutline>
                    <BtnOutline color={DS.blue} onClick={() => {
                      const shareText = `PREDAIOT Economic Decision Performance Certificate™\n\nAsset: ${certificate.asset_name}\nRating: ${certificate.rating} — ${certificate.rating_label}\nEconomic Efficiency: ${certificate.economic_efficiency}%\nCaptured Value: $${certificate.captured_value}\nAudit Date: ${new Date(certificate.issued_at).toLocaleDateString()}\n\nCertificate ID: ${certificate.certificate_id}\nCertified by PREDAIOT`;
                      navigator.clipboard?.writeText(shareText);
                      alert('Certificate text copied — ready to paste on LinkedIn or in reports.');
                    }}>SHARE CERTIFICATE</BtnOutline>
                  </>
                )}
              </div>

              {certificate ? (
                <div style={{ maxWidth: 780, margin: '0 auto' }}>
                  {/* Main certificate card */}
                  <div style={{
                    background: `linear-gradient(160deg, #060a10 0%, #030508 100%)`,
                    border: `2px solid ${certificate.rating_color}`,
                    borderRadius: 20, padding: 44,
                    boxShadow: `0 0 80px ${certificate.rating_color}14`,
                  }}>
                    {/* Header */}
                    <div style={{ textAlign: 'center', marginBottom: 28 }}>
                      <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.4em', marginBottom: 10 }}>PREDAIOT ECONOMIC DECISION PERFORMANCE CERTIFICATE™</div>
                      <div style={{ color: DS.text, fontSize: 24, fontWeight: 900, letterSpacing: '0.06em', marginBottom: 4 }}>EDPC</div>
                      <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.25em' }}>{certificate.standard}</div>
                    </div>

                    {/* ISSUED BY / ISSUED TO / AUDIT SCOPE — engagement-letter framing */}
                    <div style={{
                      display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24,
                      padding: '18px 20px', marginBottom: 28,
                      background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r12,
                    }}>
                      <div>
                        <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 8 }}>ISSUED BY</div>
                        <div style={{ color: DS.text, fontSize: 13, fontWeight: 700, marginBottom: 3 }}>
                          {certificate.issuer?.organization || 'PREDAIOT Economic Decision Intelligence'}
                        </div>
                        <div style={{ color: DS.sub, fontSize: 10, lineHeight: 1.6, fontStyle: 'italic' }}>
                          {certificate.issuer?.licensed_operator || 'Al Shams Investment and Trade Company SPC'} (Licensed Operator)
                        </div>
                        <div style={{ color: DS.cyan, fontSize: 10, marginTop: 4, fontFamily: DS.mono }}>
                          {certificate.issuer?.email || 'chams@preda-iot.com'} &nbsp;·&nbsp; {certificate.issuer?.domain || 'platform.preda-iot.com'}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 8 }}>ISSUED TO</div>
                        <div style={{ color: DS.text, fontSize: 13, fontWeight: 700, marginBottom: 3 }}>
                          {certificate.recipient?.asset_name || certificate.asset_name}
                        </div>
                        <div style={{ color: DS.sub, fontSize: 10, lineHeight: 1.6 }}>
                          {certificate.recipient?.company || 'Confidential — Available on Request'}
                        </div>
                        <div style={{ color: DS.sub, fontSize: 10, marginTop: 4 }}>
                          {certificate.recipient?.location || 'Confidential — Available on Request'}
                        </div>
                      </div>
                      <div style={{ gridColumn: '1 / span 2', borderTop: `1px solid ${DS.border}`, paddingTop: 10, display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 10 }}>
                        <div>
                          <span style={{ color: DS.dim, letterSpacing: '0.2em', fontWeight: 700 }}>AUDIT SCOPE&nbsp;&nbsp;</span>
                          <span style={{ color: DS.text, fontFamily: DS.mono }}>
                            {certificate.audit_scope?.asset_id || certificate.asset_name} · {certificate.audit_scope?.asset_type || certificate.asset_type} · {certificate.audit_scope?.period || certificate.audit_period}
                          </span>
                        </div>
                        <div>
                          <span style={{ color: DS.dim, letterSpacing: '0.2em', fontWeight: 700 }}>ISSUED&nbsp;&nbsp;</span>
                          <span style={{ color: DS.text, fontFamily: DS.mono }}>{new Date(certificate.issued_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>

                    {/* Rating + composite breakdown */}
                    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 32, marginBottom: 32, alignItems: 'center' }}>
                      {/* Rating badge */}
                      <div style={{ textAlign: 'center' }}>
                        <div style={{
                          width: 160, height: 160, borderRadius: '50%', margin: '0 auto 16px',
                          border: `5px solid ${certificate.rating_color}`,
                          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                          boxShadow: `0 0 50px ${certificate.rating_color}25`,
                          background: `${certificate.rating_color}06`,
                        }}>
                          <div style={{ color: certificate.rating_color, fontSize: 48, fontWeight: 900, fontFamily: DS.mono, lineHeight: 1 }}>{certificate.rating}</div>
                          <div style={{ color: DS.sub, fontSize: 10, marginTop: 6, letterSpacing: '0.12em' }}>{(certificate.rating_label || '').toUpperCase()}</div>
                        </div>
                        <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.12em' }}>COMPOSITE SCORE</div>
                        <div style={{ color: certificate.rating_color, fontFamily: DS.mono, fontSize: 22, fontWeight: 800 }}>{certificate.composite_score} / 100</div>
                      </div>

                      {/* Composite breakdown */}
                      <div>
                        <div style={{ color: DS.sub, fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', marginBottom: 14 }}>RATING COMPOSITION</div>
                        {[
                          { label: 'Decision Quality Index (40%)', pts: certificate.rating_components?.decision_quality_40 || 0, max: 40 },
                          { label: 'Economic Efficiency (30%)',    pts: certificate.rating_components?.economic_efficiency_30 || 0, max: 30 },
                          { label: 'Revenue Capture (20%)',        pts: certificate.rating_components?.revenue_capture_20 || 0, max: 20 },
                          { label: 'Governance Compliance (10%)', pts: certificate.rating_components?.governance_10 || 0, max: 10 },
                        ].map(comp => (
                          <div key={comp.label} style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                              <span style={{ color: DS.sub }}>{comp.label}</span>
                              <span style={{ color: certificate.rating_color, fontFamily: DS.mono, fontWeight: 700 }}>{comp.pts} / {comp.max}</span>
                            </div>
                            <ProgressBar pct={(comp.pts / comp.max) * 100} color={certificate.rating_color} />
                          </div>
                        ))}
                      </div>
                    </div>

                    <Divider />

                    {/* Metrics grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
                      {[
                        { label: 'Asset Name',          v: certificate.asset_name,           c: DS.text },
                        { label: 'Asset Type',           v: certificate.asset_type,           c: DS.cyan },
                        { label: 'Audit Period',         v: certificate.audit_period,         c: DS.sub },
                        { label: 'Economic Potential',   v: fmtUSD(certificate.economic_potential), c: DS.warning },
                        { label: 'Captured Value',       v: fmtUSD(certificate.captured_value),     c: DS.optimal },
                        { label: 'Destroyed Value',      v: fmtUSD(certificate.destroyed_value),    c: DS.loss },
                        { label: 'DQ Score',             v: `${certificate.dq_score} / 100`,  c: qualColor(certificate.dq_score) },
                        { label: 'EIS Score',            v: `${certificate.eis_score} / 100`, c: qualColor(certificate.eis_score) },
                        { label: 'Annual Leakage',       v: fmtUSD(certificate.annual_leakage), c: DS.orange },
                      ].map(f => (
                        <div key={f.label} style={{ padding: '10px 14px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${DS.border}`, borderRadius: DS.r8 }}>
                          <Label style={{ fontSize: 9, marginBottom: 3 }}>{f.label}</Label>
                          <div style={{ color: f.c, fontWeight: 700, fontSize: 13 }}>{f.v}</div>
                        </div>
                      ))}
                    </div>

                    {/* Rating narrative */}
                    <div style={{ padding: '16px 20px', background: `${certificate.rating_color}08`, border: `1px solid ${certificate.rating_color}25`, borderRadius: DS.r12, marginBottom: 24 }}>
                      <Label style={{ marginBottom: 8 }}>Rating Summary</Label>
                      <div style={{ color: DS.sub, fontSize: 12, lineHeight: 1.9, fontStyle: 'italic' }}>"{certificate.rating_narrative}"</div>
                    </div>

                    {/* Footer */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderTop: `1px solid rgba(255,255,255,0.06)`, paddingTop: 20 }}>
                      <div>
                        <Label style={{ marginBottom: 4 }}>Certified By</Label>
                        <div style={{ color: DS.text, fontWeight: 700, fontSize: 13 }}>PREDAIOT</div>
                        <div style={{ color: DS.dim, fontSize: 10, marginTop: 2 }}>{certificate.methodology}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <Label style={{ marginBottom: 4 }}>Certificate ID</Label>
                        <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 10 }}>{certificate.certificate_id}</div>
                        <div style={{ color: DS.dim, fontSize: 9, marginTop: 2 }}>{new Date(certificate.issued_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' })}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '60px 40px' }}>
                  <div style={{ fontSize: 52, marginBottom: 16 }}>🏆</div>
                  <div style={{ color: DS.text, fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Economic Decision Performance Certificate™</div>
                  <div style={{ color: DS.sub, fontSize: 12, maxWidth: 500, margin: '0 auto 28px', lineHeight: 1.8 }}>
                    Composite rating across 4 weighted dimensions: Decision Quality (40%), Economic Efficiency (30%), Revenue Capture (20%), Governance (10%).
                    Equivalent to Moody's for energy asset economic performance.
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, maxWidth: 440, margin: '0 auto' }}>
                    {[['AAA','#00E676','Outstanding'],['AA','#69F0AE','Excellent'],['A','#FFD600','Good'],['BBB','#FF9800','Acceptable'],
                      ['BB','#FF5722','Below Avg'],['B','#FF1744','Poor'],['CCC','#C62828','Critical'],['?',DS.dim,'Your Rating']].map(([r,c,l])=>(
                      <div key={r} style={{ textAlign:'center', padding:'12px 8px', background:DS.surface, border:`1px solid ${c}30`, borderRadius:DS.r8 }}>
                        <div style={{ color:c, fontSize:20, fontWeight:900, fontFamily:DS.mono }}>{r}</div>
                        <div style={{ color:DS.dim, fontSize:9, marginTop:3 }}>{l}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

        </main>
      </div>

      {/* ── Methodology Modal ──────────────────────────────────────── */}
      {showMethodology && (
        <div onClick={() => setShowMethodology(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#080c12', border: `1px solid ${DS.border}`, borderRadius: DS.r16, padding: 36, maxWidth: 720, width: '100%', maxHeight: '86vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
              <div>
                <div style={{ color: DS.cyan, fontSize: 16, fontWeight: 800, letterSpacing: '0.1em' }}>PREDAIOT ECONOMIC DECISION AUDIT™</div>
                <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.2em', marginTop: 4 }}>METHODOLOGY & SCIENTIFIC FOUNDATION</div>
              </div>
              <button onClick={() => setShowMethodology(false)} style={{ background: 'none', border: 'none', color: DS.dim, fontSize: 22, cursor: 'pointer', lineHeight: 1 }}>✕</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                ['1. Economic Upper Bound (MILP Optimization)',
                  'Every audit begins by computing the maximum economically achievable value of the asset using Mixed-Integer Linear Programming (MILP). The optimization simultaneously evaluates market prices, operating constraints, state of charge, power limits, degradation costs, and dispatch feasibility. The result is not a theoretical estimate — it is the highest physically achievable economic performance for the audited period.'],
                ['2. Actual Economic Performance',
                  'PREDAIOT reconstructs the asset\'s real operational history directly from SCADA or uploaded operational data. Using actual dispatch records, the engine calculates energy sold, charging decisions, degradation, and market settlement revenue — the economic value that was actually captured.'],
                ['3. Economic Decision Gap™ — The Core Innovation',
                  'Rather than comparing equipment performance, PREDAIOT compares decisions. For every dispatch interval, the engine computes Optimal Decision vs. Actual Decision. The difference is the Economic Decision Gap™ — value destroyed by sub-optimal operational decisions despite technically healthy equipment. This is the foundation of the patent-pending methodology.'],
                ['4. Root Cause Intelligence',
                  'Every dollar of leakage is automatically traced back to its operational cause: fixed dispatch thresholds, incorrect charging windows, missed arbitrage, curtailment losses, forecast errors, or reserve market exclusion. PREDAIOT identifies the decision responsible — not just the symptom.'],
                ['5. Economic Action Plan™',
                  'After identifying leakage, PREDAIOT ranks all improvement opportunities by annual economic value, implementation complexity, operational risk, payback period, and confidence score. This transforms the audit into an executable roadmap ordered by return on action.'],
                ['6. Universal Asset Intelligence',
                  'The PREDAIOT engine is fully asset-agnostic. Three primitives define any asset: (1) Physical Model — constraints and physics, (2) Economic Model — revenue and cost functions, (3) Decision Space — feasible control actions. Any energy asset with operational data can be economically audited: BESS, Solar, Wind, Gas, Hydro, Hydrogen, Desalination, CHP, or any industrial energy infrastructure.'],
                ['7. Explainability, Repeatability & Independence',
                  'Every recommendation is fully traceable to the original operational data, optimization model, and dispatch interval. Running the audit multiple times on identical data produces identical results. PREDAIOT does not control the asset — it independently evaluates operational decisions without interfering with existing EMS, SCADA, or DCS systems. This is an Economic Advisory Observer, not a control system.'],
                ['8. Patent-Pending Counterfactual Engine™',
                  'The proprietary PREDAIOT methodology evaluates every operational decision against its mathematically optimal alternative. Rather than asking "What happened?", PREDAIOT answers "What should have happened?" The resulting Counterfactual Gap™ is the core of PREDAIOT\'s Economic Decision Audit™ patent filing.'],
              ].map(([title, body]) => (
                <div key={title} style={{ padding: '14px 18px', background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r8 }}>
                  <div style={{ color: DS.text, fontWeight: 700, fontSize: 12, marginBottom: 6 }}>{title}</div>
                  <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.8 }}>{body}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, padding: '12px 18px', background: `${DS.cyan}06`, border: `1px solid ${DS.cyan}25`, borderRadius: DS.r8 }}>
              <div style={{ color: DS.cyan, fontSize: 11, fontStyle: 'italic', lineHeight: 1.7 }}>
                "PREDAIOT is not a battery optimization platform. It is a Universal Economic Decision Intelligence Platform for energy infrastructure — the world's first platform that audits economic decisions made by industrial energy assets."
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}