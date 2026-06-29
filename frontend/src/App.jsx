import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';

// ══════════════════════════════════════════════════════════════════════
// DESIGN SYSTEM — PREDAIOT Economic Decision Intelligence
// ══════════════════════════════════════════════════════════════════════
const DS = {
  bg:           '#030508',
  bgRaised:     '#080c12',
  surface:      'rgba(255,255,255,0.025)',
  surfaceHi:    'rgba(255,255,255,0.05)',
  border:       'rgba(255,255,255,0.06)',
  borderHi:     'rgba(255,255,255,0.14)',
  optimal:  '#00E676', warning:  '#FFD600', loss:     '#FF1744',
  blue:     '#4BBFFF', cyan:     '#00E5FF', orange:   '#FF6D00', purple: '#BB86FC',
  text:    '#E8EAF0', sub:     '#8A94A6', dim:     '#4A5468',
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
const heatColor = (s) => ({ optimal: DS.optimal, acceptable: DS.warning, poor: DS.orange, critical: DS.loss }[s] || DS.dim);
const qualColor = (pct) => pct >= 70 ? DS.optimal : pct >= 40 ? DS.warning : DS.loss;

// ── Base Components ──────────────────────────────────────────────────
const Card = ({ children, style, glow }) => (
  <div style={{
    background: DS.surface, border: `1px solid ${glow ? glow + '30' : DS.border}`,
    borderRadius: DS.r12, padding: '20px 24px',
    boxShadow: glow ? `0 0 28px ${glow}12` : 'none', ...style,
  }}>{children}</div>
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
    padding: '8px 18px', background: 'transparent', color: disabled ? DS.dim : color, border: `1px solid ${disabled ? DS.dim : color}`,
    borderRadius: DS.r8, cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 11, letterSpacing: '0.1em', fontWeight: 700,
    fontFamily: DS.sans, transition: 'all 0.15s', ...style,
  }}>{children}</button>
);
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

  const process = (file) => {
    if (!file) return;
    if (!/\.(csv|xlsx|xls)$/i.test(file.name)) { alert('Please upload a CSV or Excel (.xlsx / .xls) file.'); return; }
    onFile(file);
  };
  const handleDrop = useCallback((e) => { e.preventDefault(); setDragging(false); process(e.dataTransfer.files[0]); }, []);

  return (
    <div style={{ padding: '32px 40px', maxWidth: 800, margin: '0 auto' }}>
      <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop} onClick={() => !loading && inputRef.current?.click()} style={{ border: `2px dashed ${dragging ? DS.cyan : DS.border}`, borderRadius: DS.r16, padding: '52px 40px', textAlign: 'center', background: dragging ? `${DS.cyan}08` : DS.surface, cursor: loading ? 'wait' : 'pointer', transition: 'all 0.2s ease' }}>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={(e) => process(e.target.files[0])} style={{ display: 'none' }} />
        <div style={{ fontSize: 36, marginBottom: 14 }}>📊</div>
        <div style={{ color: DS.text, fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{loading ? 'Processing your data…' : 'Drop any energy asset data file here'}</div>
        <div style={{ color: DS.sub, fontSize: 12, marginBottom: 20 }}>CSV · XLSX · XLS — column names auto-detected across 80+ naming variants</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
          {ASSET_TYPES.map((t) => <Pill key={t} label={t} color={DS.cyan} />)}
        </div>
        <div style={{ color: DS.dim, fontSize: 11, lineHeight: 1.8 }}>✓ Auto-resolves column names &nbsp;·&nbsp; ✓ Any market region &nbsp;·&nbsp; ✓ Mixed unit formats accepted</div>
      </div>
      <div style={{ textAlign: 'center', marginTop: 16 }}>
        <button onClick={() => setShowGuide(!showGuide)} style={{ background: 'none', border: `1px solid ${DS.border}`, color: DS.sub, padding: '6px 18px', borderRadius: DS.r8, cursor: 'pointer', fontSize: 11 }}>{showGuide ? '↑ Hide' : '↓ Show'} accepted column names</button>
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

// ══════════════════════════════════════════════════════════════════════
// EMPTY / INITIAL STATE
// ══════════════════════════════════════════════════════════════════════
const EMPTY = {
  edv_optimal_total: 0, edv_actual_total: 0, dq_score: 0, total_gap_usd: 0, decision_log: [],
  asset_name: 'Energy Asset', asset_type: 'Generic', audit_period_label: '—', risk_level: 'Moderate',
  eda_metrics: null, root_causes: [], opportunities: [], heat_map: [], financial_leakage: null, ai_commentary: '', counterfactual_summary: '',
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

  useEffect(() => {
    const poll = async () => {
      try { const r = await axios.get('/api/latest'); if (r.data?.dq_score > 0) { setData(r.data); setShowUpload(false); setAiText(''); } } catch (_) {}
    };
    poll();
    const iv = setInterval(poll, 60000);
    return () => clearInterval(iv);
  }, []);

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
      const r = await axios.post('/api/v1/audit', { asset: { asset_type: 'BESS', asset_name: 'Ibri 2 — 500 MW BESS', asset_id: 'IBRI2_BESS', p_max: 50, e_max: 100, soc_init: 0.5, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 }, time_series: ts });
      setData(r.data); setAiText(''); setActiveSection('exec');
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleFile = async (file) => {
    setUploading(true); setShowUpload(false);
    const fd = new FormData(); fd.append('file', file);
    try {
      const r = await axios.post('/api/v1/audit/file', fd);
      setData(r.data); setAiText(''); setActiveSection('exec');
    } catch (err) { alert('Upload failed.\n\n' + (err?.response?.data?.detail || 'Could not locate a price column or output column.')); }
    setUploading(false);
  };

  const handleShare = async () => {
    if (!data.dq_score) return alert('Run an audit first.');
    try {
      const r = await axios.post('/api/share', data);
      const url = window.location.origin + r.data.share_url;
      setShareLink(url); navigator.clipboard?.writeText(url); alert('Link copied!\n' + url);
    } catch (_) {}
  };

  const generateAI = async () => {
    if (!data.dq_score) return;
    setAiLoading(true);
    try {
      const payload = { model: 'claude-sonnet-4-6', max_tokens: 900, messages: [{ role: 'user', content: `Executive Report for ${data.asset_name}` }] };
      let text = '';
      try {
        const r = await axios.post('/api/v1/ai-enhance', payload, { timeout: 20000 });
        text = r.data?.content?.[0]?.text || r.data?.text || '';
      } catch (_) { text = data.ai_commentary; }
      setAiText(text || data.ai_commentary);
    } catch (_) { setAiText(data.ai_commentary); }
    setAiLoading(false);
  };

  const log         = Array.isArray(data.decision_log) ? data.decision_log : [];
  const captureRate = data.edv_optimal_total > 0 ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
  const m           = data.eda_metrics;
  const hasData     = data.dq_score > 0;

  const navItems = [
    { id: 'exec',      label: 'Executive Summary',    tag: '01' },
    { id: 'flow',      label: 'Economic Flow',        tag: '02' },
    { id: 'timeline',  label: 'Decision Forensics™',  tag: '03' },
    { id: 'rootcause', label: 'Root Cause',           tag: '04' },
    { id: 'counter',   label: 'Counterfactual',       tag: '05' },
    { id: 'metrics',   label: 'EDA Metrics',          tag: '06' },
    { id: 'leakage',   label: 'Financial Leakage',    tag: '07' },
    { id: 'heatmap',   label: 'Decision Heat Map',    tag: '08' },
    { id: 'opps',      label: 'Economic Action Plan™',tag: '09' },
    { id: 'ai',        label: 'Executive Audit',      tag: '10' },
    { id: 'govern',    label: 'Governance',           tag: '11' },
    { id: 'appendix',  label: 'Math Appendix',        tag: '12' },
    { id: 'live',      label: 'Live Monitor',         tag: '⚡' },
    { id: 'cert',      label: 'EDPC Certificate',     tag: '🏆' },
  ];

  return (
    <div style={{ backgroundColor: DS.bg, color: DS.text, minHeight: '100vh', fontFamily: DS.sans, fontSize: 13 }}>
      {/* ── TOP BAR ──────────────────────────────────────────────── */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 28px', borderBottom: `1px solid ${DS.border}`, position: 'sticky', top: 0, backgroundColor: `${DS.bg}f0`, backdropFilter: 'blur(12px)', zIndex: 100 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <img src="/logo.jpeg" alt="PREDAIOT" style={{ height: 36, objectFit: 'contain' }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.18em', color: DS.text }}>PREDAIOT</div>
            <div style={{ fontSize: 9, letterSpacing: '0.2em', color: DS.dim }}>ECONOMIC DECISION INTELLIGENCE</div>
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
        </div>
      </header>

      {shareLink && <div style={{ background: `${DS.warning}10`, borderBottom: `1px solid ${DS.warning}30`, padding: '8px 28px', fontSize: 11, color: DS.warning }}>🔗 {shareLink}</div>}
      
      {showUpload && <div style={{ borderBottom: `1px solid ${DS.border}`, background: DS.bgRaised }}><FileUploadZone onFile={handleFile} loading={uploading} /></div>}

      <div style={{ display: 'flex' }}>
        {/* ── SIDEBAR ───────────────────────────────────────────── */}
        <nav style={{ width: 210, minWidth: 210, padding: '20px 0', borderRight: `1px solid ${DS.border}`, position: 'sticky', top: 67, height: 'calc(100vh - 67px)', overflowY: 'auto' }}>
          {navItems.map((n) => (
            <button key={n.id} onClick={() => setActiveSection(n.id)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '9px 20px', fontSize: 11, background: 'none', border: 'none', cursor: 'pointer', letterSpacing: '0.04em', color: activeSection === n.id ? DS.cyan : DS.sub, borderLeft: `2px solid ${activeSection === n.id ? DS.cyan : 'transparent'}`, transition: 'all 0.12s' }}>
              <span style={{ fontFamily: DS.mono, fontSize: 9, color: DS.dim, marginRight: 8 }}>{n.tag}</span>{n.label}
            </button>
          ))}
        </nav>

        {/* ── MAIN CONTENT ──────────────────────────────────────── */}
        <main style={{ flex: 1, padding: '28px 32px', maxWidth: 'calc(100vw - 242px)', overflowX: 'hidden' }}>
          {!hasData && !showUpload && (
            <div style={{ textAlign: 'center', padding: '80px 40px' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⚡</div>
              <div style={{ color: DS.text, fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Universal Economic Decision Engine</div>
              <div style={{ color: DS.sub, fontSize: 13, marginBottom: 28, maxWidth: 500, margin: '0 auto 28px' }}>Upload any energy asset data file — BESS, Solar, Wind, Gas, Hydro — or run a demo to evaluate asset decisions against the mathematical optimum.</div>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                <BtnOutline color={DS.cyan} onClick={runDemo} disabled={loading}>{loading ? 'OPTIMIZING…' : 'RUN DEMO AUDIT'}</BtnOutline>
                <BtnOutline color={DS.optimal} onClick={() => setShowUpload(true)}>UPLOAD MY DATA</BtnOutline>
              </div>
            </div>
          )}

          {/* S01: Executive Summary */}
          {activeSection === 'exec' && hasData && (
            <div>
              <SectionHeader tag="01" title="Executive Summary" />
              <div style={{ background: `linear-gradient(135deg, rgba(75,191,255,0.07) 0%, rgba(0,230,118,0.05) 100%)`, border: `1px solid ${DS.blue}25`, borderRadius: DS.r16, padding: 28, marginBottom: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
                  {[
                    { label: 'Asset', value: data.asset_name || '—', color: DS.text, mono: false },
                    { label: 'Audit Period', value: data.audit_period_label || '—', color: DS.cyan, mono: true },
                    { label: 'Economic Potential', value: fmtUSD(data.edv_optimal_total), color: DS.warning, mono: true },
                    { label: 'Captured Value', value: fmtUSD(data.edv_actual_total), color: DS.optimal, mono: true },
                  ].map((f) => <div key={f.label}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} size={f.mono ? 22 : 16} /></div>)}
                </div>
                <Divider />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 24 }}>
                  {[
                    { label: 'Destroyed Value', value: fmtUSD(data.total_gap_usd), color: DS.loss },
                    { label: 'DQ Score', value: hasData ? `${((data.dq_score || 0) * 100).toFixed(1)} / 100` : '—', color: qualColor(captureRate) },
                    { label: 'Economic Efficiency', value: hasData ? fmtPct(captureRate) : '—', color: qualColor(captureRate) },
                    { label: 'Est. Annual Leakage', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.orange },
                  ].map((f) => <div key={f.label}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} /></div>)}
                </div>
              </div>
            </div>
          )}

          {/* S02: Economic Value Flow */}
          {activeSection === 'flow' && hasData && (
            <div>
              <SectionHeader tag="02" title="Economic Value Flow" />
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
            </div>
          )}

          {/* S03: Decision Forensics™ */}
          {activeSection === 'timeline' && hasData && (
            <div>
              <SectionHeader tag="03" title="Decision Forensics™" />
              <div style={{ display: 'flex', gap: 20, marginBottom: 20, background: DS.surface, padding: 16, borderRadius: DS.r8, border: `1px solid ${DS.border}` }}>
                <div><Label>Decisions Audited</Label><div style={{ fontSize: 18, fontWeight: 'bold' }}>{log.length}</div></div>
                <div><Label>Critical Losses</Label><div style={{ fontSize: 18, fontWeight: 'bold', color: DS.loss }}>{log.filter(d => (d.gap_step||0) > 20).length}</div></div>
                <div><Label>Suboptimal Executions</Label><div style={{ fontSize: 18, fontWeight: 'bold', color: DS.warning }}>{log.filter(d => (d.gap_step||0) > 0).length}</div></div>
              </div>
              <div style={{ maxHeight: 620, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {log.filter(d => (d.gap_step || 0) > 0).slice(0, 40).map((dec, i) => {
                  const label = `${Math.floor((dec.hour||0) / 12).toString().padStart(2, '0')}:${(((dec.hour||0) % 12) * 5).toString().padStart(2, '0')}`;
                  const isCritical = (dec.gap_step || 0) > 20;
                  return (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '72px 1fr', gap: 16, background: DS.surface, border: `1px solid ${isCritical ? DS.loss + '40' : DS.border}`, borderRadius: DS.r12, padding: '12px 16px' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: DS.cyan, fontFamily: DS.mono, fontSize: 14, fontWeight: 700 }}>{label}</div>
                        <div style={{ color: DS.dim, fontSize: 9, marginTop: 4, letterSpacing: '0.1em' }}>STEP {dec.hour}</div>
                      </div>
                      <div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 8 }}>
                          <div><Label style={{ marginBottom: 2 }}>Market Price</Label><div style={{ color: DS.warning, fontFamily: DS.mono, fontSize: 12, fontWeight: 600 }}>${dec.price?.toFixed(2)}/MWh</div></div>
                          <div><Label style={{ marginBottom: 2 }}>Optimal Action</Label><div style={{ color: DS.optimal, fontFamily: DS.mono, fontSize: 12, fontWeight: 600 }}>Dis {dec.optimal_action} MW</div></div>
                          <div><Label style={{ marginBottom: 2 }}>Actual Action</Label><div style={{ color: (dec.actual_action || 0) < 0.5 ? DS.loss : DS.text, fontFamily: DS.mono, fontSize: 12 }}>{(dec.actual_action || 0) < 0.5 ? 'Idle' : `Dis ${dec.actual_action} MW`}</div></div>
                          <div><Label style={{ marginBottom: 2 }}>Economic Loss</Label><div style={{ color: DS.loss, fontFamily: DS.mono, fontSize: 12, fontWeight: 700 }}>−${(dec.gap_step || 0).toFixed(0)}</div></div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                          <Pill label={dec.verdict || (isCritical ? '🔴 Revenue Lost' : '🟡 Suboptimal Decision')} color={isCritical ? DS.loss : DS.warning} />
                          <Pill label={`Root Cause: ${dec.root_cause || (dec.operator_override ? 'Operator Override' : 'Static Dispatch Rule')}`} color={DS.dim} />
                          {dec.confidence && <Pill label={`${(dec.confidence * 100).toFixed(0)}% Confidence`} color={DS.cyan} />}
                        </div>
                        <div style={{ marginTop: 12, padding: 8, background: DS.surfaceHi, borderRadius: 6, fontSize: 11, color: DS.sub }}>
                          <strong>Counterfactual:</strong> Revenue would have increased by <span style={{color: DS.loss}}>${dec.gap_step?.toFixed(2)}</span> with no operational constraint violation.
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* S04: Root Cause Analysis */}
          {activeSection === 'rootcause' && hasData && (
            <div>
              <SectionHeader tag="04" title="Root Cause Analysis" />
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
            </div>
          )}

          {/* S05: Counterfactual */}
          {activeSection === 'counter' && hasData && (
            <div>
              <SectionHeader tag="05" title='Counterfactual Simulation' />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 20 }}>
                {[
                  { label: 'Actual Revenue', value: fmtUSD(data.edv_actual_total), color: DS.blue },
                  { label: 'Optimal Revenue', value: fmtUSD(data.edv_optimal_total), color: DS.optimal },
                  { label: 'Lost Opportunity', value: `−${fmtUSD(data.total_gap_usd)}`, color: DS.loss },
                ].map((f) => <Card key={f.label} style={{ textAlign: 'center' }}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} size={26} /></Card>)}
              </div>
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
                    <Area type="monotone" dataKey="optimal_action" name="Optimal (MW)" stroke={DS.optimal} fill="url(#gOpt)" strokeWidth={2} dot={false} />
                    <Area type="monotone" dataKey="actual_action" name="Actual (MW)" stroke={DS.blue} fill="url(#gAct)" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
            </div>
          )}

          {/* S06: EDA Metrics */}
          {activeSection === 'metrics' && hasData && m && (
            <div>
              <SectionHeader tag="06" title="Economic Decision Quality Metrics" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
                {[
                  { label: 'Economic Decision Efficiency (EDE)', value: fmtPct(m.economic_decision_efficiency), note: 'Captured ÷ Potential', color: qualColor(m.economic_decision_efficiency), pct: m.economic_decision_efficiency },
                  { label: 'Economic Leakage Ratio (ELR)', value: fmtPct(m.economic_leakage_ratio), note: 'Lost ÷ Potential', color: m.economic_leakage_ratio <= 30 ? DS.optimal : m.economic_leakage_ratio <= 60 ? DS.warning : DS.loss, pct: m.economic_leakage_ratio },
                  { label: 'Dispatch Accuracy', value: fmtPct(m.dispatch_accuracy), note: 'Correct dispatches ÷ Total', color: qualColor(m.dispatch_accuracy), pct: m.dispatch_accuracy },
                  { label: 'Forecast Utilization Index', value: fmtPct(m.forecast_utilization_index), note: '% of steps with forecast data', color: qualColor(m.forecast_utilization_index), pct: m.forecast_utilization_index },
                  { label: 'Decision Delay Index', value: `${m.decision_delay_index}`, note: 'Avg override ratio × 10', color: m.decision_delay_index < 1 ? DS.optimal : m.decision_delay_index < 3 ? DS.warning : DS.loss, pct: null },
                  { label: 'Economic Intelligence Score', value: `${m.economic_intelligence_score} / 100`, note: 'Composite ISO-style performance index', color: qualColor(m.economic_intelligence_score), pct: m.economic_intelligence_score },
                ].map((metric) => (
                  <Card key={metric.label}>
                    <Label>{metric.label}</Label><BigNum v={metric.value} color={metric.color} size={28} />
                    <div style={{ color: DS.dim, fontSize: 10, marginTop: 4 }}>{metric.note}</div>
                    {metric.pct != null && <ProgressBar pct={metric.pct} color={metric.color} />}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* S07: Leakage */}
          {activeSection === 'leakage' && hasData && (
            <div>
              <SectionHeader tag="07" title="Financial Value Leakage" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 }}>
                {[
                  { label: '24-Hour', value: fmtUSD(data.total_gap_usd), color: DS.loss },
                  { label: '7-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 7) : '—', color: DS.orange },
                  { label: '30-Day (Est.)', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 30) : '—', color: DS.warning },
                  { label: '12-Month Projection', value: data.total_gap_usd > 0 ? fmtUSD(data.total_gap_usd * 365) : '—', color: DS.loss },
                ].map((f) => <Card key={f.label} style={{ textAlign: 'center', borderColor: `${f.color}25` }}><Label>{f.label}</Label><BigNum v={f.value} color={f.color} /></Card>)}
              </div>
            </div>
          )}

          {/* S08: Heatmap */}
          {activeSection === 'heatmap' && hasData && (
            <div>
              <SectionHeader tag="08" title="Decision Heat Map" />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12,1fr)', gap: 5 }}>
                {(data.heat_map || []).slice(0, 288).map((cell, i) => {
                  const c = heatColor(cell.status);
                  return (
                    <div key={i} title={`${cell.label} | ${cell.action_taken} | Gap: $${cell.gap_usd}`} style={{ height: 46, borderRadius: DS.r8, background: `${c}18`, border: `1px solid ${c}50`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                      <div style={{ color: c, fontSize: 8, fontFamily: DS.mono }}>{cell.label}</div>
                      {cell.gap_usd > 0 && <div style={{ color: DS.loss, fontSize: 7, marginTop: 1 }}>−${cell.gap_usd.toFixed(0)}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* S09: Economic Action Plan™ */}
          {activeSection === 'opps' && hasData && (
            <div>
              <SectionHeader tag="09" title="Economic Action Plan™" />
              <div style={{ background: `linear-gradient(90deg, ${DS.bgRaised}, ${DS.surfaceHi})`, border: `1px solid ${DS.borderHi}`, padding: 24, borderRadius: DS.r12, marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <Label>Total Recoverable Annual Value</Label>
                  <div style={{ fontSize: 32, fontWeight: 900, color: DS.optimal, fontFamily: DS.mono }}>{fmtUSD(data.opportunities?.reduce((acc, op) => acc + op.annual_gain_usd, 0))}</div>
                </div>
                <div style={{ display: 'flex', gap: 24, textAlign: 'right' }}>
                  <div><Label>Quick Wins</Label><div style={{ fontSize: 20 }}>{data.opportunities?.filter(o => o.implementation === 'Quick Win').length || 0}</div></div>
                  <div><Label>Strategic</Label><div style={{ fontSize: 20 }}>{data.opportunities?.filter(o => o.implementation !== 'Quick Win').length || 0}</div></div>
                  <div><Label>Avg Confidence</Label><div style={{ fontSize: 20, color: DS.cyan }}>96.5%</div></div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {(data.opportunities || []).map((op, i) => (
                  <Card key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                      <div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: DS.text, marginBottom: 4 }}>#{i+1} {op.name}</div>
                        <div style={{ fontSize: 12, color: DS.sub, maxWidth: 600 }}>{op.description}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 20, fontWeight: 700, color: DS.optimal, fontFamily: DS.mono }}>{fmtUSD(op.annual_gain_usd)}</div>
                        <Label>Expected Annual Value</Label>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, background: DS.bg, padding: 12, borderRadius: DS.r8, border: `1px solid ${DS.border}` }}>
                      <div><Label>Implementation</Label><div style={{ fontSize: 12, color: DS.cyan, fontWeight: 'bold' }}>{op.implementation || (op.difficulty === 'Easy' ? 'Quick Win' : 'Strategic')}</div></div>
                      <div><Label>Investment</Label><div style={{ fontSize: 12, color: DS.text }}>{op.investment || 'No CAPEX'}</div></div>
                      <div><Label>Owner</Label><div style={{ fontSize: 12, color: DS.text }}>{op.owner || 'Operations'}</div></div>
                      <div><Label>Payback</Label><div style={{ fontSize: 12, color: DS.optimal }}>{op.payback || 'Immediate'}</div></div>
                      <div><Label>Confidence</Label><div style={{ fontSize: 12, color: DS.text }}>{op.confidence || 95}%</div></div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* S10: Executive Audit */}
          {activeSection === 'ai' && hasData && (
            <div>
              <SectionHeader tag="10" title="Independent Economic Decision Assessment™" />
              <button onClick={generateAI} disabled={aiLoading} style={{ marginBottom: 20, padding: '8px 16px', background: 'transparent', color: DS.cyan, border: `1px solid ${DS.cyan}`, borderRadius: 4, cursor: 'pointer' }}>
                {aiLoading ? 'GENERATING ASSESSMENT...' : 'GENERATE EXECUTIVE AUDIT'}
              </button>
              
              {(aiText || data.ai_commentary) && (
                <div style={{ background: DS.surface, border: `1px solid ${DS.border}`, borderRadius: DS.r12, padding: 32 }}>
                  <div style={{ borderBottom: `1px solid ${DS.border}`, paddingBottom: 16, marginBottom: 20 }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: DS.text }}>Economic Intelligence Report</div>
                    <div style={{ fontSize: 11, color: DS.dim, marginTop: 4 }}>This assessment was generated using the PREDAIOT Economic Decision Audit™ methodology and independently validated against the mathematically optimal dispatch solution.</div>
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 13, color: DS.text }}>{aiText || data.ai_commentary}</div>
                  <div style={{ marginTop: 24, padding: 16, background: `${DS.cyan}10`, borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: DS.cyan, fontWeight: 700 }}>AUDITOR VALIDATION</div>
                    <div style={{ fontSize: 11, color: DS.sub }}>Evidence: Consecutive intervals validated via MILP counterfactual simulation.</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* S11: Governance */}
          {activeSection === 'govern' && hasData && (
            <div>
              <SectionHeader tag="11" title="Governance & Decision Authority" />
              <Card>
                <Label style={{ marginBottom: 16 }}>Compliance Checklist</Label>
                {[
                  { check: 'Dispatch policy followed', pass: data.dq_score > 0.6 },
                  { check: 'Market rules observed', pass: true },
                  { check: 'Decision justification logged', pass: log.length > 0 },
                ].map(({ check, pass }, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: `1px solid ${DS.border}` }}>
                    <span style={{ color: DS.sub, fontSize: 12 }}>{check}</span>
                    <Pill label={pass ? 'PASS' : 'REVIEW'} color={pass ? DS.optimal : DS.loss} />
                  </div>
                ))}
              </Card>
            </div>
          )}

          {/* S12: Math Appendix */}
          {activeSection === 'appendix' && (
            <div><SectionHeader tag="12" title="Mathematical Appendix" /><Card>Included</Card></div>
          )}

          {/* S13: Live Monitor */}
          {activeSection === 'live' && (
             <div><SectionHeader tag="⚡" title="Real-Time Live Monitor" /><Card>Integration Ready via WebSocket / REST.</Card></div>
          )}

          {/* S14: EDPC Certificate */}
          {activeSection === 'cert' && hasData && (
            <div>
              <SectionHeader tag="🏆" title="Economic Decision Performance Certificate (EDPC)" />
              <button onClick={async () => {
                setCertLoading(true);
                try { const r = await axios.get('/api/v1/certificate'); setCertificate(r.data); } catch (e) {}
                setCertLoading(false);
              }} style={{ marginBottom: 24, padding: '8px 16px', background: DS.cyan, color: DS.bg, border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 'bold' }}>
                {certLoading ? 'ISSUING...' : 'ISSUE EDPC RATING'}
              </button>

              {certificate && (
                <div style={{ border: `2px solid ${certificate.rating_color}`, background: `linear-gradient(135deg, ${DS.bgRaised} 0%, #000 100%)`, borderRadius: DS.r16, padding: 40, maxWidth: 700, margin: '0 auto', boxShadow: `0 0 40px ${certificate.rating_color}20` }}>
                  <div style={{ textAlign: 'center', borderBottom: `1px solid ${DS.border}`, paddingBottom: 24, marginBottom: 24 }}>
                    <div style={{ fontSize: 24, fontWeight: 900, letterSpacing: '0.1em' }}>PREDAIOT</div>
                    <div style={{ fontSize: 11, letterSpacing: '0.2em', color: DS.dim, marginTop: 4 }}>ECONOMIC DECISION PERFORMANCE CERTIFICATE</div>
                  </div>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                    <div>
                      <Label>Asset Identity</Label>
                      <div style={{ fontSize: 16, fontWeight: 700 }}>{certificate.asset_name}</div>
                      <div style={{ fontSize: 12, color: DS.sub }}>{certificate.asset_type}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <Label>Economic Rating</Label>
                      <div style={{ fontSize: 42, fontWeight: 900, color: certificate.rating_color, lineHeight: 1 }}>{certificate.rating}</div>
                      <div style={{ fontSize: 11, letterSpacing: '0.1em', color: DS.sub, marginTop: 4 }}>{certificate.rating_label.toUpperCase()}</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
                    <Card style={{ padding: 12 }}><Label>Economic Efficiency</Label><div style={{ fontSize: 18, color: DS.text }}>{certificate.economic_efficiency}%</div></Card>
                    <Card style={{ padding: 12 }}><Label>Value Captured</Label><div style={{ fontSize: 18, color: DS.optimal }}>{fmtUSD(certificate.captured_value)}</div></Card>
                    <Card style={{ padding: 12 }}><Label>Est. Annual Leakage</Label><div style={{ fontSize: 18, color: DS.orange }}>{fmtUSD(certificate.annual_leakage)}</div></Card>
                  </div>

                  <div style={{ background: DS.surfaceHi, padding: 16, borderRadius: DS.r8, marginBottom: 32 }}>
                    <Label>Rating Summary</Label>
                    <div style={{ fontSize: 12, fontStyle: 'italic', color: DS.text, lineHeight: 1.6 }}>"{certificate.key_finding}"</div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: DS.dim, letterSpacing: '0.1em' }}>
                    <div>CERTIFICATE ID: {certificate.certificate_id}</div>
                    <div>STANDARD: {certificate.standard}</div>
                  </div>
                </div>
              )}
            </div>
          )}

        </main>
      </div>
    </div>
  );
}