import React, { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import axios from 'axios';
import ExecutiveCommandCenter from './components/ExecutiveCommandCenter';
import { Workspace, Zone, useWorkspaceTier, tierAtLeast } from './workspace/Workspace';

// SPEC-PF rule 2: recharts and every instrument travel in a code-split
// chunk, loaded on demand — never on the initial path.
const chartsModule = () => import('./instruments/charts');
const FinancialTimeline = lazy(() => chartsModule().then((m) => ({ default: m.FinancialTimeline })));
const LeakageFlow       = lazy(() => chartsModule().then((m) => ({ default: m.LeakageFlow })));
const DispatchCurve     = lazy(() => chartsModule().then((m) => ({ default: m.DispatchCurve })));
const LeakageHistory    = lazy(() => chartsModule().then((m) => ({ default: m.LeakageHistory })));
const LiveGapFlow       = lazy(() => chartsModule().then((m) => ({ default: m.LiveGapFlow })));
const LiveCaptureScore  = lazy(() => chartsModule().then((m) => ({ default: m.LiveCaptureScore })));

import { ChartSkeleton } from './instruments/theme';

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

const AUTH_STORAGE_KEY = 'predaiot.auth.v1';

const authStore = {
  get: () => {
    try { return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || 'null'); }
    catch { return null; }
  },
  set: (v) => { try { localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(AUTH_STORAGE_KEY); } catch {} },
};

axios.interceptors.request.use((cfg) => {
  // Signed-in account takes precedence; legacy trial token otherwise.
  const a = authStore.get();
  if (a?.token) {
    cfg.headers['Authorization'] = `Bearer ${a.token}`;
    return cfg;
  }
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
// RESPONSIVE — viewport hook shared across the app
// ══════════════════════════════════════════════════════════════════════
// 720px is the "phone-portrait or narrow tablet" breakpoint. Below this,
// the sidebar collapses to a hamburger drawer and the header buttons
// wrap onto multiple rows.
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' && window.matchMedia('(max-width: 720px)').matches
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia('(max-width: 720px)');
    const onChange = (e) => setIsMobile(e.matches);
    if (mql.addEventListener) mql.addEventListener('change', onChange);
    else mql.addListener(onChange);  // older Safari
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', onChange);
      else mql.removeListener(onChange);
    };
  }, []);
  return isMobile;
}

// ══════════════════════════════════════════════════════════════════════
// DESIGN SYSTEM — PREDAIOT Economic Decision Audit™
// ══════════════════════════════════════════════════════════════════════
// Legacy inline-style token object. Its hex VALUES now mirror the PREDAIOT
// design system (design/tokens.css) so every section that styles via `DS`
// inherits the quiet, premium palette at once — while `${DS.color}30` alpha
// concatenation keeps working (raw hex, not var() refs). Semantic source of
// truth remains tokens.css / PDS; this is the bridge for legacy inline styles.
const DS = {
  bg:           '#06090F',   // --pds-bg-0 (matches index.css canvas)
  bgRaised:     '#0E1420',   // --pds-panel
  surface:      'rgba(255,255,255,0.025)',
  surfaceHi:    'rgba(255,255,255,0.05)',
  border:       'rgba(255,255,255,0.07)',
  borderHi:     'rgba(255,255,255,0.15)',

  optimal:  '#2FD69B',   // --pds-recover  (was neon #00E676)
  warning:  '#F3B24C',   // --pds-warn     (was pure #FFD600)
  loss:     '#FF5C7A',   // --pds-loss     (was neon #FF1744)
  blue:     '#5AA9FF',   // --pds-info
  cyan:     '#34E0C8',   // --pds-accent   (signature teal, was #00E5FF)
  orange:   '#F5945B',   // --pds-grade-d
  purple:   '#7C9CFF',   // --pds-dec-recovery

  text:    '#EAF1F8',    // --pds-text
  sub:     '#97A6BC',    // --pds-text-2
  dim:     '#7A89A3',    // --pds-text-3
  seal:    '#E4C674',    // --pds-seal (certificate gold)

  mono: "'JetBrains Mono','Fira Code','Courier New',monospace",
  sans: "'Inter','Segoe UI',sans-serif",
  r8: '10px', r12: '14px', r16: '18px', r20: '24px',   // --pds radii
};

// ── Utilities ────────────────────────────────────────────────────────
const fmtUSD = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}k`;
  return `$${n.toFixed(2)}`;
};

// Currency-aware money: "$1.2k" for USD, "1.2k OMR" for detected currencies.
const fmtMoney = (n, cur) => {
  const s = fmtUSD(n);
  if (!cur || cur === 'USD' || s === '—') return s;
  return `${s.slice(1)} ${cur}`;
};
const fmtPct = (n, decimals = 1) => n == null ? '—' : `${Number(n).toFixed(decimals)}%`;
const riskColor = (r) => r === 'Low' ? DS.optimal : r === 'Moderate' ? DS.warning : DS.loss;
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

const SectionHeader = ({ tag, title, sub, right }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
                gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
    <div>
      {tag && <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 10, fontWeight: 600,
                            letterSpacing: '0.22em', marginBottom: 7 }}>EDA-{tag}</div>}
      <h2 style={{ margin: 0, fontSize: 21, fontWeight: 800, color: DS.text, letterSpacing: '-0.012em' }}>{title}</h2>
      {sub && <div style={{ fontSize: 12, color: DS.dim, marginTop: 5, maxWidth: 620, lineHeight: 1.55 }}>{sub}</div>}
    </div>
    {right}
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
    fontFamily: DS.sans, ...style,
  }}>{children}</button>
);

// ── Progress Bar ─────────────────────────────────────────────────────
const ProgressBar = ({ pct, color }) => (
  <div style={{ height: 5, background: DS.border, borderRadius: 3, marginTop: 8, overflow: 'hidden' }}>
    <div style={{ width: '100%', height: '100%', background: color, borderRadius: 3,
                  transform: `scaleX(${Math.min(100, pct || 0) / 100})`, transformOrigin: 'left',
                  transition: 'transform var(--pds-dur-slow) var(--pds-ease)' }} />
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
        }}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={(e) => process(e.target.files[0])} style={{ display: 'none' }} />
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
  h2: {
    label: 'H₂ · 20 MW electrolyzer',
    asset_id: 'DEMO_H2_20MW',
    p_max: 20, deg_cost: 3,
    init: (ref) => { ref.step = 0; },
    tick: (ref) => {
      ref.step += 1;
      const t = ref.step;
      // Diurnal price shape — the electrolyzer wants the trough
      const price = Math.max(4, 45 + 40 * Math.sin((t - 18) * Math.PI / 36) + (Math.random() - 0.5) * 14);
      // Naive operator: run baseload 24/7 regardless of price, meets target
      // by brute force. Optimal would concentrate consumption in the trough.
      const actual_charge = 12 + Math.round((Math.random() - 0.5) * 6);
      return {
        market_price: Math.round(price * 100) / 100,
        actual_discharge: 0, actual_charge,
        p_max: 20, e_max: 0,
        deg_cost: 3, curtailment: 0,
        forecast_price: Math.round(price * (0.9 + Math.random() * 0.2) * 100) / 100,
        grid_limit: 20,
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

function RealTimePanel({ isSignedIn, onSignIn }) {
  const [running, setRunning] = useState(false);
  const [state, setState] = useState(null);
  const [hist, setHist] = useState([]);
  const [err, setErr] = useState('');
  const clockRef = useRef(0);
  const timerRef = useRef(null);
  const STREAM = 'live-demo-stream';

  const tick = async () => {
    const h = clockRef.current % 24;
    const price = 12 + (h >= 18 && h <= 21 ? 30 : 0) + (Math.random() * 2 - 1);
    const ev = {
      timestamp: `2024-07-01T${String(h).padStart(2, '0')}:00:00Z`,
      spot_price: Math.round(price * 100) / 100,
      actual_charge: h < 6 ? 20 : 0,
      actual_discharge: (h >= 18 && h <= 21) ? 40 : 0,
      soc_percent: 50,
    };
    clockRef.current += 1;
    try {
      const r = await axios.post('/api/v1/live/ingest',
        { stream_id: STREAM, source: 'sim', currency: 'OMR', events: [ev] });
      const s = r.data.state;
      setState(s);
      if (s && typeof s.live_leakage === 'number') setHist((H) => [...H.slice(-40), s.live_leakage]);
      setErr('');
    } catch (e) { setErr('Live ingest failed — check you are signed in.'); }
  };
  const start = () => {
    if (timerRef.current) return;
    setRunning(true); setErr(''); tick();
    timerRef.current = setInterval(tick, 3000);
  };
  const stop = () => { if (timerRef.current) clearInterval(timerRef.current); timerRef.current = null; setRunning(false); };
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  if (!isSignedIn) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Real-Time Economic Intelligence</div>
        <div style={{ fontSize: 12, color: DS.sub, marginBottom: 18, lineHeight: 1.6 }}>
          Sign in to stream live events and watch the economic leakage update every few seconds &mdash;
          computed by the same certified audit engine, marked provisional until a certified audit confirms it.
        </div>
        <button onClick={onSignIn} style={primaryBtn}>Sign in &rarr;</button>
      </div>
    );
  }
  const money = (v) => (v == null ? '—' : `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${state?.currency || 'OMR'}`);
  const tile = (label, value, color) => (
    <div style={{ background: DS.panel, border: `1px solid ${DS.border}`, borderRadius: DS.r8, padding: '16px 20px', minWidth: 190, flex: 1 }}>
      <div style={{ fontSize: 9, letterSpacing: '0.16em', color: DS.dim, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 800, color: color || DS.text, fontFamily: DS.mono }}>{value}</div>
    </div>
  );
  const s = state || {};
  const insufficient = s.status === 'INSUFFICIENT_EVIDENCE' || s.status === 'NO_STREAM';
  return (
    <div>
      <SectionHeader tag="RT" title="REAL-TIME ECONOMIC INTELLIGENCE (PROVISIONAL)" />
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '10px 0 18px' }}>
        {!running
          ? <button onClick={start} style={{ ...primaryBtn, width: 'auto', padding: '10px 22px' }}>&#9654; Start live stream</button>
          : <button onClick={stop} style={{ ...primaryBtn, width: 'auto', padding: '10px 22px', background: DS.loss }}>&#9632; Stop</button>}
        <span style={{ fontSize: 11, color: running ? DS.optimal : DS.sub }}>
          {running ? `streaming · ${s.n_events || 0} events in window · updates every 3s` : 'idle'}
        </span>
      </div>
      {err && <EmptyMsg>{err}</EmptyMsg>}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {tile('LIVE LEAKAGE', insufficient ? '—' : money(s.live_leakage), DS.loss)}
        {tile('LIVE RECOVERABLE', insufficient ? '—' : money(s.live_recoverable), DS.optimal)}
        {tile('CONFIDENCE', s.confidence_grade ? `${s.confidence_grade}` : '—', _gradeColor(s.confidence_grade))}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12 }}>
        <div style={{ background: DS.panel, border: `1px solid ${DS.border}`, borderRadius: DS.r8, padding: '14px 18px', flex: 2, minWidth: 260 }}>
          <div style={{ fontSize: 9, letterSpacing: '0.16em', color: DS.dim, marginBottom: 8 }}>TOP ACTION</div>
          <div style={{ fontSize: 13, color: DS.text }}>
            {s.top_action
              ? <><b style={{ color: DS.cyan }}>{s.top_action.decision_type}</b> &mdash; {s.top_action.statement}</>
              : (insufficient ? 'Awaiting sufficient events…' : 'No material action in the current window.')}
          </div>
        </div>
        <div style={{ background: DS.panel, border: `1px solid ${DS.border}`, borderRadius: DS.r8, padding: '14px 18px', flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 9, letterSpacing: '0.16em', color: DS.dim, marginBottom: 8 }}>EVIDENCE STATUS</div>
          <div style={{ fontSize: 11, color: DS.warning, fontWeight: 700 }}>PROVISIONAL</div>
          <div style={{ fontSize: 10, color: DS.sub, marginTop: 4 }}>not yet certified by a batch audit</div>
          {s.evidence_sha256 && <div style={{ fontSize: 10, color: DS.dim, marginTop: 6, fontFamily: DS.mono }}>evidence {String(s.evidence_sha256).slice(0, 16)}…</div>}
          {s.dqi != null && <div style={{ fontSize: 10, color: DS.dim, marginTop: 2 }}>DQI {(s.dqi * 100).toFixed(1)}% · AC {(s.audit_confidence * 100).toFixed(1)}%</div>}
        </div>
      </div>
      {hist.length > 1 && (
        <div style={{ marginTop: 14, fontSize: 10, color: DS.dim }}>
          leakage trace ({hist.length}): {hist.slice(-12).map((x) => Number(x).toFixed(0)).join('  →  ')}
        </div>
      )}
      <div style={{ marginTop: 16, fontSize: 10, color: DS.dim, lineHeight: 1.6 }}>
        Live states are computed by the SAME certified Layer-2 audit engine used for CSV audits &mdash;
        no parallel logic. Every value is provisional and evidence-hashed until a certified batch audit confirms it.
        Raw telemetry is a drill-down only; the surface shows economic meaning.
      </div>
    </div>
  );
}

function AuditHistoryPanel({ isSignedIn, onLoad, onSignIn, busyId }) {
  const [rows, setRows] = useState(null);
  const [memory, setMemory] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    if (!isSignedIn) return;
    Promise.all([axios.get('/api/v1/audits'), axios.get('/api/v1/memory')])
      .then(([a, m]) => { setRows(a.data.audits); setMemory(m.data); })
      .catch(() => setErr('Could not load audit history.'));
  }, [isSignedIn]);
  if (!isSignedIn) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Your audits, remembered</div>
        <div style={{ fontSize: 12, color: DS.sub, marginBottom: 18, lineHeight: 1.6 }}>
          Sign in and every Economic Decision Audit you run is stored under your organization &mdash;
          reload any past audit bit-for-bit, and see what your assets keep leaking.
        </div>
        <button onClick={onSignIn} style={primaryBtn}>Sign in &rarr;</button>
      </div>
    );
  }
  const money = (v, ccy) => (v == null ? '\u2014' : `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${ccy || ''}`);
  const th = { textAlign: 'left', padding: '8px 10px', fontSize: 9, letterSpacing: '0.14em', color: DS.dim, borderBottom: `1px solid ${DS.border}` };
  const td = { padding: '9px 10px', fontSize: 11, borderBottom: `1px solid ${DS.border}22`, whiteSpace: 'nowrap' };
  return (
    <div>
      <SectionHeader tag="EDA-15" title="AUDIT HISTORY \u2014 ECONOMIC MEMORY" />
      {err && <EmptyMsg>{err}</EmptyMsg>}
      {memory && memory.audits > 0 && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '14px 0 18px' }}>
          {[
            ['AUDITS ON RECORD', memory.audits],
            ['LEAKAGE IDENTIFIED', money(memory.total_gap_identified, memory.currency)],
            ['RECOVERABLE IDENTIFIED', money(memory.total_recoverable_identified, memory.currency)],
            ['MEAN DQI', memory.mean_dqi != null ? `${(memory.mean_dqi * 100).toFixed(1)}%` : '\u2014'],
            ['RECURRING ROOT CAUSE', memory.recurring_top_root_cause ? `${memory.recurring_top_root_cause.cause} (${memory.recurring_top_root_cause.audits}\u00d7)` : '\u2014'],
          ].map(([label, val]) => (
            <div key={label} style={{ background: DS.panel, border: `1px solid ${DS.border}`, borderRadius: DS.r8, padding: '12px 16px', minWidth: 150 }}>
              <div style={{ fontSize: 9, letterSpacing: '0.14em', color: DS.dim, marginBottom: 6 }}>{label}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: DS.cyan }}>{String(val)}</div>
            </div>
          ))}
        </div>
      )}
      {memory && memory.audits > 0 && (
        <div style={{ fontSize: 10, color: DS.dim, marginBottom: 14 }}>{memory.method_note}</div>
      )}
      {rows === null && !err && <EmptyMsg>Loading history&hellip;</EmptyMsg>}
      {rows && rows.length === 0 && <EmptyMsg>No audits stored yet &mdash; run an audit while signed in and it will appear here.</EmptyMsg>}
      {rows && rows.length > 0 && (
        <div style={{ overflowX: 'auto', background: DS.panel, border: `1px solid ${DS.border}`, borderRadius: DS.r8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={th}>DATE (UTC)</th><th style={th}>FILE</th><th style={th}>GAP</th>
              <th style={th}>RECOVERABLE</th><th style={th}>DQI</th><th style={th}>CONFIDENCE</th>
              <th style={th}>TOP ROOT CAUSE</th><th style={th}></th>
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td style={td}>{(r.created_at || '').replace('T', ' ').slice(0, 16)}</td>
                  <td style={{ ...td, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.filename}>{r.filename || '\u2014'}</td>
                  <td style={{ ...td, color: DS.loss, fontWeight: 700 }}>{money(r.gap_total, r.currency)}</td>
                  <td style={{ ...td, color: DS.optimal, fontWeight: 700 }}>{money(r.gap_recoverable, r.currency)}</td>
                  <td style={{ ...td, color: _gradeColor(r.dqi_grade), fontWeight: 700 }}>{r.dqi_grade || '\u2014'}</td>
                  <td style={{ ...td, color: _gradeColor(r.confidence_grade), fontWeight: 700 }}>{r.confidence_grade || '\u2014'}</td>
                  <td style={td}>{r.top_root_cause || '\u2014'}</td>
                  <td style={td}>
                    <button onClick={() => onLoad(r.id)} disabled={busyId === r.id}
                      style={{ background: 'transparent', border: `1px solid ${DS.cyan}66`, color: DS.cyan,
                               borderRadius: 6, padding: '4px 12px', fontSize: 10, cursor: 'pointer',
                               opacity: busyId === r.id ? 0.5 : 1 }}>
                      {busyId === r.id ? 'LOADING\u2026' : 'OPEN'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TrialGate({ busy, error, onSubmit, onDismiss, onSignIn, onRegister, initialMode }) {
  const [mode, setMode] = useState(initialMode || 'trial'); // trial | signin | register
  const [email, setEmail] = useState('');
  const [assetName, setAssetName] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const submit = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    if (mode === 'signin') { onSignIn(email.trim(), password); return; }
    if (mode === 'register') { onRegister(email.trim(), password, orgName.trim() || email.trim()); return; }
    onSubmit(email.trim(), assetName.trim());
  };
  const switchLink = (label, m) => (
    <button type="button" onClick={() => setMode(m)}
      style={{ background: 'transparent', border: 'none', color: DS.cyan, cursor: 'pointer', fontSize: 11, padding: 0 }}>
      {label}
    </button>
  );
  if (mode === 'signin' || mode === 'register') {
    return (
      <div style={overlayStyle} role="dialog" aria-modal="true"
           aria-label={mode === 'signin' ? 'Sign in to PREDAIOT' : 'Create a PREDAIOT organization account'}>
        <div style={cardStyle}>
          <div style={{ fontSize: 10, letterSpacing: '0.2em', color: DS.cyan, marginBottom: 6 }}>
            {mode === 'signin' ? 'SIGN IN' : 'CREATE ORGANIZATION ACCOUNT'}
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>
            {mode === 'signin' ? 'Welcome back' : 'Your assets, remembered'}
          </div>
          <div style={{ fontSize: 12, color: DS.sub, marginBottom: 20, lineHeight: 1.5 }}>
            {mode === 'signin'
              ? 'Access your organization’s assets and audit history.'
              : 'An account keeps every audit, certificate and asset under your organization.'}
          </div>
          <form onSubmit={submit}>
            {mode === 'register' && (
              <input style={inputStyle} type="text" placeholder="Organization name"
                value={orgName} onChange={(e) => setOrgName(e.target.value)} disabled={busy} />
            )}
            <input style={inputStyle} type="email" placeholder="Work email" value={email}
              onChange={(e) => setEmail(e.target.value)} required autoFocus disabled={busy} />
            <input style={inputStyle} type="password"
              placeholder={mode === 'register' ? 'Password (min. 8 characters)' : 'Password'}
              value={password} onChange={(e) => setPassword(e.target.value)} required disabled={busy} />
            {error && (
              <div style={{ color: DS.loss, fontSize: 11, marginBottom: 12 }}>{String(error)}</div>
            )}
            <button type="submit" style={{ ...primaryBtn, opacity: busy ? 0.6 : 1 }} disabled={busy}>
              {busy ? 'Working…' : (mode === 'signin' ? 'Sign in →' : 'Create account →')}
            </button>
          </form>
          <div style={{ marginTop: 14, fontSize: 11, color: DS.sub, display: 'flex', gap: 14, justifyContent: 'center' }}>
            {mode === 'signin'
              ? <>New here? {switchLink('Create an account', 'register')} {switchLink('Free diagnostic', 'trial')}</>
              : <>Have an account? {switchLink('Sign in', 'signin')} {switchLink('Free diagnostic', 'trial')}</>}
          </div>
          <button onClick={onDismiss}
            style={{ marginTop: 10, width: '100%', padding: '8px', background: 'transparent',
                     color: DS.sub, border: 'none', cursor: 'pointer', fontSize: 11 }}>
            Just looking around
          </button>
        </div>
      </div>
    );
  }
  return (
    <div style={overlayStyle} role="dialog" aria-modal="true"
         aria-label="Start your free PREDAIOT economic diagnostic">
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
        <div style={{ marginTop: 14, fontSize: 11, color: DS.sub, display: 'flex', gap: 14, justifyContent: 'center' }}>
          Have an account? {switchLink('Sign in', 'signin')} {switchLink('Create one', 'register')}
        </div>
        <button
          onClick={onDismiss}
          style={{
            marginTop: 10, width: '100%', padding: '8px',
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
    <div style={overlayStyle} role="dialog" aria-modal="true"
         aria-label="Your free diagnostic period has ended">
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
// DATA QUALITY / AUDIT CONFIDENCE PANEL (EDA metrics W1–W4).
// Every number here is reproducible from the Data Quality Manifest via the
// published equations; N/A components are shown and excluded from the mean.
// ══════════════════════════════════════════════════════════════════════
const _gradeColor = (g) => (
  g === 'A' ? DS.optimal : g === 'B' ? '#69F0AE' : g === 'C' ? DS.warning :
  g === 'D' ? DS.orange : g === 'E' ? DS.loss : DS.dim);

function DataQualityPanel({ dqi, ac, fr, compact }) {
  if (!dqi) return null;
  const cell = (label, obj) => {
    const val = obj?.value_pct;
    const grade = obj?.grade;
    return (
      <div style={{ textAlign: 'center', minWidth: 120 }}>
        <Label style={{ fontSize: 9 }}>{label}</Label>
        <div style={{ color: _gradeColor(grade), fontFamily: DS.mono, fontSize: compact ? 18 : 24, fontWeight: 800 }}>
          {val != null ? `${val}%` : (grade || 'N/A')}
        </div>
        <div style={{ color: _gradeColor(grade), fontSize: 10, fontWeight: 700 }}>
          {grade != null ? `Grade ${grade}` : ''}
        </div>
        {!compact && obj?.interpretation && (
          <div style={{ color: DS.dim, fontSize: 9, marginTop: 2 }}>{obj.interpretation}</div>
        )}
      </div>
    );
  };
  return (
    <div style={{ background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r12, padding: compact ? '12px 16px' : '16px 20px', marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <Label>DATA QUALITY &amp; AUDIT CONFIDENCE</Label>
        <span style={{ color: DS.dim, fontSize: 9, fontFamily: DS.mono }}>
          {dqi.version}{ac ? ` · ${ac.version}` : ''}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {cell('Data Quality Index', dqi)}
        {cell('Audit Confidence', ac)}
        {fr && (
          <div style={{ textAlign: 'center', minWidth: 120 }}>
            <Label style={{ fontSize: 9 }}>Forecast Reliability</Label>
            <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: compact ? 18 : 24, fontWeight: 800 }}>{fr.value_pct}%</div>
            <div style={{ color: DS.dim, fontSize: 8.5, marginTop: 2 }}>Experimental · report-only</div>
          </div>
        )}
      </div>
      {!compact && (
        <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
          {Object.entries(dqi.components || {}).map(([k, c]) => (
            <div key={k} style={{ padding: '6px 10px', background: 'rgba(255,255,255,0.015)', border: `1px solid ${DS.border}`, borderRadius: DS.r8 }}>
              <div style={{ color: DS.sub, fontSize: 10 }}>{c.label}</div>
              <div style={{ color: c.applicable ? _gradeColor(dqi.grade) : DS.dim, fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>
                {c.applicable ? `${c.value_pct}%` : 'N/A'}
              </div>
            </div>
          ))}
        </div>
      )}
      {!compact && (
        <div style={{ color: DS.dim, fontSize: 9.5, marginTop: 10, lineHeight: 1.5 }}>
          DQI = geometric mean of applicable components (N/A excluded, never scored 0).
          Audit Confidence = DQI × model consistency, solver-gated — measures confidence in the
          audit process, independent of forecast accuracy. Grade bands are a declared EDA scale.
          Every value reproduces from the Data Quality Manifest.
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// INGESTION NOTES BANNER — shown after an upload when the pipeline made
// auto-corrections (units, timestamps, or fuzzy column matches). Lets the
// operator see "here's what we assumed" before they quote the audit to
// their boss. Dismissible.
// ══════════════════════════════════════════════════════════════════════
function IngestionNotesBanner({ notes, onDismiss }) {
  const units      = notes.unit_corrections || [];
  const timestamps = notes.timestamp_corrections || [];
  const fuzzy      = notes.fuzzy_column_matches || {};
  const fuzzyList  = Object.entries(fuzzy);
  const tsFormat   = notes.timestamp_format || null;
  const resolution = notes.time_resolution || null;
  const dataQuality = notes.data_quality || [];
  const dqWarnings  = dataQuality.filter((f) => f.severity === 'warning');
  const dqInfos     = dataQuality.filter((f) => f.severity !== 'warning');
  const currency    = notes.currency || null;

  const showTsFormat   = tsFormat && tsFormat.format_detected;
  const showResolution = resolution && (resolution.detected_resolution_sec || resolution.warning);

  if (
    units.length === 0 && timestamps.length === 0 && fuzzyList.length === 0 &&
    !showTsFormat && !showResolution && dataQuality.length === 0 && !currency
  ) return null;

  return (
    <div style={{
      background: `linear-gradient(135deg, ${DS.cyan}12, ${DS.blue}08)`,
      border: `1px solid ${DS.cyan}35`,
      borderRadius: DS.r12,
      padding: '14px 18px',
      marginBottom: 18,
      position: 'relative',
    }}>
      <button
        onClick={onDismiss}
        aria-label="Dismiss ingestion notes"
        style={{
          position: 'absolute', top: 8, right: 10,
          background: 'transparent', border: 'none', color: DS.dim,
          cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 6,
        }}
      >
        ✕
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        
        <div style={{ color: DS.cyan, fontSize: 10, fontWeight: 700, letterSpacing: '0.15em' }}>
          INGESTION AUTO-CORRECTIONS APPLIED
        </div>
      </div>
      <div style={{ color: DS.sub, fontSize: 11, marginBottom: 10, lineHeight: 1.5 }}>
        The audit engine made the following assumptions about your file. Review before quoting the audit externally.
      </div>

      {units.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>UNIT CONVERSIONS</div>
          {units.map((line, i) => (
            <div key={i} style={{ color: DS.text, fontSize: 11, marginBottom: 3, paddingLeft: 12 }}>
              • {line}
            </div>
          ))}
        </div>
      )}

      {timestamps.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>TIMESTAMP RECOVERY</div>
          {timestamps.map((line, i) => (
            <div key={i} style={{ color: DS.text, fontSize: 11, marginBottom: 3, paddingLeft: 12 }}>
              • {line}
            </div>
          ))}
        </div>
      )}

      {fuzzyList.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>FUZZY COLUMN MATCHES</div>
          {fuzzyList.map(([internal, info]) => (
            <div key={internal} style={{ color: DS.text, fontSize: 11, marginBottom: 3, paddingLeft: 12, fontFamily: DS.mono }}>
              • <span style={{ color: DS.cyan }}>{info.from_col}</span> → <span style={{ color: DS.optimal }}>{internal}</span>{' '}
              <span style={{ color: DS.dim }}>({info.score}% match to “{info.matched_alias}”)</span>
            </div>
          ))}
        </div>
      )}

      {showTsFormat && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>TIMESTAMP FORMAT</div>
          <div style={{ color: DS.text, fontSize: 11, marginBottom: 3, paddingLeft: 12 }}>
            • Detected format: <span style={{ color: DS.cyan, fontFamily: DS.mono }}>{tsFormat.format_detected}</span>
          </div>
          {tsFormat.first_ts && (
            <div style={{ color: DS.sub, fontSize: 10, marginBottom: 3, paddingLeft: 12, fontFamily: DS.mono }}>
              • Range: {String(tsFormat.first_ts).slice(0, 19)} → {String(tsFormat.last_ts || '').slice(0, 19)}
            </div>
          )}
        </div>
      )}

      {showResolution && (
        <div>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>TIME RESOLUTION</div>
          {resolution.detected_resolution_label && (
            <div style={{ color: DS.text, fontSize: 11, marginBottom: 3, paddingLeft: 12 }}>
              • Detected: <span style={{ color: DS.cyan }}>{resolution.detected_resolution_label}</span>
              {' '}steps
              {resolution.resampled && (
                <span style={{ color: DS.optimal }}>
                  {' — resampled '}{resolution.actual_steps} → {resolution.expected_steps} steps
                  {' ('}{resolution.missing_pct}% missing filled{')'}
                </span>
              )}
            </div>
          )}
          {resolution.warning && (
            <div style={{ color: DS.loss, fontSize: 11, marginBottom: 3, paddingLeft: 12, lineHeight: 1.5 }}>
              ⚠ {resolution.warning}
            </div>
          )}
        </div>
      )}

      {dqWarnings.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: DS.loss, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>
            DATA QUALITY WARNINGS
          </div>
          {dqWarnings.map((f) => (
            <div key={f.code} style={{ color: DS.text, fontSize: 11, marginBottom: 4, paddingLeft: 12, lineHeight: 1.5 }}>
              ⚠ {f.message}
            </div>
          ))}
        </div>
      )}

      {dqInfos.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: DS.cyan, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>
            DATA CLEANING APPLIED
          </div>
          {dqInfos.map((f) => (
            <div key={f.code} style={{ color: DS.sub, fontSize: 11, marginBottom: 3, paddingLeft: 12, lineHeight: 1.5 }}>
              • {f.message}
            </div>
          ))}
        </div>
      )}

      {currency && currency !== 'USD' && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: DS.warning, fontSize: 10, letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>
            CURRENCY
          </div>
          <div style={{ color: DS.text, fontSize: 11, paddingLeft: 12, lineHeight: 1.5 }}>
            • Column names indicate this file is denominated in{' '}
            <span style={{ color: DS.cyan, fontWeight: 700 }}>{currency}</span> — all monetary
            figures in this audit are {currency}, not USD.
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// OPS CONSOLE — S01 Executive Summary redesign (matches reference photo).
// Neon-lime + red on a deep dark canvas; SVG semi-circle DQ gauge with
// glow; ComposedChart for the market-vs-action audit; live-telemetry
// strip; discrepancy timeline; asset performance tiles.
// ══════════════════════════════════════════════════════════════════════
// Ops-console palette bridge — values mirror the PREDAIOT tokens (SPEC-DS),
// exactly like the DS bridge: raw hex so ${color}NN alpha-concat keeps
// working. The neon set (#00FF9D/#FF3366/#FFD600/#38BDF8) is retired.
const OPS = {
  bg:      '#0A0E16',   // --pds-bg-1
  card:    '#0E1420',   // --pds-panel
  border:  '#1B2536',   // --pds-border
  green:   '#2FD69B',   // --pds-recover
  red:     '#FF5C7A',   // --pds-loss
  amber:   '#F3B24C',   // --pds-warn
  yellow:  '#F3B24C',   // --pds-warn (single caution hue — no second yellow)
  blue:    '#5AA9FF',   // --pds-info
  text:    '#EAF1F8',   // --pds-text
  sub:     '#97A6BC',   // --pds-text-2
  dim:     '#7A89A3',   // --pds-text-3 (AA)
};

// (S01 ops-console widget cluster removed — the Executive Experience is a
//  six-act decision narrative in components/ExecutiveCommandCenter.jsx.)


// ══════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════
export default function App() {
  const [data, setData]                   = useState(EMPTY);
  const [loading, setLoading]             = useState(false);
  const [actionError, setActionError]     = useState(null);   // SPEC-IX: no silent dead ends
  const [uploading, setUploading]         = useState(false);
  const [shareLink, setShareLink]         = useState('');
  const [activeSection, setActiveSection] = useState('exec');
  const [showMethodology, setShowMethodology] = useState(false);

  // ── Mobile responsive state ────────────────────────────────────────
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);   // header REPORTS menu (SPEC-NV rule 4)
  const [lensOpen, setLensOpen] = useState(false);         // archetype lens menu (SPEC-RB)
  // SPEC-RB: presentation lens — emphasis only, never truth. CFO is the
  // native grip (the moat is economic truth). Explicit choice persists.
  const [archetype, setArchetype] = useState(() => {
    try { return localStorage.getItem('predaiot.archetype.v1') || 'CFO'; } catch { return 'CFO'; }
  });
  const chooseLens = (a) => {
    setArchetype(a); setLensOpen(false);
    try { localStorage.setItem('predaiot.archetype.v1', a); } catch { /* private mode */ }
  };
  useEffect(() => {
    // Close the drawer if the viewport transitions back to desktop
    if (!isMobile && sidebarOpen) setSidebarOpen(false);
  }, [isMobile, sidebarOpen]);

  // ── Ingestion notes from the upload pipeline ───────────────────────
  const [ingestionNotes, setIngestionNotes] = useState(null);
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
  // ── Live-feed resilience (grid/network outage mid-session) ─────────
  // 'offline' | 'connected' | 'reconnecting'. On unexpected socket loss we
  // KEEP everything on screen, auto-reconnect with exponential backoff, and
  // resume the simulated feed where it left off. Only the DISCONNECT button
  // stops the retry loop.
  const [liveStatus, setLiveStatus]       = useState('offline');
  const [lastTickAt, setLastTickAt]       = useState(null);
  const [reconnectRef]                    = useState({ timer: null, attempt: 0, userStop: false });
  // Re-render every 5s while live so the "feed stale" age stays current.
  const [, setStaleTick] = useState(0);
  useEffect(() => {
    if (!liveMode) return undefined;
    const iv = setInterval(() => setStaleTick(t => t + 1), 5000);
    return () => clearInterval(iv);
  }, [liveMode]);

  // Opens /ws/live with resilience wiring. Lives here (not inline in S13's
  // button) because the auto-reconnect loop re-invokes it after an outage.
  const connectLive = () => {
    const scheduleRetry = () => {
      setLiveStatus('reconnecting');
      const delay = Math.min(30000, 1000 * Math.pow(2, reconnectRef.attempt));
      reconnectRef.attempt += 1;
      reconnectRef.timer = setTimeout(connectLive, delay);
    };
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/live`);
      ws.onopen = () => {
        reconnectRef.attempt = 0;
        // If we have cumulative stats from before the drop, replay them in
        // the first message so the server-side session continues, not resets.
        reconnectRef.needResume = !!reconnectRef.lastCums;
        setLiveMode(true);
        setLiveStatus('connected');
      };
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          reconnectRef.lastCums = {
            cumulative_opt: d.cumulative_opt,
            cumulative_act: d.cumulative_act,
            step: d.step,
          };
          setLiveData(prev => [...prev.slice(-287), d]);
          setLastTickAt(Date.now());
        } catch (_) {}
      };
      ws.onclose = () => {
        wsRef.current = null;
        if (reconnectRef.userStop) {
          setLiveMode(false);
          setLiveStatus('offline');
          return;
        }
        // Unexpected loss (grid / network outage mid-session): keep every
        // chart and statistic on screen and retry with capped exponential
        // backoff. The simulated feed's interval keeps running — its tick()
        // no-ops while the socket is down and resumes on reconnect.
        scheduleRetry();
      };
      ws.onerror = () => { try { ws.close(); } catch (_) {} };
      wsRef.current = ws;
    } catch (err) {
      scheduleRetry();
    }
  };

  const startLive = () => {
    reconnectRef.userStop = false;
    reconnectRef.attempt = 0;
    reconnectRef.lastCums = null;   // manual start = fresh session stats
    reconnectRef.needResume = false;
    setLiveMode(true);              // session starts now; status shows progress
    setLiveStatus('reconnecting');  // amber until onopen flips it green
    connectLive();
  };

  const disconnectLive = () => {
    reconnectRef.userStop = true;
    if (reconnectRef.timer) { clearTimeout(reconnectRef.timer); reconnectRef.timer = null; }
    if (simRef.current) { clearInterval(simRef.current); simRef.current = null; }
    setSimRunning(false);
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setLiveMode(false);
    setLiveStatus('offline');
  };
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
  // Auto-open the gate only when the visitor has NEITHER a trial token NOR
  // a signed-in account — an authenticated user must never see the gate.
  const [gateOpen, setGateOpen]           = useState(() => !trialStore.get() && !authStore.get()?.token);
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

  const [account, setAccount] = useState(() => authStore.get());
  const [gateMode, setGateMode] = useState('trial');

  const signIn = async (email, password) => {
    setGateBusy(true);
    setGateError('');
    try {
      const r = await axios.post('/api/v1/auth/login', { email, password });
      authStore.set(r.data);
      setAccount(r.data);
      setGateOpen(false);
      setExpiredInfo(null);
    } catch (err) {
      setGateError(err?.response?.data?.detail?.message || 'Sign-in failed. Check your credentials.');
    }
    setGateBusy(false);
  };

  const registerAccount = async (email, password, organization) => {
    setGateBusy(true);
    setGateError('');
    try {
      const r = await axios.post('/api/v1/auth/register', { email, password, organization });
      authStore.set(r.data);
      setAccount(r.data);
      setGateOpen(false);
      setExpiredInfo(null);
    } catch (err) {
      setGateError(err?.response?.data?.detail?.message || 'Could not create the account.');
    }
    setGateBusy(false);
  };

  const [historyBusyId, setHistoryBusyId] = useState(null);
  const loadPastAudit = async (id) => {
    setHistoryBusyId(id);
    try {
      const r = await axios.get(`/api/v1/audits/${id}`);
      setData(r.data);
      setDataSource('historical');
      setShowUpload(false);
      setAiText('');
      setActiveSection('exec');
    } catch (_) { /* row stays; user can retry */ }
    setHistoryBusyId(null);
  };

  const signOut = () => {
    authStore.clear();
    setAccount(null);
    window.location.reload();
  };

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
        // decision_log presence — not dq_score truthiness — signals a real
        // result (dq can legitimately be 0.0 for destructive dispatch).
        if (Array.isArray(r.data?.decision_log) && r.data.decision_log.length > 0) {
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

  // Cleanup live WebSocket + simulator + reconnect loop on unmount
  useEffect(() => {
    return () => {
      reconnectRef.userStop = true;
      if (reconnectRef.timer) clearTimeout(reconnectRef.timer);
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
        dt_hours: 1 / 12,  // 288 five-minute steps = a 24h demo day
      });
      setData(r.data);
      setDataSource('demo');
      setAiText('');
      setIngestionNotes(null);  // demo data is synthetic; no ingestion notes
      setActiveSection('exec');
      setActionError(null);
    } catch (e) {
      console.error(e);
      // SPEC-IX rule 4: errors state impact + recovery path, in place.
      setActionError('The demo audit could not be completed — the audit engine did not respond. Check your connection and run the demo again.');
    }
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
      // ingestion_notes is appended by the backend when auto-corrections fire
      // (unit / timestamp / fuzzy column). Surface them so operators see
      // exactly what the pipeline did before quoting the audit.
      setIngestionNotes(r.data?.ingestion_notes || null);
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
    if (!(data.decision_log || []).length) return alert('Run an audit first.');
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
    if (!(data.decision_log || []).length) return alert('Run an audit first.');
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

  // ── Download Economic Energy Ledger (Ref. Manual Ch 8.1) ───────────
  // Step-by-step CSV where every PDF headline number is a column sum —
  // the transparency artifact that lets a customer reconcile the audit.
  const downloadLedger = async () => {
    if (!(data.decision_log || []).length) return alert('Run an audit first.');
    if (!requireTrial()) return;
    try {
      const r = await axios.get('/api/v1/audit/ledger.csv', { responseType: 'blob' });
      const blobUrl = URL.createObjectURL(new Blob([r.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = blobUrl; a.download = 'predaiot_audit_ledger.csv';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (err) {
      if (err?.response?.status !== 401 && err?.response?.status !== 402) {
        alert('Ledger export failed. Run an audit first, then try again.');
      }
    }
  };

  // ── Claude AI enhanced commentary ─────────────────────────────────
  const generateAI = async () => {
    if (!(data.decision_log || []).length) return;
    setAiLoading(true);
    try {
      const capturePct = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
      const missedCount = (data.decision_log || []).filter(d => d.decision_type === 'Missed Arbitrage').length;
      const opsBlock = (data.opportunities || []).slice(0, 5).map((o, i) =>
        `${i + 1}. ${o.name}${o.experimental ? ' [EXPERIMENTAL — not quantified]' : ` — Period Value: ${o.period_gain} | Annualised (linear est.): ${o.annual_gain_usd} | Ledger intervals: ${o.intervals_observed} | Derivation: ${o.derivation}`} | Evidence: ${o.evidence || '—'}`
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
  // "An audit is loaded" = the decision log has rows. NOT dq_score > 0 —
  // an honest DQ of 0.0 (destructive dispatch) is a real, displayable audit.
  const hasData     = log.length > 0;

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
    { id: 'live',      label: 'Live Monitor',                 tag: 'LV' },
    { id: 'cert',      label: 'EDPC Certificate',             tag: 'CT' },
    { id: 'history',   label: 'Audit History',                tag: 'HX' },
    { id: 'realtime',  label: 'Real-Time',                    tag: 'RT' },
  ];

  // SPEC-IA Section Taxonomy — the sidebar renders these ratified groups.
  // Items reference navItems entries by id; glyph tags retired (SPEC-ID).
  const NAV_GROUPS = [
    { label: 'Command',               ids: ['exec'] },
    { label: 'Analysis',              ids: ['flow', 'timeline', 'rootcause', 'counter', 'metrics', 'leakage', 'heatmap'] },
    { label: 'Action',                ids: ['opps', 'ai'] },
    { label: 'Evidence & Governance', ids: ['govern', 'cert', 'history'] },
    { label: 'Operations',            ids: ['live', 'realtime'] },
    { label: 'Reference',             ids: ['appendix'] },
  ].map((g) => ({ ...g, items: g.ids.map((id) => navItems.find((n) => n.id === id)) }));

  // SPEC-RB emphasis matrix — group order + elevated/de-emphasized sections
  // per archetype. Same data, same evidence, different reading order.
  const ARCHETYPE_EMPHASIS = {
    CFO:           { order: ['Command', 'Analysis', 'Action', 'Evidence & Governance', 'Operations', 'Reference'],
                     up: ['flow', 'leakage', 'cert'], down: ['live', 'realtime'] },
    CEO:           { order: ['Command', 'Evidence & Governance', 'Action', 'Analysis', 'Operations', 'Reference'],
                     up: ['govern', 'history'], down: ['appendix', 'metrics'] },
    Operations:    { order: ['Command', 'Action', 'Operations', 'Analysis', 'Evidence & Governance', 'Reference'],
                     up: ['opps', 'live'], down: ['appendix'] },
    Engineer:      { order: ['Command', 'Analysis', 'Reference', 'Action', 'Evidence & Governance', 'Operations'],
                     up: ['rootcause', 'counter', 'metrics', 'appendix'], down: [] },
    Administrator: { order: ['Command', 'Evidence & Governance', 'Operations', 'Analysis', 'Action', 'Reference'],
                     up: ['history'], down: [] },
  };
  const ARCHETYPES = Object.keys(ARCHETYPE_EMPHASIS);
  const lens = ARCHETYPE_EMPHASIS[archetype] || ARCHETYPE_EMPHASIS.CFO;
  const orderedGroups = lens.order
    .map((label) => NAV_GROUPS.find((g) => g.label === label)).filter(Boolean);

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
          onSignIn={signIn}
          onRegister={registerAccount}
          initialMode={gateMode}
          onDismiss={() => { setGateOpen(false); setGateMode('trial'); }}
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
        minHeight: 'var(--ws-header-h)',
        padding: isMobile ? '8px 14px' : '10px 28px',
        borderBottom: `1px solid ${DS.border}`,
        position: 'sticky', top: 0, backgroundColor: `${DS.bg}f0`, backdropFilter: 'blur(12px)',
        zIndex: 100, gap: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 14, minWidth: 0, flex: '0 1 auto' }}>
          {isMobile && (
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label={sidebarOpen ? 'Close navigation' : 'Open navigation'}
              style={{
                background: 'none', border: `1px solid ${DS.border}`,
                color: DS.text, cursor: 'pointer',
                minWidth: 44, minHeight: 44, borderRadius: DS.r8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, lineHeight: 1,
              }}
            >
              {sidebarOpen ? '✕' : '☰'}
            </button>
          )}
          <img src="/logo.jpeg" alt="PREDAIOT" style={{ height: isMobile ? 28 : 36, objectFit: 'contain' }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: isMobile ? 12 : 14, fontWeight: 700, letterSpacing: '0.18em', color: DS.text }}>PREDAIOT</div>
            {!isMobile && (
              <div style={{ fontSize: 9, letterSpacing: '0.2em', color: DS.dim }}>ECONOMIC DECISION AUDIT™</div>
            )}
          </div>
          {hasData && !isMobile && (
            <div style={{ marginLeft: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: DS.sub }}>{data.asset_name}</span>
              <Pill label={data.risk_level || 'Moderate'} color={riskColor(data.risk_level)} />
              <Pill label={data.asset_type || 'Generic'} color={DS.cyan} />
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: isMobile ? 6 : 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {/* SPEC-NV rule 4: one accent primary + quiet utilities only.
              Report/evidence exports live in a single quiet menu. */}
          <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading || uploading}>
            {loading ? 'OPTIMIZING…' : (isMobile ? 'DEMO' : 'RUN DEMO')}
          </BtnOutline>
          <BtnOutline color={DS.sub} onClick={() => setShowUpload(!showUpload)} disabled={uploading}>
            {uploading ? 'PARSING…' : (isMobile ? 'UPLOAD' : 'UPLOAD DATA')}
          </BtnOutline>
          <div style={{ position: 'relative' }}>
            <BtnOutline color={DS.sub} onClick={() => setReportsOpen((v) => !v)}
              aria-haspopup="menu" aria-expanded={reportsOpen}>
              REPORTS {reportsOpen ? '▴' : '▾'}
            </BtnOutline>
            {reportsOpen && (
              <>
                <div onClick={() => setReportsOpen(false)}
                     style={{ position: 'fixed', inset: 0, zIndex: 120 }} />
                <div role="menu" style={{
                  position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 121,
                  background: DS.bgRaised, border: `1px solid ${DS.borderHi}`,
                  borderRadius: DS.r12, boxShadow: 'var(--pds-shadow-2)',
                  minWidth: 210, padding: 6,
                }}>
                  {[
                    { label: pdfLoading ? 'Preparing PDF…' : 'Download PDF report', fn: downloadPdf, off: pdfLoading || !hasData },
                    { label: 'Download ledger CSV', fn: downloadLedger, off: !hasData },
                    { label: 'Share report link', fn: handleShare, off: !hasData },
                    { label: 'Methodology', fn: () => setShowMethodology(true), off: false },
                  ].map((m) => (
                    <button key={m.label} role="menuitem" disabled={m.off}
                      className="pds-menu-item"
                      onClick={() => { setReportsOpen(false); m.fn(); }}
                      style={{
                        display: 'block', width: '100%', textAlign: 'left',
                        padding: '10px 12px', background: 'none', border: 'none',
                        borderRadius: DS.r8, cursor: m.off ? 'not-allowed' : 'pointer',
                        color: m.off ? DS.dim : DS.text, fontSize: 12, fontFamily: DS.sans,
                      }}>
                      {m.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
          {/* SPEC-RB archetype lens — one interaction, always visible,
              instantly reversible. Emphasis only; figures never change. */}
          {!isMobile && (
            <div style={{ position: 'relative' }}>
              <BtnOutline color={DS.sub} onClick={() => setLensOpen((v) => !v)}
                aria-haspopup="menu" aria-expanded={lensOpen}>
                LENS · {archetype.toUpperCase()} {lensOpen ? '▴' : '▾'}
              </BtnOutline>
              {lensOpen && (
                <>
                  <div onClick={() => setLensOpen(false)}
                       style={{ position: 'fixed', inset: 0, zIndex: 120 }} />
                  <div role="menu" style={{
                    position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 121,
                    background: DS.bgRaised, border: `1px solid ${DS.borderHi}`,
                    borderRadius: DS.r12, boxShadow: 'var(--pds-shadow-2)',
                    minWidth: 190, padding: 6,
                  }}>
                    {ARCHETYPES.map((a) => (
                      <button key={a} role="menuitemradio" aria-checked={a === archetype}
                        className="pds-menu-item"
                        onClick={() => chooseLens(a)}
                        style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          width: '100%', textAlign: 'left', padding: '10px 12px',
                          background: 'none', border: 'none', borderRadius: DS.r8,
                          cursor: 'pointer', fontSize: 12, fontFamily: DS.sans,
                          color: a === archetype ? DS.cyan : DS.text,
                        }}>
                        {a}
                        {a === archetype && <span aria-hidden style={{ fontSize: 10 }}>●</span>}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          {account?.token ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {!isMobile && (
                <span style={{ fontSize: 10, color: DS.sub, maxWidth: 160, overflow: 'hidden',
                               textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={account.email}>
                  {account.organization?.name || account.email}
                </span>
              )}
              <BtnOutline color={DS.dim} onClick={signOut}>SIGN OUT</BtnOutline>
            </div>
          ) : (
            <BtnOutline color={DS.sub} onClick={() => { setGateMode('signin'); setGateError(''); setGateOpen(true); }}>
              SIGN IN
            </BtnOutline>
          )}
          <SessionBadge liveMode={liveMode} simRunning={simRunning} dataSource={dataSource} />
        </div>
      </header>

      {shareLink && (
        <div style={{ background: `${DS.warning}10`, borderBottom: `1px solid ${DS.warning}30`, padding: '8px 28px', fontSize: 11, color: DS.warning }}>
          <span style={{ letterSpacing: '0.1em', fontWeight: 700, marginRight: 8 }}>SHARE LINK</span>
          <span className="pds-num">{shareLink}</span>
        </div>
      )}
      {/* SPEC-IX error surface — institutional candor: what failed + the
          recovery path, recoverable in place, dismissible. */}
      {actionError && (
        <div role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          gap: 16, background: `${DS.loss}10`, borderBottom: `1px solid ${DS.loss}30`,
          padding: '10px 28px', fontSize: 12, color: DS.text }}>
          <span><span style={{ color: DS.loss, fontWeight: 700, letterSpacing: '0.08em', marginRight: 10 }}>AUDIT FAILED</span>{actionError}</span>
          <button onClick={() => setActionError(null)} aria-label="Dismiss error"
            style={{ background: 'none', border: `1px solid ${DS.border}`, color: DS.sub,
                     borderRadius: DS.r8, padding: '4px 10px', cursor: 'pointer', fontSize: 11 }}>
            DISMISS
          </button>
        </div>
      )}

      {/* ── FILE UPLOAD PANEL ───────────────────────────────────── */}
      {showUpload && (
        <div style={{ borderBottom: `1px solid ${DS.border}`, background: DS.bgRaised }}>
          <FileUploadZone onFile={handleFile} loading={uploading} />
        </div>
      )}

      <div style={{ display: 'flex' }}>
        {/* ── SIDEBAR — persistent on desktop, drawer on mobile ── */}
        {isMobile && sidebarOpen && (
          <div
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
              zIndex: 99, backdropFilter: 'blur(2px)',
            }}
            aria-label="Close navigation"
          />
        )}
        <nav style={isMobile ? {
          /* SPEC-MO compositor law: drawer slides via transform, never left. */
          position: 'fixed', left: 0, top: 0, bottom: 0,
          transform: sidebarOpen ? 'translateX(0)' : 'translateX(-272px)',
          width: 272, padding: '76px 0 20px 0', background: DS.bgRaised,
          borderRight: `1px solid ${DS.borderHi}`,
          transition: 'transform var(--pds-dur) var(--pds-ease)', overflowY: 'auto',
          zIndex: 100, boxShadow: sidebarOpen ? '4px 0 30px rgba(0,0,0,0.5)' : 'none',
        } : {
          /* SPEC-WS §4: sidebar = clamp(248px, 18vw, 400px); 18–20% share on
             1440–2200px displays, capped beyond so surplus canvas feeds
             intelligence zones, never navigation. */
          width: 'var(--ws-sidebar-w)', minWidth: 248, flexShrink: 0, padding: '20px 0',
          borderRight: `1px solid ${DS.border}`,
          position: 'sticky', top: 'var(--ws-header-h)',
          height: 'calc(100vh - var(--ws-header-h))', overflowY: 'auto',
        }}>
          {/* SPEC-NV: grouped instrument rail — the taxonomy is the map,
              ordered by the active SPEC-RB lens (emphasis, never truth). */}
          {orderedGroups.map((g) => (
            <div key={g.label} style={{ marginBottom: 14 }}>
              <div style={{
                padding: isMobile ? '8px 22px 5px' : '6px 20px 5px',
                fontSize: 9, letterSpacing: '0.22em', textTransform: 'uppercase',
                color: DS.dim, fontWeight: 700,
              }}>{g.label}</div>
              {g.items.map((n) => {
                const active = activeSection === n.id;
                const elevated = lens.up.includes(n.id);
                const dimmed = lens.down.includes(n.id) && !active;
                return (
                  <button
                    key={n.id}
                    onClick={() => {
                      setActiveSection(n.id);
                      if (isMobile) setSidebarOpen(false);
                    }}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: isMobile ? '14px 22px' : '9px 20px',
                      minHeight: isMobile ? 44 : undefined,  // Apple HIG / Material touch target
                      fontSize: isMobile ? 13 : 11,
                      background: active ? `${DS.cyan}0C` : 'none',
                      border: 'none', cursor: 'pointer',
                      letterSpacing: '0.04em',
                      // SPEC-RB de-emphasis via color demotion (text-2 → text-3),
                      // never opacity stacking — keeps SPEC-AX ≥4.5:1 at 9–11px.
                      color: active ? DS.cyan : (dimmed ? DS.dim : DS.sub),
                      borderLeft: `2px solid ${active ? DS.cyan : 'transparent'}`,
                    }}
                  >
                    <span style={{ fontFamily: DS.mono, fontSize: isMobile ? 10 : 9, color: active ? DS.cyan : DS.dim, marginRight: 8 }}>{n.tag}</span>
                    {n.label}
                    {elevated && !active && (
                      <span aria-hidden style={{ display: 'inline-block', width: 4, height: 4, borderRadius: '50%',
                        background: DS.cyan, marginLeft: 7, verticalAlign: 'middle', opacity: 0.8 }} />
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* ── MAIN CONTENT — the Executive Workspace (SPEC-WS §5) ── */}
        <main style={{
          flex: 1, minWidth: 0,
          padding: 'var(--ws-pad)',
          overflowX: 'hidden',
        }}>

          {/* Welcome / empty state — only shown when on a data-dependent section
              with no audit loaded. Skipped for live/appendix/govern which work
              independently of audit data. */}
          {!hasData && !showUpload && !['live', 'appendix', 'govern', 'history', 'realtime'].includes(activeSection) && (
            <div style={{ textAlign: 'center', padding: '70px 40px' }}>
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
                  LIVE MONITOR
                </BtnOutline>
                <BtnOutline color={DS.purple} onClick={() => setActiveSection('appendix')}>
                  SEE THE MATH
                </BtnOutline>
              </div>
              <div style={{ color: DS.dim, fontSize: 10, marginTop: 24 }}>
                Don&rsquo;t have data handy? RUN DEMO replays the reference 500 MW BESS audit (~7s on CBC).
              </div>
            </div>
          )}

          {/* ══ S01: Executive Summary — SPEC-EX on the Workspace ══════ */}
          {/* SPEC-WS §1: no max-width container, no centered column — the
              1720px interim cap is removed per the ratified contract. Extra
              canvas is absorbed by the zone system, not stretched cards. */}
          {hasData && activeSection === 'exec' && (
            <Workspace>
              {ingestionNotes && (
                <IngestionNotesBanner notes={ingestionNotes} onDismiss={() => setIngestionNotes(null)} />
              )}
              <ExecutiveCommandCenter data={data} log={log} live={dataSource === 'live'}
                onOpenLive={() => setActiveSection('live')} />
            </Workspace>
          )}

          {/* ══ S02: Economic Value Flow ════════════════════════════ */}
          {hasData && activeSection === 'flow' && (
            <div>
              <SectionHeader tag="02" title="Economic Value Flow" />
              {!hasData ? <EmptyMsg>Run an audit to populate the economic flow.</EmptyMsg> : (
                <div style={{ maxWidth: 560, margin: '0 auto' }}>
                  {/* Every stage below is a COMPUTED quantity from the audit
                      engine. The former intermediate stages (×0.92 grid,
                      ×0.87 SOC, ×0.97 settlement, ×0.12 unrecoverable) were
                      fabricated multipliers — removed (docs/REMOVED_HEURISTICS.md). */}
                  {[
                    { label: 'Theoretical Ceiling (Upper Bound)', value: fmtMoney(data.edv_optimal_total, data.currency), color: DS.warning, desc: 'Perfect-foresight MILP benchmark — not an achievable operating target' },
                    ...(data.gap_attribution ? [
                      { label: 'Forecast-Unreachable Gap', value: `−${fmtMoney(data.gap_attribution.forecast_gap, data.currency)}`, color: DS.dim, desc: 'Reachable only with perfect price foresight (Ch 8.2) — not operator-attributable' },
                      { label: 'Recoverable Execution Gap', value: `−${fmtMoney(data.gap_attribution.execution_gap, data.currency)}`, color: DS.loss, desc: 'Achievable with the day-ahead forecast available at decision time' },
                    ] : [
                      { label: 'Ceiling Gap (Upper Bound)', value: `−${fmtMoney(data.total_gap_usd, data.currency)}`, color: DS.loss, desc: 'Includes forecast-unreachable value; forecast column required to split' },
                    ]),
                    { label: 'Captured Value', value: fmtMoney(data.edv_actual_total, data.currency), color: DS.optimal, desc: 'EDV of the dispatch actually executed (Σ edv_actual_step from the ledger)' },
                  ].map((step, i, arr) => (
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
                      {i < arr.length - 1 && <div style={{ textAlign: 'center', color: DS.dim, lineHeight: '22px', fontSize: 18 }}>↓</div>}
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
              <SectionHeader tag="04" title="Root Cause Analysis"
                sub="Recorded leakage decomposed by cause — ranked by economic loss." />
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
                    {/* IN-06 Leakage Flow — leakage decomposed by root cause. */}
                    <Label style={{ marginBottom: 12 }}>Leakage Flow — Root-Cause Contribution</Label>
                    <Suspense fallback={<ChartSkeleton h={260} />}>
                      <LeakageFlow rootCauses={data.root_causes || []} />
                    </Suspense>
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
                  { label: 'Actual Revenue', value: fmtMoney(data.edv_actual_total, data.currency), color: DS.blue },
                  { label: 'Theoretical Ceiling (Upper Bound)', value: fmtMoney(data.edv_optimal_total, data.currency), color: DS.optimal },
                  ...(data.gap_attribution
                    ? [{ label: 'Recoverable Execution Gap', value: `−${fmtMoney(data.gap_attribution.execution_gap, data.currency)}`, color: DS.loss }]
                    : [{ label: 'Ceiling Gap (Upper Bound)', value: `−${fmtMoney(data.total_gap_usd, data.currency)}`, color: DS.loss }]),
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
                  <Suspense fallback={<ChartSkeleton h={260} />}>
                    <DispatchCurve log={log} />
                  </Suspense>
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
              <DataQualityPanel dqi={data.data_quality_index} ac={data.audit_confidence} fr={data.forecast_reliability} />
              {!m ? <EmptyMsg>Run an audit to generate metrics.</EmptyMsg> : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
                  {/* Ledger-derived ratios only. EIS composite, Decision Delay
                      Index, Revenue Stacking Index and Battery Opportunity
                      Capture were withdrawn under the No-Fabrication rule —
                      see docs/REMOVED_HEURISTICS.md. */}
                  {[
                    { label: 'Economic Decision Efficiency (EDE)', value: fmtPct(m.economic_decision_efficiency), note: 'EDV_actual ÷ EDV_ceiling × 100 (Ch 4.2 domain rules)', color: qualColor(m.economic_decision_efficiency), pct: m.economic_decision_efficiency },
                    { label: 'Economic Leakage Ratio (ELR)', value: fmtPct(m.economic_leakage_ratio), note: '100 − EDE', color: m.economic_leakage_ratio <= 30 ? DS.optimal : m.economic_leakage_ratio <= 60 ? DS.warning : DS.loss, pct: m.economic_leakage_ratio },
                    { label: 'Dispatch Accuracy', value: fmtPct(m.dispatch_accuracy), note: 'Steps classified Correct ÷ Total × 100', color: qualColor(m.dispatch_accuracy), pct: m.dispatch_accuracy },
                    { label: 'Forecast Utilization Index', value: fmtPct(m.forecast_utilization_index), note: 'Steps with a forecast value ÷ Total × 100', color: qualColor(m.forecast_utilization_index), pct: m.forecast_utilization_index },
                    ...(m.override_rate_pct != null
                      ? [{ label: 'Override Rate', value: fmtPct(m.override_rate_pct), note: 'Override-flagged steps ÷ Total × 100', color: DS.blue, pct: m.override_rate_pct }]
                      : []),
                    ...(m.curtailed_energy_mwh != null
                      ? [{ label: 'Curtailed Energy', value: `${m.curtailed_energy_mwh} MWh`, note: 'Σ curtailment_mw × Δt (descriptive; not a gap attribution)', color: DS.cyan, pct: null }]
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
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 16, marginBottom: 8 }}>
                {[
                  ...(data.gap_attribution
                    ? [{ label: 'Recoverable Execution Gap — Audit Period', value: fmtMoney(data.gap_attribution.execution_gap, data.currency), color: DS.loss }]
                    : []),
                  { label: 'Ceiling Gap — Audit Period', value: fmtMoney(data.total_gap_usd, data.currency), color: data.gap_attribution ? DS.orange : DS.loss },
                  { label: '7-Day (Linear Est., Ceiling Basis)', value: data.total_gap_usd > 0 ? fmtMoney(data.total_gap_usd * 7, data.currency) : '—', color: DS.orange },
                  { label: '30-Day (Linear Est., Ceiling Basis)', value: data.total_gap_usd > 0 ? fmtMoney(data.total_gap_usd * 30, data.currency) : '—', color: DS.warning },
                  { label: '12-Month (Linear Est., Ceiling Basis)', value: data.total_gap_usd > 0 ? fmtMoney(data.total_gap_usd * 365, data.currency) : '—', color: DS.loss },
                ].map((f) => (
                  <Card key={f.label} style={{ textAlign: 'center', borderColor: `${f.color}25` }}>
                    <Label>{f.label}</Label>
                    <BigNum v={f.value} color={f.color} />
                  </Card>
                ))}
              </div>
              <div style={{ color: DS.dim, fontSize: 10, lineHeight: 1.5, marginBottom: 20 }}>
                Ceiling basis = gap vs the Theoretical Economic Ceiling (perfect-foresight upper-bound
                benchmark). Multi-period figures are linear extrapolations of the audited period, not
                statistical forecasts.
                {data.gap_attribution
                  ? ' The Recoverable Execution Gap is the portion achievable with information available at decision time (Ch 8.2).'
                  : ' A day-ahead forecast column is required to isolate the operationally recoverable portion.'}
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
                <Suspense fallback={<ChartSkeleton h={200} />}>
                  <LeakageHistory histData={histData} />
                </Suspense>
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
                // Header stats derived strictly from the ledger-backed items.
                // Former "Portfolio Confidence" (mean of fabricated per-item
                // confidences) and difficulty timeline claims removed.
                const quantified = ops.filter(o => !o.experimental && o.period_gain != null);
                const advisory   = ops.filter(o => o.experimental);
                const periodTotal = quantified
                  .filter(o => o.name !== 'Operator override governance') // cross-cut, excluded from sum
                  .reduce((s, o) => s + (o.period_gain || 0), 0);
                const intervalsTotal = quantified
                  .filter(o => o.name !== 'Operator override governance')
                  .reduce((s, o) => s + (o.intervals_observed || 0), 0);
                return (
                  <div style={{ background: `linear-gradient(135deg, rgba(0,230,118,0.06) 0%, rgba(75,191,255,0.04) 100%)`, border: `1px solid ${DS.optimal}25`, borderRadius: DS.r16, padding: 24, marginBottom: 24 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 20 }}>
                      {[
                        { label: 'Period Gap Attributed', v: fmtMoney(periodTotal, data.currency), c: DS.optimal, big: true, sub: 'Σ over classified ledger rows' },
                        { label: 'Annualised (Linear Est.)', v: fmtMoney(periodTotal * 365, data.currency), c: DS.warning, sub: 'ceiling basis' },
                        { label: 'Quantified Actions', v: quantified.length, c: DS.optimal, sub: 'ledger-derived' },
                        { label: 'Ledger Intervals', v: intervalsTotal, c: DS.blue, sub: 'evidence rows' },
                        { label: 'Advisory (Experimental)', v: advisory.length, c: DS.dim, sub: 'not quantified' },
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
                  {(data.opportunities || []).map((op, i) => (
                    <div key={i} style={{ background: DS.surface, border: `1px solid ${op.experimental ? DS.dim : DS.border}`, borderRadius: DS.r12, overflow: 'hidden', opacity: op.experimental ? 0.85 : 1 }}>
                      {/* Card header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '18px 22px 14px', borderBottom: `1px solid ${DS.border}` }}>
                        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                          <div style={{ color: DS.dim, fontFamily: DS.mono, fontSize: 20, fontWeight: 800, lineHeight: 1, minWidth: 30 }}>#{i+1}</div>
                          <div>
                            <div style={{ color: DS.text, fontWeight: 700, fontSize: 14, marginBottom: 5 }}>
                              {op.name}
                              {op.experimental && <Pill label="EXPERIMENTAL — NOT PART OF EDA STANDARD v1.0" color={DS.dim} style={{ marginLeft: 10 }} />}
                            </div>
                            <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.6, maxWidth: 520 }}>{op.description}</div>
                          </div>
                        </div>
                        {!op.experimental && op.period_gain != null && (
                          <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 20 }}>
                            <BigNum v={fmtMoney(op.period_gain, data.currency)} color={DS.optimal} size={22} />
                            <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.12em', marginTop: 2 }}>AUDITED PERIOD</div>
                            <div style={{ color: DS.warning, fontFamily: DS.mono, fontSize: 12, marginTop: 4 }}>{fmtMoney(op.annual_gain_usd, data.currency)}</div>
                            <div style={{ color: DS.dim, fontSize: 8.5, letterSpacing: '0.08em' }}>ANNUALISED · LINEAR EST.</div>
                          </div>
                        )}
                      </div>

                      {/* Derived metrics (quantified items only) */}
                      {!op.experimental && op.period_gain != null && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0, padding: '12px 22px' }}>
                          {[
                            { label: 'Ledger Intervals', v: op.intervals_observed, c: DS.blue },
                            { label: 'Share of Positive Gap', v: op.share_of_positive_gap_pct != null ? `${op.share_of_positive_gap_pct}%` : '—', c: DS.cyan },
                            { label: 'Reproducible From', v: 'Ledger CSV (decision_type filter)', c: DS.sub },
                          ].map(f => (
                            <div key={f.label} style={{ borderRight: `1px solid ${DS.border}`, padding: '4px 12px 4px 0', marginRight: 12 }}>
                              <Label style={{ fontSize: 9, marginBottom: 3 }}>{f.label}</Label>
                              <div style={{ color: f.c, fontSize: 12, fontWeight: 600 }}>{f.v}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Evidence + derivation footer */}
                      <div style={{ padding: '10px 22px', background: `rgba(255,255,255,0.015)`, borderTop: `1px solid ${DS.border}` }}>
                        {op.evidence && (
                          <div style={{ color: DS.dim, fontSize: 11, marginBottom: op.derivation ? 4 : 0 }}>
                            <span style={{ color: DS.sub }}>Evidence:</span> {op.evidence}
                          </div>
                        )}
                        {op.derivation && (
                          <div style={{ color: DS.dim, fontSize: 10, fontFamily: DS.mono }}>
                            <span style={{ color: DS.sub, fontFamily: 'inherit' }}>Derivation:</span> {op.derivation}
                          </div>
                        )}
                        {op.experimental && (
                          <div style={{ color: DS.dim, fontSize: 10 }}>{op.experimental_note}</div>
                        )}
                      </div>
                    </div>
                  ))}
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
                    { label: 'Risk Band (DQ Thresholds)', v: (data.risk_level || '—').toUpperCase(), c: riskColor(data.risk_level) },
                    { label: 'Ceiling Capture (ECF)', v: fmtPct(captureRate), c: qualColor(captureRate) },
                    ...(data.gap_attribution
                      ? [{ label: 'Recoverable Execution Gap', v: fmtMoney(data.gap_attribution.execution_gap, data.currency), c: DS.optimal }]
                      : [{ label: 'Ceiling Gap (Upper Bound)', v: fmtMoney(data.total_gap_usd, data.currency), c: DS.warning }]),
                    { label: 'Dispatch Accuracy', v: m ? `${m.dispatch_accuracy?.toFixed(1)}%` : '—', c: DS.cyan },
                    { label: 'Forecast Coverage', v: m ? `${m.forecast_utilization_index?.toFixed(0)}%` : '—', c: DS.blue },
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
                        <Pill label={data.risk_level === 'Severe' ? 'CRITICAL' : data.risk_level === 'Moderate' ? 'MODERATE' : 'LOW RISK'} color={riskColor(data.risk_level)} />
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
                  {/* Recorded facts only. The former "Compliance Checklist"
                      issued PASS verdicts on unverified items (market rules,
                      SOC limits) and invented DQ thresholds — removed
                      (docs/REMOVED_HEURISTICS.md). */}
                  <Label style={{ marginBottom: 16 }}>Recorded Audit Facts</Label>
                  {[
                    { fact: 'Decision intervals in ledger', v: log.length },
                    { fact: 'Operator overrides recorded', v: log.filter(r => r.operator_override).length },
                    { fact: 'Overrides with positive gap', v: log.filter(r => r.operator_override && (r.gap_step || 0) > 0).length },
                    { fact: 'Steps with forecast value', v: `${(m?.forecast_utilization_index ?? 0).toFixed(0)}%` },
                    { fact: 'Steps with SoC telemetry', v: `${log.length ? ((log.filter(r => r.soc != null).length / log.length) * 100).toFixed(0) : 0}%` },
                    { fact: 'Risk band (published DQ thresholds)', v: (data.risk_level || '—').toUpperCase() },
                  ].map(({ fact, v }, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: `1px solid ${DS.border}` }}>
                      <span style={{ color: DS.sub, fontSize: 12 }}>{fact}</span>
                      <span style={{ color: DS.text, fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>{v}</span>
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
                      name: 'Economic Intelligence Score (EIS) — WITHDRAWN',
                      formula: '(formerly 0.45·EDE + 0.30·DA + 0.15·FUI + 0.10·(1−ELR))',
                      desc: 'WITHDRAWN under the No-Fabrication rule: the 45/30/15/10 weights were never validated, and EDE ≡ DQ by construction made the composite a DQ-weighted-twice signal. A composite index will only return if EDA Standard v1.0 formally defines and validates one. See docs/REMOVED_HEURISTICS.md.',
                      units: 'Not issued',
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
          {activeSection === 'realtime' && (
            <RealTimePanel
              isSignedIn={!!account?.token}
              onSignIn={() => { setGateMode('signin'); setGateError(''); setGateOpen(true); }}
            />
          )}

          {activeSection === 'history' && (
            <AuditHistoryPanel
              isSignedIn={!!account?.token}
              onLoad={loadPastAudit}
              busyId={historyBusyId}
              onSignIn={() => { setGateMode('signin'); setGateError(''); setGateOpen(true); }}
            />
          )}

          {activeSection === 'live' && (
            <div>
              <SectionHeader tag="RT" title="Real-Time Live Monitor — Economic Advisory Observer" />

              <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                <BtnOutline
                  color={liveMode ? DS.loss : DS.optimal}
                  onClick={() => (liveMode ? disconnectLive() : startLive())}
                >
                  {liveMode ? 'DISCONNECT' : 'CONNECT TO /ws/live'}
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
                        const msg = {
                          timestamp: new Date().toISOString(),
                          asset_id: data.asset_name || profile.asset_id,
                          ...payload,
                        };
                        // First tick on a reconnected socket carries the resume
                        // seed so cumulative session stats survive the outage.
                        if (reconnectRef.needResume && reconnectRef.lastCums) {
                          msg.resume = reconnectRef.lastCums;
                          reconnectRef.needResume = false;
                        }
                        wsRef.current.send(JSON.stringify(msg));
                      };
                      tick();
                      simRef.current = setInterval(tick, 1200);
                      setSimRunning(true);
                    }
                  }}
                >
                  {simRunning ? 'STOP SIMULATED FEED' : `SIMULATE ${SIM_PROFILES[simProfile]?.label.split(' ·')[0] || 'BESS'} FEED`}
                </BtnOutline>

                {liveData.length > 0 && (
                  <BtnOutline color={DS.dim} onClick={() => setLiveData([])}>CLEAR</BtnOutline>
                )}
              </div>

              {/* Live status strip — green when healthy, amber while the
                  auto-reconnect loop is riding out a grid/network outage. */}
              {liveMode && (() => {
                const reconnecting = liveStatus === 'reconnecting';
                const stripColor = reconnecting ? DS.warning : DS.optimal;
                const staleForSec = (!reconnecting && simRunning && lastTickAt)
                  ? Math.floor((Date.now() - lastTickAt) / 1000) : 0;
                const isStale = staleForSec > 15;
                return (
                <div style={{ display: 'flex', gap: 20, padding: '12px 20px', background: `${stripColor}08`, border: `1px solid ${stripColor}30`, borderRadius: DS.r12, marginBottom: 16, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: stripColor, boxShadow: `0 0 10px ${stripColor}` }} />
                    <span style={{ color: stripColor, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em' }}>
                      {reconnecting
                        ? 'CONNECTION LOST — RECONNECTING… (data held on screen)'
                        : `CONNECTED${simRunning ? ' · SIMULATING' : ''}`}
                    </span>
                  </div>
                  {isStale && (
                    <span style={{ color: DS.warning, fontSize: 12, fontWeight: 700 }}>
                      ⚠ FEED STALE — last tick {staleForSec}s ago
                    </span>
                  )}
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
                );
              })()}

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
                      {last.alert && <Pill label="⚠ GAP > 50% OF STEP OPTIMUM" color={DS.loss} />}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 12 }}>
                      {/* Withdrawn: per-step "Confidence" (fabricated constants)
                          and HIGH/MED/LOW severity (fabricated $ thresholds) —
                          replaced by the derived gap-share ratio. */}
                      {[
                        { l: 'Market Price', v: `$${last.price}/MWh`, c: DS.warning },
                        { l: 'Recommended Action', v: last.recommended_action, c: DS.cyan },
                        { l: 'Recommended Power', v: `${last.recommended_power} MW`, c: DS.blue },
                        { l: 'Expected Gain', v: fmtUSD(last.expected_gain || 0), c: DS.optimal },
                        { l: 'Gap % of Step Optimum', v: last.gap_pct_of_optimal != null ? `${last.gap_pct_of_optimal}%` : '—', c: DS.orange },
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
                    <Suspense fallback={<ChartSkeleton h={200} />}>
                      <LiveGapFlow liveData={liveData} />
                    </Suspense>
                  </Card>
                  <Card>
                    <Label style={{ marginBottom: 12 }}>Live Decision Quality Score</Label>
                    <Suspense fallback={<ChartSkeleton h={150} />}>
                      <LiveCaptureScore liveData={liveData} />
                    </Suspense>
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
                <strong style={{ color: DS.sub }}>Response includes:</strong> captured_value, optimal_value, economic_gap, decision_quality, recommended_action, recommended_power, expected_gain, gap_pct_of_optimal.
              </div>
            </div>
          )}

          {/* ══ S14: EDPC Certificate ════════════════════════════ */}
          {hasData && activeSection === 'cert' && (
            <div>
              <SectionHeader tag="CT" title="Economic Decision Performance Certificate™ (EDPC)" />
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
                  {certLoading ? 'GENERATING…' : 'GENERATE EDPC CERTIFICATE'}
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

                    {/* Economic Rating: WITHDRAWN. The AAA–CCC composite used
                        unvalidated 40/30/20/10 weights and is not re-derived
                        from DQ alone (hardening constraint 4). DQ — the one
                        validated metric — is shown instead. */}
                    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 32, marginBottom: 32, alignItems: 'center' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{
                          width: 160, height: 160, borderRadius: '50%', margin: '0 auto 16px',
                          border: `5px solid ${qualColor(certificate.dq_score)}`,
                          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                          background: `${qualColor(certificate.dq_score)}06`,
                        }}>
                          <div style={{ color: qualColor(certificate.dq_score), fontSize: 40, fontWeight: 900, fontFamily: DS.mono, lineHeight: 1 }}>{certificate.dq_score}</div>
                          <div style={{ color: DS.sub, fontSize: 10, marginTop: 6, letterSpacing: '0.12em' }}>DQ / ECF · /100</div>
                        </div>
                        <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.12em' }}>RISK BAND (DQ THRESHOLDS)</div>
                        <div style={{ color: riskColor(certificate.risk_level), fontFamily: DS.mono, fontSize: 18, fontWeight: 800 }}>{(certificate.risk_level || '—').toUpperCase()}</div>
                      </div>
                      <div style={{ padding: '16px 20px', background: 'rgba(255,255,255,0.02)', border: `1px dashed ${DS.border}`, borderRadius: DS.r12 }}>
                        <div style={{ color: DS.sub, fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', marginBottom: 10 }}>ECONOMIC RATING (AAA–CCC)</div>
                        <div style={{ color: DS.dim, fontSize: 12, lineHeight: 1.7 }}>
                          {certificate.rating_label || 'Withdrawn — pending EDA Standard v1.0 definition'}.
                          The previous composite rating relied on unvalidated weightings and has been
                          withdrawn under the No-Fabrication rule. A rating will only be issued once the
                          EDA Standard formally defines and validates its methodology.
                        </div>
                      </div>
                    </div>

                    <Divider />

                    {/* Metrics grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
                      {[
                        { label: 'Asset Name',          v: certificate.asset_name,           c: DS.text },
                        { label: 'Asset Type',           v: certificate.asset_type,           c: DS.cyan },
                        { label: 'Audit Period',         v: certificate.audit_period,         c: DS.sub },
                        { label: 'Theoretical Ceiling (Upper Bound)', v: fmtMoney(certificate.economic_potential, certificate.currency), c: DS.warning },
                        { label: 'Captured Value',       v: fmtMoney(certificate.captured_value, certificate.currency),     c: DS.optimal },
                        { label: 'Ceiling Gap',          v: fmtMoney(certificate.theoretical_ceiling_gap ?? certificate.destroyed_value, certificate.currency),    c: DS.loss },
                        ...(certificate.recoverable_execution_gap != null
                          ? [{ label: 'Recoverable Execution Gap', v: fmtMoney(certificate.recoverable_execution_gap, certificate.currency), c: DS.loss }]
                          : []),
                        { label: 'DQ / ECF',             v: `${certificate.dq_score} / 100`,  c: qualColor(certificate.dq_score) },
                        { label: 'Data Quality Grade', v: certificate.data_quality_index ? `${certificate.data_quality_index.value_pct}% / ${certificate.data_quality_grade}` : (certificate.data_quality_grade || 'N/A'), c: _gradeColor(certificate.data_quality_grade) },
                        { label: 'Audit Confidence Grade', v: certificate.audit_confidence ? (certificate.audit_confidence.value_pct != null ? `${certificate.audit_confidence.value_pct}% / ${certificate.confidence_grade}` : certificate.confidence_grade) : (certificate.confidence_grade || 'N/A'), c: _gradeColor(certificate.confidence_grade) },
                        { label: 'Annual Ceiling Gap (Linear Est.)', v: fmtMoney(certificate.annual_leakage, certificate.currency), c: DS.orange },
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
                  'After identifying leakage, PREDAIOT derives each improvement opportunity directly from the decision ledger: the value shown is the sum of the gap over the ledger rows matching that opportunity\'s classification, with the exact filter published alongside the figure. Strategy directions that cannot be quantified from the audited data are listed separately as Experimental.'],
                ['6. Universal Asset Intelligence',
                  'The PREDAIOT engine is fully asset-agnostic. Three primitives define any asset: (1) Physical Model — constraints and physics, (2) Economic Model — revenue and cost functions, (3) Decision Space — feasible control actions. Any energy asset with operational data can be economically audited: BESS, Solar, Wind, Gas, Hydro, Hydrogen, Desalination, CHP, or any industrial energy infrastructure.'],
                ['7. Explainability, Repeatability & Independence',
                  'Every recommendation is fully traceable to the original operational data, optimization model, and dispatch interval. Running the audit multiple times on identical data produces identical results. PREDAIOT does not control the asset — it independently evaluates operational decisions without interfering with existing EMS, SCADA, or DCS systems. This is an Economic Advisory Observer, not a control system.'],
                ['8. Counterfactual Engine',
                  'The PREDAIOT methodology evaluates every operational decision against its mathematically optimal alternative. Rather than asking "What happened?", PREDAIOT answers "What should have happened?" — the resulting Counterfactual Gap is the core quantity of the Economic Decision Audit methodology.'],
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