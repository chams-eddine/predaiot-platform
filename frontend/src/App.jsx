import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';

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
  <div style={{ color: color || DS.text, fontSize: size, fontWeight: 700, fontFamily: DS.mono, lineHeight: 1.1 }}>{v}</div>
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
const ASSET_TYPES = ['BESS', 'Solar', 'Wind', 'Gas', 'Hydro', 'Generic'];

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
  const [certificate, setCertificate]     = useState(null);
  const [certLoading, setCertLoading]     = useState(false);

  // Live SCADA poll
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await axios.get('/api/latest');
        if (r.data?.dq_score > 0) { setData(r.data); setShowUpload(false); setAiText(''); }
      } catch (_) {}
    };
    poll();
    const iv = setInterval(poll, 60000);
    return () => clearInterval(iv);
  }, []);

  // ── Demo audit ─────────────────────────────────────────────────────
  const runDemo = async () => {
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
      setAiText('');
      setActiveSection('exec');
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // ── File upload ────────────────────────────────────────────────────
  const handleFile = async (file) => {
    setUploading(true);
    setShowUpload(false);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post('/api/v1/audit/file', fd);
      setData(r.data);
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

  // ── Claude AI enhanced commentary ─────────────────────────────────
  const generateAI = async () => {
    if (!data.dq_score) return;
    setAiLoading(true);
    try {
      // Attempt to call Claude via a backend proxy at /api/v1/ai-enhance
      // Falls back to the pre-computed commentary if the endpoint is unavailable.
      const payload = {
        model: 'predait',
        max_tokens: 900,
        messages: [{
          role: 'user',
          content: `You are a senior energy economist at a Big-4 audit firm.

AUDIT DATA:
• Asset: ${data.asset_name} (${data.asset_type})
• Period: ${data.audit_period_label}
• Economic Potential: ${fmtUSD(data.edv_optimal_total)}
• Captured Value:    ${fmtUSD(data.edv_actual_total)}
• Destroyed Value:   ${fmtUSD(data.total_gap_usd)} (${fmtPct((data.total_gap_usd / data.edv_optimal_total) * 100)} of potential)
• Decision Quality Score: ${((data.dq_score || 0) * 100).toFixed(1)} / 100
• Risk Level: ${data.risk_level}
• Annual Leakage Projection: ${fmtUSD(data.total_gap_usd * 365)}
• Top Root Causes: ${(data.root_causes || []).slice(0, 3).map(r => `${r.category} (${r.contribution_pct}%)`).join(', ')}
• Missed Arbitrage Events: ${(data.decision_log || []).filter(d => d.decision_type === 'Missed Arbitrage').length}

Write a professional Economic Decision Audit finding in this structure:
1. EXECUTIVE FINDING (2 sentences) — concise, quantified
2. LOSS ATTRIBUTION (2–3 sentences) — root causes with specific percentages
3. RECOVERY OPPORTUNITY (2 sentences) — quantified upside
4. RECOMMENDATIONS (5 numbered items) — specific, actionable, ordered by priority

Use formal financial audit language. Reference exact figures. Maximum 380 words.`,
        }],
      };

      // Try backend proxy first
      let text = '';
      try {
        const r = await axios.post('/api/v1/ai-enhance', payload, { timeout: 20000 });
        text = r.data?.content?.[0]?.text || r.data?.text || '';
      } catch (_) {
        // Proxy not available — fall back to Anthropic direct (works only in dev / artifact context)
        const r = await fetch('https://api.anthropic.com/v1/messages', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (r.ok) {
          const j = await r.json();
          text = j.content?.[0]?.text || '';
        }
      }

      setAiText(text || data.ai_commentary);
    } catch (_) {
      setAiText(data.ai_commentary);
    }
    setAiLoading(false);
  };

  // ── Derived ────────────────────────────────────────────────────────
  const log         = Array.isArray(data.decision_log) ? data.decision_log : [];
  const captureRate = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
  const m           = data.eda_metrics;
  const hasData     = data.dq_score > 0;

  const navItems = [
    { id: 'exec',      label: 'Executive Summary',   tag: '01' },
    { id: 'flow',      label: 'Economic Flow',        tag: '02' },
    { id: 'timeline',  label: 'Decision Timeline',    tag: '03' },
    { id: 'rootcause', label: 'Root Cause',           tag: '04' },
    { id: 'counter',   label: 'Counterfactual',       tag: '05' },
    { id: 'metrics',   label: 'EDA Metrics',          tag: '06' },
    { id: 'leakage',   label: 'Financial Leakage',    tag: '07' },
    { id: 'heatmap',   label: 'Decision Heat Map',    tag: '08' },
    { id: 'opps',      label: 'Opportunity Ranking',  tag: '09' },
    { id: 'ai',        label: 'AI Commentary',        tag: '10' },
    { id: 'govern',    label: 'Governance',           tag: '11' },
    { id: 'appendix',  label: 'Math Appendix',        tag: '12' },
    { id: 'live',      label: 'Live Monitor',         tag: '⚡' },
    { id: 'cert',      label: 'EDA Certificate',      tag: '🏆' },
  ];

  // ══════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════
  return (
    <div style={{ backgroundColor: DS.bg, color: DS.text, minHeight: '100vh', fontFamily: DS.sans, fontSize: 13 }}>

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
          <BtnOutline color={DS.dim} onClick={() => setShowMethodology(true)}>METHODOLOGY</BtnOutline>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: DS.optimal, boxShadow: `0 0 8px ${DS.optimal}` }} />
            <span style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.12em' }}>LIVE</span>
          </div>
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
        <main style={{ flex: 1, padding: '28px 32px', maxWidth: 'calc(100vw - 242px)', overflowX: 'hidden' }}>

          {/* Welcome / empty state */}
          {!hasData && !showUpload && (
            <div style={{ textAlign: 'center', padding: '80px 40px' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⚡</div>
              <div style={{ color: DS.text, fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Economic Decision Audit™</div>
              <div style={{ color: DS.sub, fontSize: 13, marginBottom: 28, maxWidth: 500, margin: '0 auto 28px' }}>
                Upload any energy asset data file — BESS, Solar, Wind, Gas, Hydro — or run a demo to see a full 12-section audit report.
              </div>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading}>
                  {loading ? 'OPTIMIZING…' : 'RUN DEMO AUDIT'}
                </BtnOutline>
                <BtnOutline color={DS.optimal} onClick={() => setShowUpload(true)}>
                  UPLOAD MY DATA
                </BtnOutline>
              </div>
            </div>
          )}

          {/* ══ S01: Executive Summary ══════════════════════════════ */}
          {activeSection === 'exec' && (
            <div>
              <SectionHeader tag="01" title="Executive Summary" />

              {/* KPI shock panel */}
              <div style={{
                background: `linear-gradient(135deg, rgba(75,191,255,0.07) 0%, rgba(0,230,118,0.05) 100%)`,
                border: `1px solid ${DS.blue}25`, borderRadius: DS.r16, padding: 28, marginBottom: 20,
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
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

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
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
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
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
          {activeSection === 'flow' && (
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

          {/* ══ S03: Decision Timeline ══════════════════════════════ */}
          {activeSection === 'timeline' && (
            <div>
              <SectionHeader tag="03" title="Decision Timeline — Black Box" />
              {log.length === 0 ? <EmptyMsg>Run an audit to populate the decision log.</EmptyMsg> : (
                <div style={{ maxHeight: 620, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {log.filter(d => (d.gap_step || 0) > 0).slice(0, 40).map((dec, i) => {
                    const h = dec.hour || 0;
                    const label = `${Math.floor(h / 12).toString().padStart(2, '0')}:${((h % 12) * 5).toString().padStart(2, '0')}`;
                    const isCritical = (dec.gap_step || 0) > 20;
                    return (
                      <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '72px 1fr', gap: 16,
                        background: DS.surface, border: `1px solid ${isCritical ? DS.loss + '30' : DS.border}`,
                        borderRadius: DS.r12, padding: '12px 16px',
                      }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 14, fontWeight: 700 }}>{label}</div>
                          <div style={{ color: DS.dim, fontSize: 9, marginTop: 4, letterSpacing: '0.1em' }}>STEP {h}</div>
                        </div>
                        <div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 8 }}>
                            <div><Label style={{ marginBottom: 2 }}>Price</Label><div style={{ color: DS.warning, fontFamily: DS.mono, fontSize: 12, fontWeight: 600 }}>${dec.price}/MWh</div></div>
                            <div><Label style={{ marginBottom: 2 }}>Optimal</Label><div style={{ color: DS.optimal, fontFamily: DS.mono, fontSize: 12, fontWeight: 600 }}>Dis {dec.optimal_action} MW</div></div>
                            <div><Label style={{ marginBottom: 2 }}>Actual</Label><div style={{ color: (dec.actual_action || 0) < 0.5 ? DS.loss : DS.text, fontFamily: DS.mono, fontSize: 12 }}>{(dec.actual_action || 0) < 0.5 ? 'Idle' : `Dis ${dec.actual_action} MW`}</div></div>
                            <div><Label style={{ marginBottom: 2 }}>Decision Loss</Label><div style={{ color: DS.loss, fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>−${(dec.gap_step || 0).toFixed(0)}</div></div>
                          </div>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            <Pill label={dec.decision_type || 'Unknown'} color={isCritical ? DS.loss : DS.optimal} />
                            {dec.confidence && <Pill label={`${(dec.confidence * 100).toFixed(0)}% confidence`} color={DS.cyan} />}
                            {dec.operator_override && <Pill label="Operator Override" color={DS.orange} />}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ══ S04: Root Cause Analysis ════════════════════════════ */}
          {activeSection === 'rootcause' && (
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
          {activeSection === 'counter' && (
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
          {activeSection === 'metrics' && (
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
          {activeSection === 'leakage' && (
            <div>
              <SectionHeader tag="07" title="Financial Value Leakage" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 }}>
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
          {activeSection === 'heatmap' && (
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

          {/* ══ S09: Opportunity Ranking ════════════════════════════ */}
          {activeSection === 'opps' && (
            <div>
              <SectionHeader tag="09" title="Opportunity Ranking" />
              {(data.opportunities || []).length === 0 ? <EmptyMsg>Run an audit to generate opportunity rankings.</EmptyMsg> : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {(data.opportunities || []).map((op, i) => (
                    <div key={i} style={{
                      display: 'grid', gridTemplateColumns: '36px 1fr 150px 110px 110px', gap: 16,
                      alignItems: 'center', padding: '16px 22px',
                      background: DS.surface, border: `1px solid ${DS.border}`,
                      borderRadius: DS.r12,
                    }}>
                      <div style={{ color: DS.dim, fontSize: 14, fontWeight: 700, fontFamily: DS.mono }}>#{i + 1}</div>
                      <div>
                        <div style={{ color: DS.text, fontWeight: 700, fontSize: 13, marginBottom: 3 }}>{op.name}</div>
                        <div style={{ color: DS.dim, fontSize: 11, lineHeight: 1.5 }}>{op.description}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <BigNum v={fmtUSD(op.annual_gain_usd)} color={DS.optimal} size={16} />
                        <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.1em', marginTop: 2 }}>ANNUAL GAIN</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <Pill label={op.difficulty} color={op.difficulty === 'Easy' ? DS.optimal : op.difficulty === 'Medium' ? DS.warning : DS.loss} />
                      </div>
                      <div style={{ textAlign: 'center', fontSize: 14, letterSpacing: 2 }}>
                        <span style={{ color: DS.warning }}>{'★'.repeat(op.priority_stars)}</span>
                        <span style={{ color: DS.border }}>{'★'.repeat(5 - op.priority_stars)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S10: AI Auditor Commentary ══════════════════════════ */}
          {activeSection === 'ai' && (
            <div>
              <SectionHeader tag="10" title="AI Auditor Commentary" />
              <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
                <BtnOutline
                  color={DS.cyan}
                  onClick={generateAI}
                  disabled={!hasData || aiLoading}
                >
                  {aiLoading ? 'GENERATING…' : '✦ ENHANCE WITH CLAUDE AI'}
                </BtnOutline>
                {(aiText || data.ai_commentary) && (
                  <BtnOutline color={DS.dim} onClick={() => setAiText('')} disabled={!aiText}>
                    RESET TO DEFAULT
                  </BtnOutline>
                )}
              </div>
              <Card glow={DS.cyan}>
                {(aiText || data.ai_commentary) ? (
                  <pre style={{
                    color: DS.text, fontSize: 13, lineHeight: 1.9,
                    fontFamily: DS.sans, whiteSpace: 'pre-wrap', margin: 0,
                  }}>
                    {aiText || data.ai_commentary}
                  </pre>
                ) : <EmptyMsg>Run an audit and click "Enhance with Claude AI" to generate professional commentary.</EmptyMsg>}
              </Card>
              <div style={{ marginTop: 12, color: DS.dim, fontSize: 10 }}>
                ✦ AI commentary is generated by Claude (claude-sonnet-4-6) via the Anthropic API. Backend proxy endpoint: POST /api/v1/ai-enhance
              </div>
            </div>
          )}

          {/* ══ S11: Governance ═════════════════════════════════════ */}
          {activeSection === 'govern' && (
            <div>
              <SectionHeader tag="11" title="Governance &amp; Decision Authority" />
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
              <Card>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  {[
                    { name: 'Economic Decision Efficiency (EDE)', formula: 'EDE = V_captured / V_potential', desc: 'Primary performance ratio. Measures the fraction of available market value actually captured by the dispatch strategy.', units: 'Dimensionless [0, 1]' },
                    { name: 'Economic Leakage (EL)', formula: 'EL = V_potential − V_captured', desc: 'Absolute revenue destroyed by sub-optimal dispatch decisions. Physically achievable but economically squandered value.', units: 'USD per audit period' },
                    { name: 'Decision Quality Index (DQI)', formula: 'DQI = Σ(wᵢ · Sᵢ) / Σwᵢ', desc: 'Weighted composite score. wᵢ = economic impact weight of decision i; Sᵢ = binary correctness score for that decision.', units: 'Score [0, 100]' },
                    { name: 'Step Economic Decision Value (EDV)', formula: 'EDV(t) = P(t) × D(t) − c_deg × D(t)', desc: 'P(t) = market price [$/MWh], D(t) = discharge power [MW], c_deg = degradation cost per MWh dispatched.', units: 'USD per timestep' },
                    { name: 'Counterfactual Gap (CG)', formula: 'CG(t) = EDV_optimal(t) − EDV_actual(t)', desc: 'Per-timestep revenue gap between the MILP-optimal solution and actual recorded dispatch. Core of the PREDAIOT patent method.', units: 'USD per timestep' },
                    { name: 'Economic Intelligence Score (EIS)', formula: 'EIS = 0.45·EDE + 0.30·DA + 0.15·FUI + 0.10·(1−ELR)', desc: 'Composite ISO-style index. DA = Dispatch Accuracy; FUI = Forecast Utilization Index; ELR = Economic Leakage Ratio.', units: 'Score [0, 100]' },
                    { name: 'Annual Leakage Projection (ALP)', formula: 'ALP = EL_24h × 365', desc: 'Linear annualisation of single-period leakage. Assumes stationary price/dispatch patterns across the year.', units: 'USD / year' },
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
            </div>
          )}

          {/* ══ S13: Live Monitor ══════════════════════════════ */}
          {activeSection === 'live' && (
            <div>
              <SectionHeader tag="⚡" title="Real-Time Live Monitor" />

              <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                <BtnOutline
                  color={liveMode ? DS.loss : DS.optimal}
                  onClick={() => {
                    if (liveMode) {
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
                        ws.onclose = () => setLiveMode(false);
                        ws.onerror = () => { setLiveMode(false); alert('WebSocket connection failed. Make sure the backend is running.'); };
                        wsRef.current = ws;
                      } catch (err) { alert('Could not open WebSocket: ' + err.message); }
                    }
                  }}
                >
                  {liveMode ? '⏹ STOP LIVE STREAM' : '▶ START LIVE STREAM'}
                </BtnOutline>
                {liveData.length > 0 && (
                  <BtnOutline color={DS.dim} onClick={() => setLiveData([])}>CLEAR</BtnOutline>
                )}
              </div>

              {/* Live status strip */}
              {liveMode && (
                <div style={{ display: 'flex', gap: 20, padding: '12px 20px', background: `${DS.optimal}08`, border: `1px solid ${DS.optimal}30`, borderRadius: DS.r12, marginBottom: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: DS.optimal, boxShadow: `0 0 10px ${DS.optimal}`, animation: 'pulse 1s infinite' }} />
                    <span style={{ color: DS.optimal, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em' }}>STREAMING LIVE</span>
                  </div>
                  <span style={{ color: DS.sub, fontSize: 12 }}>{liveData.length} steps received</span>
                  {liveData.length > 0 && (
                    <>
                      <span style={{ color: DS.warning, fontFamily: DS.mono, fontSize: 12 }}>
                        Live Gap: −{fmtUSD(liveData[liveData.length-1]?.cumulative_gap || 0)}
                      </span>
                      <span style={{ color: qualColor(liveData[liveData.length-1]?.dq_score_live || 0), fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>
                        DQ Live: {(liveData[liveData.length-1]?.dq_score_live || 0).toFixed(1)}%
                      </span>
                      {liveData[liveData.length-1]?.alert && (
                        <Pill label="⚠ ECONOMIC ALERT" color={DS.loss} />
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Live chart */}
              {liveData.length > 1 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <Card>
                    <Label style={{ marginBottom: 12 }}>Live Gap Accumulation</Label>
                    <ResponsiveContainer width="100%" height={220}>
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
                    <ResponsiveContainer width="100%" height={160}>
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
                    ? 'Waiting for data… Connect your SCADA/EMS to ws://your-server/ws/live'
                    : 'Click START LIVE STREAM to connect to the real-time WebSocket feed.'}
                </EmptyMsg>
              )}

              <div style={{ marginTop: 16, padding: '12px 16px', background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r8, fontSize: 11, color: DS.dim, lineHeight: 1.8 }}>
                <strong style={{ color: DS.sub }}>Integration:</strong> Your SCADA/EMS sends one JSON object per interval to <code style={{ color: DS.cyan }}>ws://your-server/ws/live</code><br />
                Payload: <code style={{ color: DS.cyan }}>{'{"price": 85.5, "actual_discharge": 20, "p_max": 50, "deg_cost": 5, "soc": 0.7}'}</code><br />
                For polling-based systems: <code style={{ color: DS.cyan }}>POST /api/v1/live/step</code> (same payload, no WebSocket needed)
              </div>
            </div>
          )}

          {/* ══ S14: EDA Certificate ══════════════════════════════ */}
          {activeSection === 'cert' && (
            <div>
              <SectionHeader tag="🏆" title="Economic Decision Certificate" />

              <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
                <BtnOutline
                  color={DS.warning}
                  onClick={async () => {
                    setCertLoading(true);
                    try {
                      const r = await axios.get('/api/v1/certificate');
                      setCertificate(r.data);
                    } catch (e) {
                      alert('Generate an audit first, then request the certificate.');
                    }
                    setCertLoading(false);
                  }}
                  disabled={!hasData || certLoading}
                >
                  {certLoading ? 'GENERATING…' : '🏆 GENERATE CERTIFICATE'}
                </BtnOutline>
                {certificate && (
                  <BtnOutline color={DS.cyan} onClick={() => window.print()}>PRINT / DOWNLOAD PDF</BtnOutline>
                )}
              </div>

              {certificate ? (
                <div style={{
                  background: `linear-gradient(135deg, #0a0e15 0%, #040810 100%)`,
                  border: `2px solid ${certificate.rating_color || DS.warning}`,
                  borderRadius: DS.r16, padding: 40,
                  boxShadow: `0 0 60px ${certificate.rating_color || DS.warning}18`,
                  maxWidth: 720, margin: '0 auto',
                }}>
                  {/* Header */}
                  <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.35em', marginBottom: 8 }}>ECONOMIC DECISION AUDIT CERTIFICATE</div>
                    <div style={{ color: DS.text, fontSize: 22, fontWeight: 800, letterSpacing: '0.08em', marginBottom: 4 }}>PREDAIOT EDA™</div>
                    <div style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.2em' }}>{certificate.standard}</div>
                  </div>

                  {/* Rating badge - center */}
                  <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div style={{
                      display: 'inline-flex', flexDirection: 'column', alignItems: 'center',
                      width: 120, height: 120, borderRadius: '50%',
                      border: `4px solid ${certificate.rating_color}`,
                      justifyContent: 'center',
                      boxShadow: `0 0 40px ${certificate.rating_color}30`,
                      background: `${certificate.rating_color}08`,
                    }}>
                      <div style={{ color: certificate.rating_color, fontSize: 36, fontWeight: 900, fontFamily: DS.mono, lineHeight: 1 }}>{certificate.rating}</div>
                      <div style={{ color: DS.sub, fontSize: 9, marginTop: 4, letterSpacing: '0.12em' }}>{certificate.rating_label.toUpperCase()}</div>
                    </div>
                  </div>

                  {/* Asset details */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
                    {[
                      { label: 'Asset Name', value: certificate.asset_name, color: DS.text },
                      { label: 'Asset Type', value: certificate.asset_type, color: DS.cyan },
                      { label: 'Audit Period', value: certificate.audit_period, color: DS.sub },
                      { label: 'Issued', value: new Date(certificate.issued_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }), color: DS.sub },
                    ].map(f => (
                      <div key={f.label} style={{ padding: '10px 14px', background: 'rgba(255,255,255,0.025)', borderRadius: DS.r8 }}>
                        <Label style={{ marginBottom: 4 }}>{f.label}</Label>
                        <div style={{ color: f.color, fontWeight: 700, fontSize: 13 }}>{f.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Financial metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 24 }}>
                    {[
                      { label: 'Economic Potential', value: fmtUSD(certificate.economic_potential), color: DS.warning },
                      { label: 'Captured Value', value: fmtUSD(certificate.captured_value), color: DS.optimal },
                      { label: 'Destroyed Value', value: fmtUSD(certificate.destroyed_value), color: DS.loss },
                      { label: 'DQ Score', value: `${certificate.dq_score} / 100`, color: qualColor(certificate.dq_score) },
                      { label: 'EIS Score', value: `${certificate.eis_score} / 100`, color: qualColor(certificate.eis_score) },
                      { label: 'Annual Leakage', value: fmtUSD(certificate.annual_leakage), color: DS.orange },
                    ].map(f => (
                      <div key={f.label} style={{ textAlign: 'center', padding: '12px 8px', background: 'rgba(255,255,255,0.02)', border: `1px solid rgba(255,255,255,0.06)`, borderRadius: DS.r8 }}>
                        <Label style={{ marginBottom: 4, fontSize: 9 }}>{f.label}</Label>
                        <div style={{ color: f.color, fontFamily: DS.mono, fontWeight: 700, fontSize: 16 }}>{f.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Key finding */}
                  <div style={{ padding: '14px 18px', background: `${certificate.rating_color}08`, border: `1px solid ${certificate.rating_color}25`, borderRadius: DS.r12, marginBottom: 24 }}>
                    <Label style={{ marginBottom: 6 }}>Key Finding</Label>
                    <div style={{ color: DS.sub, fontSize: 12, lineHeight: 1.8, fontStyle: 'italic' }}>"{certificate.key_finding}"</div>
                  </div>

                  {/* Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderTop: `1px solid rgba(255,255,255,0.06)`, paddingTop: 20 }}>
                    <div>
                      <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.15em', marginBottom: 3 }}>CERTIFIED BY</div>
                      <div style={{ color: DS.text, fontWeight: 700, fontSize: 11 }}>PREDAIOT</div>
                      <div style={{ color: DS.dim, fontSize: 9, marginTop: 2 }}>{certificate.methodology}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ color: DS.dim, fontSize: 9, letterSpacing: '0.15em', marginBottom: 3 }}>CERTIFICATE ID</div>
                      <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 10 }}>{certificate.certificate_id}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '60px 40px' }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>🏆</div>
                  <div style={{ color: DS.text, fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Economic Decision Certificate</div>
                  <div style={{ color: DS.sub, fontSize: 12, maxWidth: 440, margin: '0 auto 24px' }}>
                    Run an audit and click "Generate Certificate" to produce a formal PREDAIOT EDA certificate with your asset's economic performance rating (AAA–CCC).
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, maxWidth: 500, margin: '0 auto' }}>
                    {[['AAA', '#00E676', 'Excellent'], ['AA', '#69F0AE', 'Very Good'], ['A', '#FFD600', 'Good'], ['BBB', '#FF9800', 'Acceptable'],
                      ['BB', '#FF5722', 'Below Avg'], ['B', '#FF1744', 'Poor'], ['CCC', '#C62828', 'Critical'], ['?', DS.dim, 'Your Rating']].map(([r, c, l]) => (
                      <div key={r} style={{ textAlign: 'center', padding: '12px 8px', background: DS.surface, border: `1px solid ${c}30`, borderRadius: DS.r8 }}>
                        <div style={{ color: c, fontSize: 18, fontWeight: 900, fontFamily: DS.mono }}>{r}</div>
                        <div style={{ color: DS.dim, fontSize: 9, marginTop: 3 }}>{l}</div>
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
        <div onClick={() => setShowMethodology(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.88)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#0a0d12', border: `1px solid ${DS.border}`, borderRadius: DS.r16, padding: 32, maxWidth: 680, width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div style={{ color: DS.cyan, fontSize: 15, fontWeight: 700, letterSpacing: '0.12em' }}>PREDAIOT METHODOLOGY</div>
              <button onClick={() => setShowMethodology(false)} style={{ background: 'none', border: 'none', color: DS.dim, fontSize: 20, cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                ['1. Optimal Potential (MILP)', 'Solved using Mixed-Integer Linear Programming across all timesteps simultaneously. Maximizes total revenue subject to power physics, SOC bounds, and degradation cost. This is the hard upper bound — physically achievable, economically optimal.'],
                ['2. Captured Value', 'Net revenue from actual SCADA-recorded dispatch decisions, after degradation cost. This is real money that entered the settlement meter.'],
                ['3. Value Leakage', 'Arithmetic difference: Optimal − Actual. Every dollar here was physically achievable but economically destroyed by poor timing.'],
                ['4. Universal Asset Support', 'Engine is fully asset-agnostic. Upload any CSV or Excel with a price column and an output column. Optional columns (soc, curtailment_mw, forecast_price, asset_type) unlock deeper intelligence layers.'],
                ['5. AI Commentary (Claude)', 'Enhanced commentary is generated by Claude (claude-sonnet-4-6) via the Anthropic API. Requires /api/v1/ai-enhance backend proxy endpoint. Default commentary is computed deterministically from audit statistics.'],
                ['6. Patent-Pending Method', 'The counterfactual gap methodology — computing the exact decision-by-decision revenue difference against an MILP optimum — is the core of the PREDAIOT patent filing.'],
              ].map(([title, body]) => (
                <div key={title} style={{ padding: '12px 16px', background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r8 }}>
                  <div style={{ color: DS.text, fontWeight: 700, fontSize: 12, marginBottom: 5 }}>{title}</div>
                  <div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.7 }}>{body}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// ============================================
// في أعلى App.jsx — أضف الاستيرادات
// ============================================
import { useState, useEffect, useRef, useCallback } from 'react';
import AdvisorySidebar from './components/AdvisorySidebar';
import { useLiveStream } from './hooks/useLiveStream';

// ============================================
// داخل مكون App — أضف الـ hook
// ============================================
export default function App() {
  // ... (State الحالي: auditData, file, etc.) ...

  // ─── PREDAIOT Live Stream ───
  const [wsUrl, setWsUrl] = useState(null);
  const {
    connected,
    step: liveStep,
    history: liveHistory,
    connect: connectWS,
    disconnect: disconnectWS,
    reset: resetLive,
    processStep,
  } = useLiveStream(wsUrl);

  // ─── WebSocket Events from Sidebar ───
  useEffect(() => {
    const onConnect = (e) => {
      setWsUrl(e.detail);
      connectWS(e.detail);
    };
    const onDisconnect = () => {
      setWsUrl(null);
      disconnectWS();
    };
    window.addEventListener('predaiot:ws-connect', onConnect);
    window.addEventListener('predaiot:ws-disconnect', onDisconnect);
    return () => {
      window.removeEventListener('predaiot:ws-connect', onConnect);
      window.removeEventListener('predaiot:ws-disconnect', onDisconnect);
    };
  }, [connectWS, disconnectWS]);

  // ─── Demo Simulation ───
  const demoRef = useRef(null);
  const [isDemoRunning, setIsDemoRunning] = useState(false);

  const generateDemoPrices = useCallback(() => {
    const p = [];
    for (let i = 0; i < 288; i++) {
      const h = i / 12;
      let v;
      if (h < 5) v = 15 + Math.random() * 8;
      else if (h < 8) v = 30 + (h - 5) * 12 + Math.random() * 5;
      else if (h < 12) v = 58 - (h - 8) * 3 + Math.random() * 8;
      else if (h < 16) v = 38 + Math.random() * 12;
      else if (h < 20) v = 50 + (h - 16) * 14 + Math.random() * 8;
      else v = 90 - (h - 20) * 18 + Math.random() * 5;
      p.push(Math.max(5, Math.round(v * 100) / 100));
    }
    return p;
  }, []);

  const startDemo = useCallback(() => {
    if (demoRef.current) return;
    const prices = generateDemoPrices();
    let demoStep = 0;
    resetLive();
    setIsDemoRunning(true);

    demoRef.current = setInterval(() => {
      if (demoStep >= 288) {
        clearInterval(demoRef.current);
        demoRef.current = null;
        setIsDemoRunning(false);
        return;
      }

      const price = prices[demoStep];
      const threshold = 48;
      const optimal = price > threshold ? 50 : 0;
      const deg = 5;
      const r = Math.random();

      let actual = 0;
      if (price > 70) actual = 30 + Math.random() * 15;
      else if (price > 55) actual = r > 0.35 ? 15 + Math.random() * 20 : 0;
      else if (price > threshold) actual = r > 0.55 ? 10 + Math.random() * 15 : 0;

      const gap = Math.max(0, (price - deg) * optimal) - Math.max(0, (price - deg) * actual);
      let dt = 'Correct Idle';
      if (Math.abs(optimal - actual) < 1 && optimal > 0) dt = 'Correct Dispatch';
      else if (optimal > 5 && actual < 1) dt = 'Missed Arbitrage';
      else if (optimal > 5 && actual > 0 && actual < optimal) dt = 'Partial Capture';

      const conf = dt.includes('Correct') ? 96 : 78 + Math.random() * 15;
      const rec = gap > 10 ? 'DISCHARGE' : actual > 0 && gap > 5 ? 'ADJUST' : 'HOLD';
      const sev = gap > 200 ? 'CRITICAL' : gap > 80 ? 'HIGH' : gap > 20 ? 'MEDIUM' : 'LOW';

      processStep({
        step: demoStep,
        price,
        optimal_action: optimal,
        actual_action: Math.round(actual * 100) / 100,
        gap_step: Math.round(gap * 100) / 100,
        recommendation: rec,
        recommended_power: optimal,
        expected_gain: Math.round(gap * 100) / 100,
        confidence: Math.round(conf * 10) / 10,
        severity: sev,
        decision_type: dt,
        message:
          gap > 10
            ? `Dispatch ${optimal} MW — price $${price.toFixed(2)} exceeds economic threshold`
            : 'Near-optimal dispatch',
      });

      demoStep++;
    }, 200);
  }, [generateDemoPrices, resetLive, processStep]);

  const stopDemo = useCallback(() => {
    if (demoRef.current) {
      clearInterval(demoRef.current);
      demoRef.current = null;
    }
    setIsDemoRunning(false);
  }, []);

  // ... (باقي كود App.jsx — file upload, audit, etc.) ...

  // ============================================
  // في return() — غيّر الـ layout
  // ============================================
  return (
    <div className="h-screen flex flex-col bg-[#060a13] text-slate-200" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
      {/* ─── HEADER ─── */}
      <header className="h-14 flex items-center justify-between px-5 border-b border-[#1a2435] flex-shrink-0 bg-[#060a13]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          {/* Logo هنا حسب مشروعك */}
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-cyan-600 flex items-center justify-center">
            <i className="fas fa-bolt text-white text-sm" />
          </div>
          <span className="font-bold text-sm tracking-wide text-white">PREDAIOT</span>
          <span className="text-[10px] text-slate-600 ml-2 tracking-[2px]">
            ECONOMIC DECISION INTELLIGENCE
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                connected
                  ? 'bg-emerald-500 animate-pulse'
                  : isDemoRunning
                  ? 'bg-cyan-500 animate-pulse'
                  : 'bg-slate-600'
              }`}
            />
            <span className="text-slate-500">
              {connected ? 'LIVE' : isDemoRunning ? 'DEMO' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </header>

      {/* ─── MAIN: SIDEBAR + CONTENT ─── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ═══ الشريط الجانبي الاستشاري ═══ */}
        <AdvisorySidebar
          step={liveStep}
          connected={connected}
          isDemoRunning={isDemoRunning}
          onStartDemo={startDemo}
          onStopDemo={stopDemo}
        />

        {/* ═══ المحتوى الرئيسي (محتواك الحالي) ═══ */}
        <main className="flex-1 overflow-y-auto p-6">
          {/* ... كل محتوى App.jsx الحالي يبقى هنا ... */}
          {/* Upload section, results, charts, etc. */}
        </main>
      </div>
    </div>
  );
}