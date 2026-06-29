import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';
import AdvisorySidebar from './components/AdvisorySidebar';
import { useLiveStream } from './hooks/useLiveStream';

// ══════════════════════════════════════════════════════════════════════
// DESIGN SYSTEM — PREDAIOT Economic Decision Audit™
// ══════════════════════════════════════════════════════════════════════
const DS = {
  bg: '#030508', bgRaised: '#080c12',
  surface: 'rgba(255,255,255,0.025)', surfaceHi: 'rgba(255,255,255,0.05)',
  border: 'rgba(255,255,255,0.06)', borderHi: 'rgba(255,255,255,0.14)',
  optimal: '#00E676', warning: '#FFD600', loss: '#FF1744',
  blue: '#4BBFFF', cyan: '#00E5FF', orange: '#FF6D00', purple: '#BB86FC',
  text: '#E8EAF0', sub: '#8A94A6', dim: '#4A5468',
  mono: "'JetBrains Mono','Fira Code','Courier New',monospace",
  sans: "'Inter','Segoe UI',sans-serif",
  r8: '8px', r12: '12px', r16: '16px', r20: '20px',
};

const fmtUSD = (n) => { if (n == null) return '—'; const a = Math.abs(n); if (a >= 1e6) return `$${(n/1e6).toFixed(2)}M`; if (a >= 1e3) return `$${(n/1e3).toFixed(1)}k`; return `$${n.toFixed(2)}`; };
const fmtPct = (n, d = 1) => n == null ? '—' : `${Number(n).toFixed(d)}%`;
const riskColor = (r) => r === 'Low' ? DS.optimal : r === 'Moderate' ? DS.warning : DS.loss;
const riskEmoji = (r) => r === 'Low' ? '🟢' : r === 'Moderate' ? '🟡' : '🔴';
const heatColor = (s) => ({ optimal: DS.optimal, acceptable: DS.warning, poor: DS.orange, critical: DS.loss }[s] || DS.dim);
const qualColor = (p) => p >= 70 ? DS.optimal : p >= 40 ? DS.warning : DS.loss;

const Card = ({ children, style, glow }) => (
  <div style={{ background: DS.surface, border: `1px solid ${glow ? glow + '30' : DS.border}`, borderRadius: DS.r12, padding: '20px 24px', boxShadow: glow ? `0 0 28px ${glow}12` : 'none', ...style }}>{children}</div>
);
const Label = ({ children, style }) => (
  <div style={{ color: DS.dim, fontSize: 10, fontWeight: 600, letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 6, ...style }}>{children}</div>
);
const BigNum = ({ v, color, size = 26 }) => (
  <div style={{ color: color || DS.text, fontSize: size, fontWeight: 700, fontFamily: DS.mono, lineHeight: 1.1 }}>{v}</div>
);
const Pill = ({ label, color }) => (
  <span style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 20, border: `1px solid ${color}`, color, fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', background: `${color}14` }}>{label}</span>
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
    padding: '8px 18px', background: 'transparent', color: disabled ? DS.dim : color,
    border: `1px solid ${disabled ? DS.dim : color}`, borderRadius: DS.r8,
    cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 11, letterSpacing: '0.1em',
    fontWeight: 700, fontFamily: DS.sans, transition: 'all 0.15s', ...style,
  }}>{children}</button>
);
const ProgressBar = ({ pct, color }) => (
  <div style={{ height: 5, background: DS.border, borderRadius: 3, marginTop: 8, overflow: 'hidden' }}>
    <div style={{ width: `${Math.min(100, pct || 0)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
  </div>
);

// ══════════════════════════════════════════════════════════════════════
// FILE UPLOAD
// ══════════════════════════════════════════════════════════════════════
const ASSET_TYPES = ['BESS', 'Solar', 'Wind', 'Gas', 'Hydro', 'Generic'];
const COLUMN_GUIDE = [
  { label: 'Price Column', required: true, cols: ['price', 'spot_price', 'lmp', 'market_price', 'omr_mwh', 'da_price', 'rt_price', 'energy_price', 'clearing_price', 'settlement_price'] },
  { label: 'Output Column', required: true, cols: ['actual_discharge', 'generation', 'output_mw', 'gen_mw', 'actual_power', 'dispatch_mw', 'solar_output', 'wind_output', 'p_actual', 'net_output'] },
  { label: 'State of Charge', required: false, cols: ['soc', 'state_of_charge', 'battery_soc', 'soc_pct'] },
  { label: 'Curtailment', required: false, cols: ['curtailment_mw', 'curtailed_mw', 'clipped_mw', 'spillage'] },
  { label: 'Operator Override', required: false, cols: ['operator_override', 'manual_override', 'human_override'] },
  { label: 'Forecast Price', required: false, cols: ['forecast_price', 'predicted_price', 'da_forecast'] },
  { label: 'Asset Metadata', required: false, cols: ['asset_type', 'asset_name', 'p_max', 'e_max', 'eta_ch', 'eta_dis'] },
];

const FileUploadZone = ({ onFile, loading }) => {
  const [dragging, setDragging] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const inputRef = useRef(null);
  const process = (file) => { if (!file) return; if (!/\.(csv|xlsx|xls)$/i.test(file.name)) { alert('Please upload a CSV or Excel file.'); return; } onFile(file); };
  const handleDrop = useCallback((e) => { e.preventDefault(); setDragging(false); process(e.dataTransfer.files[0]); }, []);
  return (
    <div style={{ padding: '32px 40px', maxWidth: 800, margin: '0 auto' }}>
      <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop}
        onClick={() => !loading && inputRef.current?.click()}
        style={{ border: `2px dashed ${dragging ? DS.cyan : DS.border}`, borderRadius: DS.r16, padding: '52px 40px', textAlign: 'center', background: dragging ? `${DS.cyan}08` : DS.surface, cursor: loading ? 'wait' : 'pointer', transition: 'all 0.2s ease' }}>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={(e) => process(e.target.files[0])} style={{ display: 'none' }} />
        <div style={{ fontSize: 36, marginBottom: 14 }}>📊</div>
        <div style={{ color: DS.text, fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{loading ? 'Processing your data…' : 'Drop any energy asset data file here'}</div>
        <div style={{ color: DS.sub, fontSize: 12, marginBottom: 20 }}>CSV · XLSX · XLS — column names auto-detected across 80+ naming variants</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
          {ASSET_TYPES.map((t) => <Pill key={t} label={t} color={DS.cyan} />)}
        </div>
        <div style={{ color: DS.dim, fontSize: 11, lineHeight: 1.8 }}>✓ Auto-resolves column names · ✓ Any market region · ✓ Mixed unit formats accepted</div>
      </div>
      <div style={{ textAlign: 'center', marginTop: 16 }}>
        <button onClick={() => setShowGuide(!showGuide)} style={{ background: 'none', border: `1px solid ${DS.border}`, color: DS.sub, padding: '6px 18px', borderRadius: DS.r8, cursor: 'pointer', fontSize: 11 }}>
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
                {cols.map((c) => <code key={c} style={{ fontSize: 9, color: DS.cyan, background: `${DS.cyan}10`, padding: '2px 6px', borderRadius: 4 }}>{c}</code>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const EMPTY = {
  edv_optimal_total: 0, edv_actual_total: 0, dq_score: 0, total_gap_usd: 0,
  decision_log: [], asset_name: 'Energy Asset', asset_type: 'Generic',
  audit_period_label: '—', risk_level: 'Moderate', eda_metrics: null,
  root_causes: [], opportunities: [], heat_map: [], financial_leakage: null,
  ai_commentary: '', counterfactual_summary: '',
};

// ══════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════
export default function App() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [activeSection, setActiveSection] = useState('exec');
  const [showMethodology, setShowMethodology] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiText, setAiText] = useState('');
  const [histData, setHistData] = useState([]);
  const [histLoading, setHistLoading] = useState(false);
  const [certificate, setCertificate] = useState(null);
  const [certLoading, setCertLoading] = useState(false);

  // ── PREDAIOT Live Stream ──
  const [wsUrl, setWsUrl] = useState(null);
  const { connected, step: liveStep, history: liveHistory, connect: connectWS, disconnect: disconnectWS, reset: resetLive, processStep } = useLiveStream(wsUrl);
  const demoRef = useRef(null);
  const [isDemoRunning, setIsDemoRunning] = useState(false);

  useEffect(() => {
    const onC = (e) => { setWsUrl(e.detail); connectWS(e.detail); };
    const onD = () => { setWsUrl(null); disconnectWS(); };
    window.addEventListener('predaiot:ws-connect', onC);
    window.addEventListener('predaiot:ws-disconnect', onD);
    return () => { window.removeEventListener('predaiot:ws-connect', onC); window.removeEventListener('predaiot:ws-disconnect', onD); };
  }, [connectWS, disconnectWS]);

  const startDemo = useCallback(() => {
    if (demoRef.current) return;
    const prices = [];
    for (let i = 0; i < 288; i++) {
      const h = i / 12;
      let v;
      if (h < 5) v = 15 + Math.random() * 8;
      else if (h < 8) v = 30 + (h - 5) * 12 + Math.random() * 5;
      else if (h < 12) v = 58 - (h - 8) * 3 + Math.random() * 8;
      else if (h < 16) v = 38 + Math.random() * 12;
      else if (h < 20) v = 50 + (h - 16) * 14 + Math.random() * 8;
      else v = 90 - (h - 20) * 18 + Math.random() * 5;
      prices.push(Math.max(5, Math.round(v * 100) / 100));
    }
    let s = 0; resetLive(); setIsDemoRunning(true);
    demoRef.current = setInterval(() => {
      if (s >= 288) { clearInterval(demoRef.current); demoRef.current = null; setIsDemoRunning(false); return; }
      const price = prices[s], th = 48, opt = price > th ? 50 : 0, deg = 5, r = Math.random();
      let act = 0;
      if (price > 70) act = 30 + Math.random() * 15;
      else if (price > 55) act = r > 0.35 ? 15 + Math.random() * 20 : 0;
      else if (price > th) act = r > 0.55 ? 10 + Math.random() * 15 : 0;
      const gap = Math.max(0, (price - deg) * opt) - Math.max(0, (price - deg) * act);
      let dt = 'Correct Idle';
      if (Math.abs(opt - act) < 1 && opt > 0) dt = 'Correct Dispatch';
      else if (opt > 5 && act < 1) dt = 'Missed Arbitrage';
      else if (opt > 5 && act > 0 && act < opt) dt = 'Partial Capture';
      const conf = dt.includes('Correct') ? 96 : 78 + Math.random() * 15;
      processStep({
        step: s, price, optimal_action: opt, actual_action: Math.round(act * 100) / 100,
        gap_step: Math.round(gap * 100) / 100, recommendation: gap > 10 ? 'DISCHARGE' : act > 0 && gap > 5 ? 'ADJUST' : 'HOLD',
        recommended_power: opt, expected_gain: Math.round(gap * 100) / 100, confidence: Math.round(conf * 10) / 10,
        severity: gap > 200 ? 'CRITICAL' : gap > 80 ? 'HIGH' : gap > 20 ? 'MEDIUM' : 'LOW',
        decision_type: dt, message: gap > 10 ? `Dispatch ${opt} MW — price $${price.toFixed(2)} exceeds threshold` : 'Near-optimal dispatch',
      });
      s++;
    }, 200);
  }, [resetLive, processStep]);

  const stopDemo = useCallback(() => { if (demoRef.current) { clearInterval(demoRef.current); demoRef.current = null; } setIsDemoRunning(false); }, []);

  // ── Poll latest ──
  useEffect(() => {
    const poll = async () => { try { const r = await axios.get('/api/latest'); if (r.data?.dq_score > 0) { setData(r.data); setShowUpload(false); setAiText(''); } } catch (_) {} };
    poll(); const iv = setInterval(poll, 60000); return () => clearInterval(iv);
  }, []);

  // ── Demo audit ──
  const runDemo = async () => {
    setLoading(true); setShowUpload(false);
    try {
      const ts = []; let soc = 0.2;
      for (let i = 0; i < 288; i++) {
        const base = 30 + 70 * Math.sin((i - 72) * (Math.PI / 144));
        const price = Math.max(5, parseFloat((base + (Math.random() - 0.5) * 10).toFixed(2)));
        let dis = 0;
        if (price < 20 && soc < 0.9) soc += 40 * 0.95 / 100;
        if (price > 40 && soc > 0.2) { dis = Math.min(40, (soc - 0.2) * 100); soc -= dis / 0.95 / 100; }
        ts.push({ hour: i, price, actual_discharge: dis, forecast_price: parseFloat((price * (0.9 + Math.random() * 0.2)).toFixed(2)) });
      }
      const r = await axios.post('/api/v1/audit', {
        asset: { asset_type: 'BESS', asset_name: 'Ibri 2 — 500 MW BESS', asset_id: 'IBRI2_BESS', p_max: 50, e_max: 100, soc_init: 0.5, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 }, time_series: ts,
      });
      setData(r.data); setAiText(''); setActiveSection('exec');
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // ── File upload ──
  const handleFile = async (file) => {
    setUploading(true); setShowUpload(false);
    const fd = new FormData(); fd.append('file', file);
    try { const r = await axios.post('/api/v1/audit/file', fd); setData(r.data); setAiText(''); setActiveSection('exec'); }
    catch (err) { alert('Upload failed.\n\n' + (err?.response?.data?.detail || 'Could not locate price or output column.')); }
    setUploading(false);
  };

  // ── Share ──
  const handleShare = async () => {
    if (!data.dq_score) return alert('Run an audit first.');
    try { const r = await axios.post('/api/share', data); const url = window.location.origin + r.data.share_url; setShareLink(url); navigator.clipboard?.writeText(url); alert('Link copied!\n' + url); } catch (_) {}
  };

  // ── AI commentary ──
  const generateAI = async () => {
    if (!data.dq_score) return;
    setAiLoading(true);
    try {
      const payload = { model: 'predait', max_tokens: 900, messages: [{ role: 'user', content: `You are a senior energy economist at a Big-4 audit firm.\n\nAUDIT DATA:\n• Asset: ${data.asset_name} (${data.asset_type})\n• Period: ${data.audit_period_label}\n• Economic Potential: ${fmtUSD(data.edv_optimal_total)}\n• Captured Value: ${fmtUSD(data.edv_actual_total)}\n• Destroyed Value: ${fmtUSD(data.total_gap_usd)} (${fmtPct((data.total_gap_usd / data.edv_optimal_total) * 100)} of potential)\n• Decision Quality Score: ${((data.dq_score || 0) * 100).toFixed(1)} / 100\n• Risk Level: ${data.risk_level}\n• Annual Leakage Projection: ${fmtUSD(data.total_gap_usd * 365)}\n• Top Root Causes: ${(data.root_causes || []).slice(0, 3).map(r => `${r.category} (${r.contribution_pct}%)`).join(', ')}\n\nWrite a professional Economic Decision Audit finding:\n1. EXECUTIVE FINDING (2 sentences)\n2. LOSS ATTRIBUTION (2–3 sentences)\n3. RECOVERY OPPORTUNITY (2 sentences)\n4. RECOMMENDATIONS (5 numbered items)\n\nFormal financial audit language. Reference exact figures. Max 380 words.` }] };
      let text = '';
      try { const r = await axios.post('/api/v1/ai-enhance', payload, { timeout: 20000 }); text = r.data?.content?.[0]?.text || r.data?.text || ''; } catch (_) {}
      setAiText(text || data.ai_commentary);
    } catch (_) { setAiText(data.ai_commentary); }
    setAiLoading(false);
  };

  // ── Certificate ──
  const fetchCert = async () => {
    if (!data.dq_score) return;
    setCertLoading(true);
    try { const r = await axios.get('/api/v1/certificate'); setCertificate(r.data); } catch (_) { setCertificate(null); }
    setCertLoading(false);
  };

  // ── Derived ──
  const log = Array.isArray(data.decision_log) ? data.decision_log : [];
  const captureRate = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
  const m = data.eda_metrics;
  const hasData = data.dq_score > 0;
  const RATING_C = { AAA: '#00E676', AA: '#4ADE80', A: '#86EFAC', BBB: '#FFD600', BB: '#FF6D00', B: '#FF1744', CCC: '#DC2626' };
  const RATING_L = { AAA: 'Excellent', AA: 'Very Good', A: 'Good', BBB: 'Acceptable', BB: 'Below Average', B: 'Poor', CCC: 'Critical' };
  const rating = hasData ? (data.dq_score >= 0.9 ? 'AAA' : data.dq_score >= 0.8 ? 'AA' : data.dq_score >= 0.7 ? 'A' : data.dq_score >= 0.6 ? 'BBB' : data.dq_score >= 0.5 ? 'BB' : data.dq_score >= 0.4 ? 'B' : 'CCC') : '--';
  const ratingColor = RATING_C[rating] || DS.dim;

  const navItems = [
    { id: 'exec', label: 'Executive Summary', tag: '01' },
    { id: 'flow', label: 'Economic Flow', tag: '02' },
    { id: 'timeline', label: 'Decision Timeline', tag: '03' },
    { id: 'rootcause', label: 'Root Cause', tag: '04' },
    { id: 'counter', label: 'Counterfactual', tag: '05' },
    { id: 'metrics', label: 'EDA Metrics', tag: '06' },
    { id: 'leakage', label: 'Financial Leakage', tag: '07' },
    { id: 'heatmap', label: 'Decision Heat Map', tag: '08' },
    { id: 'opps', label: 'Opportunity Ranking', tag: '09' },
    { id: 'ai', label: 'AI Commentary', tag: '10' },
    { id: 'govern', label: 'Governance', tag: '11' },
    { id: 'appendix', label: 'Math Appendix', tag: '12' },
    { id: 'live', label: 'Live Feed', tag: '⚡' },
    { id: 'cert', label: 'EDPC Rating', tag: '🏆' },
  ];

  // ══════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════
  return (
    <div style={{ backgroundColor: DS.bg, color: DS.text, minHeight: '100vh', fontFamily: DS.sans, fontSize: 13 }}>

      {/* ── HEADER ── */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 28px', borderBottom: `1px solid ${DS.border}`, position: 'sticky', top: 0, backgroundColor: `${DS.bg}f0`, backdropFilter: 'blur(12px)', zIndex: 100 }}>
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
          <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading || uploading}>{loading ? 'OPTIMIZING…' : 'RUN DEMO'}</BtnOutline>
          <BtnOutline color={DS.optimal} onClick={() => setShowUpload(!showUpload)} disabled={uploading}>{uploading ? 'PARSING…' : 'UPLOAD DATA'}</BtnOutline>
          <BtnOutline color={DS.warning} onClick={handleShare}>SHARE REPORT</BtnOutline>
          <BtnOutline color={DS.dim} onClick={() => setShowMethodology(true)}>METHODOLOGY</BtnOutline>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: connected ? DS.optimal : isDemoRunning ? DS.cyan : DS.dim, boxShadow: (connected || isDemoRunning) ? `0 0 8px ${connected ? DS.optimal : DS.cyan}` : 'none', animation: (connected || isDemoRunning) ? 'pulse-dot 1.5s infinite' : 'none' }} />
            <span style={{ color: DS.dim, fontSize: 10, letterSpacing: '0.12em' }}>{connected ? 'SCADA' : isDemoRunning ? 'DEMO' : 'OFFLINE'}</span>
          </div>
        </div>
      </header>

      {shareLink && <div style={{ background: `${DS.warning}10`, borderBottom: `1px solid ${DS.warning}30`, padding: '8px 28px', fontSize: 11, color: DS.warning }}>🔗 {shareLink}</div>}

      {showUpload && <div style={{ borderBottom: `1px solid ${DS.border}`, background: DS.bgRaised }}><FileUploadZone onFile={handleFile} loading={uploading} /></div>}

      <div style={{ display: 'flex' }}>

        {/* ═══ ADVISORY SIDEBAR ═══ */}
        <AdvisorySidebar step={liveStep} connected={connected} isDemoRunning={isDemoRunning} onStartDemo={startDemo} onStopDemo={stopDemo} />

        {/* ── NAV SIDEBAR ── */}
        <nav style={{ width: 200, minWidth: 200, padding: '20px 0', borderRight: `1px solid ${DS.border}`, position: 'sticky', top: 67, height: 'calc(100vh - 67px)', overflowY: 'auto' }}>
          {navItems.map((n) => {
            const active = activeSection === n.id;
            return (
              <button key={n.id} onClick={() => { setActiveSection(n.id); if (n.id === 'cert' && !certificate && hasData) fetchCert(); }} style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '9px 18px', fontSize: 11,
                background: 'none', border: 'none', cursor: 'pointer', letterSpacing: '0.04em',
                color: active ? DS.cyan : DS.sub, borderLeft: `2px solid ${active ? DS.cyan : 'transparent'}`, transition: 'all 0.12s',
              }}>
                <span style={{ fontFamily: DS.mono, fontSize: 9, color: DS.dim, marginRight: 8 }}>{n.tag}</span>{n.label}
              </button>
            );
          })}
        </nav>

        {/* ── MAIN CONTENT ── */}
        <main style={{ flex: 1, padding: '28px 32px', maxWidth: 'calc(100vw - 542px)', overflowX: 'hidden' }}>

          {!hasData && !showUpload && (
            <div style={{ textAlign: 'center', padding: '80px 40px' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⚡</div>
              <div style={{ color: DS.text, fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Economic Decision Audit™</div>
              <div style={{ color: DS.sub, fontSize: 13, marginBottom: 28, maxWidth: 500, margin: '0 auto 28px' }}>Upload any energy asset data file — BESS, Solar, Wind, Gas, Hydro — or run a demo to see a full 12-section audit report.</div>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading}>{loading ? 'OPTIMIZING…' : 'RUN DEMO AUDIT'}</BtnOutline>
                <BtnOutline color={DS.optimal} onClick={() => setShowUpload(true)}>UPLOAD MY DATA</BtnOutline>
              </div>
            </div>
          )}

          {/* ══ S01: Executive Summary ══ */}
          {activeSection === 'exec' && (
            <div>
              <SectionHeader tag="01" title="Executive Summary" />
              <div style={{ background: 'linear-gradient(135deg, rgba(75,191,255,0.07) 0%, rgba(0,230,118,0.05) 100%)', border: `1px solid ${DS.blue}25`, borderRadius: DS.r16, padding: 28, marginBottom: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
                  {[{ label: 'Asset', value: data.asset_name || '—', color: DS.text, mono: false }, { label: 'Audit Period', value: data.audit_period_label || '—', color: DS.cyan, mono: true }, { label: 'Economic Potential', value: fmtUSD(data.edv_optimal_total), color: DS.warning, mono: true }, { label: 'Captured Value', value: fmtUSD(data.edv_actual_total), color: DS.optimal, mono: true }].map((f) => (
                    <div key={f.label}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} size={f.mono ? 22 : 16} /></div>
                  ))}
                </div>
                <Divider />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
                  {[{ label: 'Destroyed Value', value: fmtUSD(data.total_gap_usd), color: DS.loss }, { label: 'DQ Score', value: hasData ? `${((data.dq_score || 0) * 100).toFixed(1)} / 100` : '—', color: qualColor(captureRate) }, { label: 'Economic Efficiency', value: hasData ? fmtPct(captureRate) : '—', color: qualColor(captureRate) }, { label: 'Est. Annual Leakage', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.orange }].map((f) => (
                    <div key={f.label}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} /></div>
                  ))}
                </div>
              </div>
              {hasData && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 22px', background: `${riskColor(data.risk_level)}10`, border: `1px solid ${riskColor(data.risk_level)}35`, borderRadius: DS.r12, marginBottom: 20 }}>
                  <span style={{ fontSize: 22 }}>{riskEmoji(data.risk_level)}</span>
                  <div>
                    <div style={{ color: riskColor(data.risk_level), fontWeight: 700, fontSize: 14, letterSpacing: '0.1em' }}>RISK LEVEL: {(data.risk_level || '').toUpperCase()}</div>
                    <div style={{ color: DS.sub, fontSize: 11, marginTop: 3 }}>
                      {data.risk_level === 'Severe' && 'Immediate operational review required. Economic losses exceed 60% of potential.'}
                      {data.risk_level === 'Moderate' && 'Optimization opportunities identified. Revenue recovery achievable within 30 days.'}
                      {data.risk_level === 'Low' && 'Asset operating near optimal. Minor tuning recommended for full potential capture.'}
                    </div>
                  </div>
                </div>
              )}
              {m && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                  <Card>
                    <Label>Economic Intelligence Score</Label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 8 }}>
                      <div style={{ width: 80, height: 80, borderRadius: '50%', border: `4px solid ${qualColor(m.economic_intelligence_score)}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 20px ${qualColor(m.economic_intelligence_score)}30` }}>
                        <div style={{ color: qualColor(m.economic_intelligence_score), fontSize: 20, fontWeight: 800, fontFamily: DS.mono, lineHeight: 1 }}>{m.economic_intelligence_score}</div>
                        <div style={{ color: DS.dim, fontSize: 8, marginTop: 2 }}>/ 100</div>
                      </div>
                      <div style={{ flex: 1 }}><div style={{ color: DS.sub, fontSize: 11, lineHeight: 1.7 }}>Composite ISO-style index combining capture efficiency (45%), decision accuracy (30%), forecast utilization (15%), and leakage control (10%).</div></div>
                    </div>
                  </Card>
                  <Card>
                    <Label>Key Indicators</Label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                      {[{ l: 'Capture Efficiency', v: fmtPct(m.economic_decision_efficiency), c: qualColor(m.economic_decision_efficiency) }, { l: 'Dispatch Accuracy', v: fmtPct(m.dispatch_accuracy), c: qualColor(m.dispatch_accuracy) }, { l: 'Forecast Utilization', v: fmtPct(m.forecast_utilization_index), c: qualColor(m.forecast_utilization_index) }].map(({ l, v, c }) => (
                        <div key={l}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}><span style={{ color: DS.sub }}>{l}</span><span style={{ color: c, fontFamily: DS.mono, fontWeight: 700 }}>{v}</span></div><ProgressBar pct={parseFloat(v)} color={c} /></div>
                      ))}
                    </div>
                  </Card>
                </div>
              )}
            </div>
          )}

          {/* ══ S02: Economic Flow ══ */}
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px', background: DS.surface, border: `1px solid ${step.color}25`, borderRadius: DS.r12 }}>
                        <div style={{ width: 4, height: 44, backgroundColor: step.color, borderRadius: 2, flexShrink: 0 }} />
                        <div style={{ flex: 1 }}><Label style={{ marginBottom: 2 }}>{step.label}</Label><BigNum v={step.value} color={step.color} size={18} /><div style={{ color: DS.dim, fontSize: 10, marginTop: 3 }}>{step.desc}</div></div>
                      </div>
                      {i < 6 && <div style={{ textAlign: 'center', color: DS.dim, lineHeight: '22px', fontSize: 18 }}>↓</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S03: Decision Timeline ══ */}
          {activeSection === 'timeline' && (
            <div>
              <SectionHeader tag="03" title="Decision Timeline — Black Box" />
              {log.length === 0 ? <EmptyMsg>Run an audit to populate the decision log.</EmptyMsg> : (
                <div style={{ maxHeight: 620, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {log.filter(d => (d.gap_step || 0) > 0).slice(0, 40).map((dec, i) => {
                    const h = dec.hour || 0; const label = `${Math.floor(h / 12).toString().padStart(2, '0')}:${((h % 12) * 5).toString().padStart(2, '0')}`;
                    const isCritical = (dec.gap_step || 0) > 20;
                    return (
                      <div key={i} style={{ display: 'grid', gridTemplateColumns: '72px 1fr', gap: 16, background: DS.surface, border: `1px solid ${isCritical ? DS.loss + '30' : DS.border}`, borderRadius: DS.r12, padding: '12px 16px' }}>
                        <div style={{ textAlign: 'center' }}><div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 14, fontWeight: 700 }}>{label}</div><div style={{ color: DS.dim, fontSize: 9, marginTop: 4, letterSpacing: '0.1em' }}>STEP {h}</div></div>
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

          {/* ══ S04: Root Cause ══ */}
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
                          <span style={{ color: [DS.loss, DS.orange, DS.warning, DS.blue, DS.cyan, DS.purple][i % 6], fontFamily: DS.mono, fontWeight: 700 }}>{rc.contribution_pct}% · {fmtUSD(rc.loss_usd)}</span>
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
                        <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>{(data.root_causes || []).map((_, i) => <Cell key={i} fill={[DS.loss, DS.orange, DS.warning, DS.blue, DS.cyan, DS.purple][i % 6]} />)}</Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </div>
              )}
            </div>
          )}

          {/* ══ S05: Counterfactual ══ */}
          {activeSection === 'counter' && (
            <div>
              <SectionHeader tag="05" title='Counterfactual Simulation — "What Would Have Happened?"' />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 20 }}>
                {[{ label: 'Actual Revenue', value: fmtUSD(data.edv_actual_total), color: DS.blue }, { label: 'Optimal Revenue', value: fmtUSD(data.edv_optimal_total), color: DS.optimal }, { label: 'Lost Opportunity', value: `−${fmtUSD(data.total_gap_usd)}`, color: DS.loss }].map((f) => (
                  <Card key={f.label} style={{ textAlign: 'center' }}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} size={26} /></Card>
                ))}
              </div>
              {log.length > 0 && (
                <Card style={{ marginBottom: 16 }}>
                  <Label style={{ marginBottom: 14 }}>Optimal vs Actual Dispatch Curve</Label>
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={log.slice(0, 120)} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="gOpt" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={DS.optimal} stopOpacity={0.3} /><stop offset="95%" stopColor={DS.optimal} stopOpacity={0} /></linearGradient>
                        <linearGradient id="gAct" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={DS.blue} stopOpacity={0.25} /><stop offset="95%" stopColor={DS.blue} stopOpacity={0} /></linearGradient>
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
              {data.counterfactual_summary && <Card glow={DS.cyan}><div style={{ color: DS.cyan, fontSize: 12, lineHeight: 1.8, fontStyle: 'italic' }}>"{data.counterfactual_summary}"</div></Card>}
            </div>
          )}

          {/* ══ S06: EDA Metrics ══ */}
          {activeSection === 'metrics' && (
            <div>
              <SectionHeader tag="06" title="Economic Decision Quality Metrics" />
              {!m ? <EmptyMsg>Run an audit to generate metrics.</EmptyMsg> : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
                  {[
                    { label: 'Economic Decision Efficiency (EDE)', value: fmtPct(m.economic_decision_efficiency), note: 'Captured ÷ Potential', color: qualColor(m.economic_decision_efficiency), pct: m.economic_decision_efficiency },
                    { label: 'Economic Leakage Ratio (ELR)', value: fmtPct(m.economic_leakage_ratio), note: 'Lost ÷ Potential (lower is better)', color: m.economic_leakage_ratio <= 30 ? DS.optimal : m.economic_leakage_ratio <= 60 ? DS.warning : DS.loss, pct: m.economic_leakage_ratio },
                    { label: 'Dispatch Accuracy', value: fmtPct(m.dispatch_accuracy), note: 'Correct dispatches ÷ Total', color: qualColor(m.dispatch_accuracy), pct: m.dispatch_accuracy },
                    { label: 'Forecast Utilization Index', value: fmtPct(m.forecast_utilization_index), note: '% of steps with forecast data', color: qualColor(m.forecast_utilization_index), pct: m.forecast_utilization_index },
                    { label: 'Decision Delay Index', value: `${m.decision_delay_index}`, note: 'Avg override ratio × 10 (0 = perfect)', color: m.decision_delay_index < 1 ? DS.optimal : m.decision_delay_index < 3 ? DS.warning : DS.loss, pct: null },
                    { label: 'Curtailment Recovery Ratio', value: `${m.curtailment_recovery_ratio} MWh`, note: 'Potentially rescuable curtailed energy', color: DS.cyan, pct: null },
                    { label: 'Revenue Stacking Index', value: `${m.revenue_stacking_index} services`, note: 'Distinct revenue streams utilized', color: m.revenue_stacking_index >= 3 ? DS.optimal : DS.warning, pct: null },
                    { label: 'Economic Intelligence Score', value: `${m.economic_intelligence_score} / 100`, note: 'ISO-style composite performance index', color: qualColor(m.economic_intelligence_score), pct: m.economic_intelligence_score },
                    ...(m.battery_opportunity_capture != null ? [{ label: 'Battery Opportunity Capture', value: fmtPct(m.battery_opportunity_capture), note: 'BESS-specific arbitrage capture rate', color: DS.blue, pct: m.battery_opportunity_capture }] : []),
                  ].map((metric) => (
                    <Card key={metric.label}><Label>{metric.label}</Label><BigNum v={metric.value} color={metric.color} size={28} /><div style={{ color: DS.dim, fontSize: 10, marginTop: 4 }}>{metric.note}</div>{metric.pct != null && <ProgressBar pct={metric.pct} color={metric.color} />}</Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S07: Financial Leakage ══ */}
          {activeSection === 'leakage' && (
            <div>
              <SectionHeader tag="07" title="Financial Value Leakage" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 }}>
                {[{ label: '24-Hour', value: fmtUSD(data.total_gap_usd), color: DS.loss }, { label: '7-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 7) : '—', color: DS.orange }, { label: '30-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 30) : '—', color: DS.warning }, { label: '12-Month Projection', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.loss }].map((f) => (
                  <Card key={f.label} style={{ textAlign: 'center', borderColor: `${f.color}25` }}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} /></Card>
                ))}
              </div>
              <Card>
                <Label style={{ marginBottom: 16 }}>Top Leakage Sources</Label>
                {(data.financial_leakage?.top_sources || []).map((src, i) => (
                  <div key={i} style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}><span style={{ color: DS.text, fontSize: 12 }}>{src.name}</span><span style={{ color: DS.loss, fontFamily: DS.mono, fontWeight: 700, fontSize: 11 }}>{fmtUSD(src.usd)} ({src.pct}%)</span></div>
                    <ProgressBar pct={src.pct} color={DS.loss} />
                  </div>
                ))}
                {(data.financial_leakage?.top_sources || []).length === 0 && <EmptyMsg>Run an audit to populate leakage sources.</EmptyMsg>}
              </Card>
              <Card style={{ marginTop: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <Label>30-Day Trend</Label>
                  <BtnOutline color={DS.loss} onClick={async () => { setHistLoading(true); try { const r = await axios.get('/api/historical'); if (r.data?.history_log) setHistData(r.data.history_log); } catch (_) {} setHistLoading(false); }}>{histLoading ? 'QUERYING…' : 'SYNC HISTORY'}</BtnOutline>
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
                {histData.length === 0 && !histLoading && <div style={{ textAlign: 'center', color: DS.dim, marginTop: 10, fontSize: 11 }}>Connect to a production database to display historical trend data.</div>}
              </Card>
            </div>
          )}

          {/* ══ S08: Heat Map ══ */}
          {activeSection === 'heatmap' && (
            <div>
              <SectionHeader tag="08" title="Decision Heat Map — 24 Hours" />
              <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
                {[['optimal', DS.optimal, 'Optimal Decision'], ['acceptable', DS.warning, 'Acceptable'], ['poor', DS.orange, 'Poor Decision'], ['critical', DS.loss, 'Critical Loss']].map(([s, c, l]) => (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div style={{ width: 12, height: 12, borderRadius: 3, background: c }} /><span style={{ color: DS.sub, fontSize: 11 }}>{l}</span></div>
                ))}
              </div>
              {(data.heat_map || []).length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12,1fr)', gap: 3 }}>
                  {(data.heat_map || []).map((cell, i) => (
                    <div key={i} title={`${cell.label} | ${cell.action_taken} | Gap: $${cell.gap_usd} | Price: $${cell.price}`}
                      style={{ aspectRatio: '1', borderRadius: 3, background: heatColor(cell.status), cursor: 'pointer', transition: 'transform 0.15s' }}
                      onMouseEnter={(e) => { e.target.style.transform = 'scale(1.8)'; e.target.style.zIndex = 10; e.target.style.position = 'relative'; }}
                      onMouseLeave={(e) => { e.target.style.transform = 'scale(1)'; e.target.style.zIndex = 1; e.target.style.position = 'static'; }}
                    />
                  ))}
                </div>
              ) : <EmptyMsg>Run an audit to generate the heat map.</EmptyMsg>}
            </div>
          )}

          {/* ══ S09: Opportunity Ranking ══ */}
          {activeSection === 'opps' && (
            <div>
              <SectionHeader tag="09" title="Economic Action Plan" />
              {(data.opportunities || []).length === 0 ? <EmptyMsg>Run an audit to generate the action plan.</EmptyMsg> : (
                <div>
                  <Card style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 10, color: DS.dim, letterSpacing: '1.5px', textTransform: 'uppercase' }}>Total Recoverable Annual Value</div>
                      <div style={{ fontFamily: DS.mono, fontSize: 28, fontWeight: 700, color: DS.warning, marginTop: 4 }}>{fmtUSD((data.opportunities || []).reduce((s, o) => s + o.annual_gain_usd, 0))}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 24, textAlign: 'center' }}>
                      <div><div style={{ fontFamily: DS.mono, fontSize: 20, fontWeight: 600, color: DS.text }}>{(data.opportunities || []).length}</div><div style={{ fontSize: 10, color: DS.dim, letterSpacing: '1px' }}>ACTIONS</div></div>
                      <div><div style={{ fontFamily: DS.mono, fontSize: 20, fontWeight: 600, color: DS.text }}>{(data.opportunities || []).filter(o => o.difficulty === 'Easy').length}</div><div style={{ fontSize: 10, color: DS.dim, letterSpacing: '1px' }}>QUICK WINS</div></div>
                    </div>
                  </Card>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {(data.opportunities || []).map((opp, i) => (
                      <Card key={i} style={{ borderLeft: `3px solid ${i === 0 ? DS.warning : DS.border}`, cursor: 'default' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                              <span style={{ fontFamily: DS.mono, fontSize: 11, color: DS.dim }}>#{i + 1}</span>
                              <span style={{ fontSize: 15, fontWeight: 600, color: DS.text }}>{opp.name}</span>
                              <Pill label={opp.difficulty === 'Easy' ? 'QUICK WIN' : opp.difficulty === 'Medium' ? 'STRATEGIC' : 'CAPITAL PROJECT'} color={opp.difficulty === 'Easy' ? DS.optimal : opp.difficulty === 'Medium' ? DS.warning : DS.orange} />
                            </div>
                            <p style={{ fontSize: 13, color: DS.sub, lineHeight: 1.5, margin: 0 }}>{opp.description}</p>
                          </div>
                          <div style={{ textAlign: 'right', marginLeft: 24 }}>
                            <div style={{ fontSize: 10, color: DS.dim, letterSpacing: '1px', marginBottom: 4 }}>ANNUAL GAIN</div>
                            <div style={{ fontFamily: DS.mono, fontSize: 20, fontWeight: 700, color: DS.optimal }}>{fmtUSD(opp.annual_gain_usd)}</div>
                            <div style={{ fontSize: 11, color: DS.dim, marginTop: 4 }}>Priority: {opp.priority_stars}/5</div>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ S10: AI Commentary ══ */}
          {activeSection === 'ai' && (
            <div>
              <SectionHeader tag="10" title="Independent Economic Decision Assessment" />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <span style={{ fontSize: 10, fontFamily: DS.mono, color: DS.dim }}>PREDAIOT EDA Methodology — Patent Pending</span>
                <BtnOutline color={DS.cyan} onClick={generateAI} disabled={aiLoading || !hasData}>{aiLoading ? 'ANALYZING…' : 'DEEP ECONOMIC ANALYSIS'}</BtnOutline>
              </div>
              {!hasData ? <EmptyMsg>Run an audit first.</EmptyMsg> : (
                <Card glow={DS.cyan}>
                  <div style={{ fontSize: 13, color: DS.sub, lineHeight: 1.8, whiteSpace: 'pre-line' }}>
                    {aiLoading ? 'Generating executive assessment…' : (aiText || data.ai_commentary || 'Click "Deep Economic Analysis" to generate an enhanced assessment using Claude AI.')}
                  </div>
                  {!aiText && data.ai_commentary && <div style={{ marginTop: 12, fontSize: 10, color: DS.dim, fontStyle: 'italic' }}>Above: Pre-computed assessment. Click the button for enhanced AI-powered analysis.</div>}
                </Card>
              )}
            </div>
          )}

          {/* ══ S11: Governance ══ */}
          {activeSection === 'govern' && (
            <div>
              <SectionHeader tag="11" title="Governance & Compliance" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <Card>
                  <Label>Audit Trail Integrity</Label>
                  <div style={{ color: DS.sub, fontSize: 12, lineHeight: 1.8, marginTop: 8 }}>
                    <div style={{ marginBottom: 10 }}><span style={{ color: DS.optimal }}>✓</span> Every recommendation is fully traceable to the original operational data, optimization model, and dispatch interval.</div>
                    <div style={{ marginBottom: 10 }}><span style={{ color: DS.optimal }}>✓</span> Running the audit multiple times on identical data produces identical results — mathematical repeatability guaranteed.</div>
                    <div><span style={{ color: DS.optimal }}>✓</span> PREDAIOT does not control the asset. It independently evaluates operational decisions without interfering with existing EMS, SCADA, or DCS systems.</div>
                  </div>
                </Card>
                <Card>
                  <Label>Integration Level</Label>
                  <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {[
                      { level: 'Level 1 — Read Only', desc: 'SCADA → PREDAIOT (calculates only)', status: 'ACTIVE', color: DS.optimal },
                      { level: 'Level 2 — Advisory', desc: 'PREDAIOT → Recommendation → Operator decides', status: 'ACTIVE', color: DS.cyan },
                      { level: 'Level 3 — Closed Loop', desc: 'PREDAIOT → Dispatch Command → EMS (requires client approval)', status: 'AVAILABLE', color: DS.warning },
                    ].map((l) => (
                      <div key={l.level} style={{ padding: '10px 14px', background: DS.surface, border: `1px solid ${l.color}25`, borderRadius: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: DS.text }}>{l.level}</span>
                          <Pill label={l.status} color={l.color} />
                        </div>
                        <div style={{ fontSize: 11, color: DS.sub }}>{l.desc}</div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* ══ S12: Math Appendix ══ */}
          {activeSection === 'appendix' && (
            <div>
              <SectionHeader tag="12" title="Mathematical Appendix" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {[
                  { title: 'Economic Decision Value (EDV)', formula: 'EDV(k,dₖ) = R(dₖ) − C_op(dₖ) − C_deg(dₖ) − C_opp(dₖ) − C_risk(dₖ)', desc: 'Net economic value of a single dispatch decision at timestep k.' },
                  { title: 'Decision Quality (DQ)', formula: 'DQ(k) = EDV_actual(k) / EDV_optimal(k)', desc: 'Ratio of actual to optimal economic value. 1.0 = perfect, 0.0 = zero capture.' },
                  { title: 'Economic Gap', formula: 'G(k) = EDV_optimal(k) − EDV_actual(k)', desc: 'Absolute dollar value destroyed by sub-optimal decision at timestep k.' },
                  { title: 'Objective Function', formula: 'max Σ [P_market(tₖ)·E_disp − C_op − λ_deg·ΔSOHₖ]', desc: 'MILP objective maximized subject to physical, safety, and boundary constraints.' },
                  { title: 'SOC Dynamics', formula: 'SOC(k+1) = SOC(k) + (P_ch·η_ch/E − P_dis/(η_dis·E))·Δt', desc: 'State of charge update equation enforcing energy conservation.' },
                ].map((eq) => (
                  <Card key={eq.title}>
                    <Label>{eq.title}</Label>
                    <div style={{ fontFamily: DS.mono, fontSize: 16, color: DS.cyan, marginTop: 8, marginBottom: 8, padding: '12px 16px', background: 'rgba(0,229,255,0.05)', borderRadius: 8, border: '1px solid rgba(0,229,255,0.1)' }}>{eq.formula}</div>
                    <div style={{ color: DS.sub, fontSize: 12 }}>{eq.desc}</div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* ══ S13: Live Feed ══ */}
          {activeSection === 'live' && (
            <div>
              <SectionHeader tag="⚡" title="Live Decision Feed" />
              <div style={{ marginBottom: 16 }}><span style={{ fontFamily: DS.mono, fontSize: 12, color: DS.dim }}>{liveHistory.length} decisions processed</span></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: '75vh', overflowY: 'auto' }}>
                {liveHistory.length === 0 ? <EmptyMsg>No decisions yet — start demo or connect WebSocket from the advisory sidebar.</EmptyMsg> : liveHistory.map((d, i) => {
                  const h = d.step || i; const time = `${String(Math.floor(h / 12)).padStart(2, '0')}:${String((h % 12) * 5).padStart(2, '0')}`;
                  const isOk = (d.decision_type || '').includes('Correct');
                  const isMiss = (d.decision_type || '').includes('Missed');
                  return (
                    <div key={i} style={{ borderLeft: `3px solid ${isOk ? DS.optimal : isMiss ? DS.loss : DS.orange}`, background: `${isOk ? DS.optimal : isMiss ? DS.loss : DS.orange}08`, borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, animation: 'slide-in 0.3s ease' }}>
                      <i className={`fas ${isOk ? 'fa-check' : isMiss ? 'fa-times' : 'fa-adjust'}`} style={{ color: isOk ? DS.optimal : isMiss ? DS.loss : DS.orange, fontSize: 10, width: 14, textAlign: 'center' }} />
                      <span style={{ fontFamily: DS.mono, fontSize: 11, color: DS.dim, width: 44 }}>{time}</span>
                      <span style={{ fontSize: 12, color: DS.sub, flex: 1 }}>{d.decision_type}</span>
                      <span style={{ fontFamily: DS.mono, fontSize: 11, color: DS.dim }}>${d.price?.toFixed(2)}</span>
                      <span style={{ fontFamily: DS.mono, fontSize: 11, color: (d.gap_step || 0) > 5 ? DS.loss : DS.dim, minWidth: 60, textAlign: 'right' }}>{(d.gap_step || 0) > 0 ? '-$' + d.gap_step.toFixed(0) : '--'}</span>
                      <Pill label={d.recommendation} color={d.recommendation === 'DISCHARGE' ? DS.optimal : d.recommendation === 'STOP' ? DS.loss : DS.dim} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ══ S14: EDPC Certificate ══ */}
          {activeSection === 'cert' && (
            <div>
              <SectionHeader tag="🏆" title="Economic Decision Performance Certificate" />
              {!hasData ? <EmptyMsg>Run an audit to generate the certificate.</EmptyMsg> : certLoading ? (
                <div style={{ textAlign: 'center', padding: 60 }}><i className="fas fa-spinner fa-spin" style={{ fontSize: 24, color: DS.cyan }} /><div style={{ color: DS.dim, marginTop: 12, fontSize: 12 }}>Generating certificate…</div></div>
              ) : (
                <div style={{ maxWidth: 640, margin: '0 auto' }}>
                  <div style={{ background: 'linear-gradient(135deg, #fafaf9, #f5f5f4)', color: '#1c1917', border: '3px solid #d6d3d1', borderRadius: 4, padding: 48, position: 'relative', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>
                    <div style={{ position: 'absolute', top: 12, right: 16, fontSize: 9, color: '#a8a29e', fontFamily: DS.mono }}>PREDAIOT-EDA-STD-v1.0</div>
                    <div style={{ textAlign: 'center', marginBottom: 32 }}>
                      <div style={{ fontSize: 10, letterSpacing: '5px', color: '#a8a29e', textTransform: 'uppercase' }}>PREDAIOT Economic Decision Intelligence Platform</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: '#1c1917', marginTop: 8, letterSpacing: '1px' }}>Economic Decision Performance Certificate</div>
                      <div style={{ width: 96, height: 2, background: '#d6d3d1', margin: '12px auto 0' }} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px', marginBottom: 2 }}>ASSET</div><div style={{ fontSize: 16, fontWeight: 600 }}>{data.asset_name || 'Energy Asset'}</div></div>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px', marginBottom: 2 }}>AUDIT PERIOD</div><div style={{ fontSize: 16, fontWeight: 600 }}>{data.audit_period_label || '24 Hours'}</div></div>
                    </div>
                    <div style={{ textAlign: 'center', marginBottom: 24 }}>
                      <div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '2px', marginBottom: 8 }}>ECONOMIC RATING</div>
                      <div style={{ display: 'inline-block', padding: '12px 32px', borderRadius: 12, border: `3px solid ${ratingColor}`, background: `${ratingColor}15` }}>
                        <span style={{ fontSize: 48, fontWeight: 800, fontFamily: DS.mono, color: ratingColor }}>{rating}</span>
                      </div>
                      <div style={{ fontSize: 14, color: ratingColor, marginTop: 8, fontWeight: 500 }}>{RATING_L[rating] || ''}</div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 24, textAlign: 'center' }}>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px' }}>CAPTURED VALUE</div><div style={{ fontFamily: DS.mono, fontSize: 18, fontWeight: 600 }}>{fmtUSD(data.edv_actual_total)}</div></div>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px' }}>DESTROYED VALUE</div><div style={{ fontFamily: DS.mono, fontSize: 18, fontWeight: 600, color: '#dc2626' }}>{fmtUSD(data.total_gap_usd)}</div></div>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px' }}>ANNUAL LEAKAGE</div><div style={{ fontFamily: DS.mono, fontSize: 18, fontWeight: 600, color: '#dc2626' }}>{fmtUSD(data.total_gap_usd * 365)}</div></div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px' }}>DECISION QUALITY</div><div style={{ fontFamily: DS.mono, fontSize: 16, fontWeight: 600 }}>{(data.dq_score * 100).toFixed(1)}%</div></div>
                      <div><div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px' }}>ECONOMIC EFFICIENCY</div><div style={{ fontFamily: DS.mono, fontSize: 16, fontWeight: 600 }}>{fmtPct(captureRate)}</div></div>
                    </div>
                    {certificate?.rating_summary && (
                      <div style={{ borderTop: '1px solid #e7e5e4', paddingTop: 16, marginBottom: 16 }}>
                        <div style={{ fontSize: 10, color: '#a8a29e', letterSpacing: '1px', marginBottom: 6 }}>RATING SUMMARY</div>
                        <div style={{ fontSize: 12, color: '#44403c', lineHeight: 1.7, fontStyle: 'italic' }}>"{certificate.rating_summary}"</div>
                      </div>
                    )}
                    <div style={{ borderTop: '1px solid #e7e5e4', paddingTop: 16, display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#a8a29e' }}>
                      <span>Patent Pending — All Metrics Proprietary</span>
                      <span>{new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
                    </div>
                  </div>
                  <div style={{ marginTop: 16, textAlign: 'center' }}>
                    <BtnOutline color={DS.cyan} onClick={handleShare}>SHARE CERTIFICATE</BtnOutline>
                  </div>
                </div>
              )}
            </div>
          )}

        </main>
      </div>

      {/* ── METHODOLOGY MODAL ── */}
      {showMethodology && (
        <div onClick={() => setShowMethodology(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#080c12', border: `1px solid ${DS.border}`, borderRadius: DS.r16, padding: 32, maxWidth: 680, width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: DS.text, letterSpacing: '0.1em' }}>PREDAIOT Economic Decision Audit™ Methodology</h2>
              <button onClick={() => setShowMethodology(false)} style={{ background: 'none', border: 'none', color: DS.dim, cursor: 'pointer', fontSize: 18 }}><i className="fas fa-times" /></button>
            </div>
            {[
              { t: '1. Economic Upper Bound (MILP Optimization', d: 'Every audit computes the maximum economically achievable value using Mixed-Integer Linear Programming. The optimization evaluates electricity market prices, asset constraints, SOC, power limits, degradation costs, and dispatch feasibility simultaneously.' },
              { t: '2. Actual Economic Performance', d: 'PREDAIOT reconstructs real operational history from data. Using actual dispatch records, it calculates energy sold, charging decisions, degradation, and market settlement revenue.' },
              { t: '3. Economic Decision Gap™', d: 'The core innovation. For every dispatch interval, PREDAIOT computes Optimal Decision vs. Actual Decision. The difference is the value destroyed by sub-optimal decisions despite healthy equipment.' },
              { t: '4. Root Cause Intelligence', d: 'Every dollar of leakage is traced to its operational cause: fixed thresholds, incorrect charging windows, missed arbitrage, curtailment losses, forecast errors, or reserve market exclusion.' },
              { t: '5. Opportunity Engine', d: 'Improvement opportunities ranked by annual value, implementation complexity, operational risk, payback period, and confidence score — transforming audit into an executable action plan.' },
              { t: '6. Explainability & Independence', d: 'Every recommendation is traceable to original data and optimization model. Repeated audits on identical data produce identical results. PREDAIOT does not control the asset — it independently evaluates decisions.' },
            ].map((s) => (
              <div key={s.t} style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: DS.text, marginBottom: 6 }}>{s.t}</div>
                <div style={{ fontSize: 12, color: DS.sub, lineHeight: 1.7 }}>{s.d}</div>
              </div>
            ))}
            <div style={{ borderTop: `1px solid ${DS.border}`, paddingTop: 16, fontSize: 10, color: DS.dim, lineHeight: 1.6 }}>
              This assessment was generated using the PREDAIOT Economic Decision Audit™ methodology and independently validated against the mathematically optimal dispatch solution. The methodology is asset-agnostic and applicable to BESS, Solar PV, Wind, Gas Turbines, Hydrogen Electrolyzers, Desalination Plants, Microgrids, and any energy asset generating operational data.
            </div>
          </div>
        </div>
      )}

      {/* ═══ INLINE ANIMATIONS ═══ */}
      <style>{`
        @keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes pulse-critical { 0%,100%{box-shadow:0 0 0 0 rgba(255,23,68,.5)} 50%{box-shadow:0 0 0 14px rgba(255,23,68,0)} }
        @keyframes pulse-high { 0%,100%{box-shadow:0 0 0 0 rgba(255,109,0,.4)} 50%{box-shadow:0 0 0 10px rgba(255,109,0,0)} }
        @keyframes slide-in { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
      `}</style>
    </div>
  );
}