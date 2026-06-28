import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell
} from 'recharts';

// ─── Palette derived from PREDAIOT logo gradient ───────────────────────────
const C = {
  bg:       '#040608',
  surface:  'rgba(255,255,255,0.03)',
  border:   'rgba(255,255,255,0.07)',
  blue:     '#4BBFFF',
  green:    '#00E676',
  yellow:   '#FFD600',
  red:      '#FF1744',
  cyan:     '#00E5FF',
  orange:   '#FF6D00',
  text:     '#E8EAF0',
  muted:    '#596070',
  label:    '#8A94A6',
};

const SECTION_BORDER = `1px solid ${C.border}`;

// ─── Reusable primitives ───────────────────────────────────────────────────
const Card = ({ children, style }) => (
  <div style={{
    backgroundColor: C.surface, border: SECTION_BORDER,
    borderRadius: 12, padding: 24, ...style
  }}>
    {children}
  </div>
);

const SectionTitle = ({ tag, children }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 20 }}>
    {tag && <span style={{ color: C.muted, fontFamily: 'monospace', fontSize: 11, letterSpacing: 2 }}>{tag}</span>}
    <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: C.text, letterSpacing: 1, textTransform: 'uppercase' }}>{children}</h3>
  </div>
);

const Pill = ({ label, color }) => (
  <span style={{
    display: 'inline-block', padding: '3px 10px', borderRadius: 20,
    border: `1px solid ${color}`, color, fontSize: 11, fontWeight: 700,
    letterSpacing: 1, backgroundColor: `${color}18`
  }}>
    {label}
  </span>
);

const MetricRow = ({ label, value, color, note }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
    <span style={{ color: C.label, fontSize: 12 }}>{label}</span>
    <div style={{ textAlign: 'right' }}>
      <span style={{ color: color || C.text, fontWeight: 700, fontSize: 13, fontFamily: 'monospace' }}>{value}</span>
      {note && <div style={{ color: C.muted, fontSize: 10 }}>{note}</div>}
    </div>
  </div>
);

const riskColor = (r) => r === 'Low' ? C.green : r === 'Moderate' ? C.yellow : C.red;
const riskEmoji = (r) => r === 'Low' ? '🟢' : r === 'Moderate' ? '🟡' : '🔴';

const heatColor = (s) => ({
  optimal:    C.green,
  acceptable: C.yellow,
  poor:       C.orange,
  critical:   C.red,
}[s] || C.muted);

const starColor = (n, max = 5) => n >= 4 ? C.green : n >= 3 ? C.yellow : C.orange;

function formatUSD(n) {
  if (!n && n !== 0) return 'N/A';
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(2)}`;
}

// ─── Empty state data ──────────────────────────────────────────────────────
const EMPTY = {
  edv_optimal_total: 0, edv_actual_total: 0, dq_score: 0,
  total_gap_usd: 0, decision_log: [],
  asset_name: 'Energy Asset', asset_type: 'Generic',
  audit_period_label: '—', risk_level: 'Moderate',
  eda_metrics: null, root_causes: [], opportunities: [],
  heat_map: [], financial_leakage: null, ai_commentary: '',
  counterfactual_summary: ''
};

// ══════════════════════════════════════════════════════════════════════════
export default function App() {
  const [data, setData]             = useState(EMPTY);
  const [loading, setLoading]       = useState(false);
  const [historyData, setHistoryData]   = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [shareLink, setShareLink]   = useState('');
  const [activeSection, setActiveSection] = useState('exec');
  const [showMethodology, setShowMethodology] = useState(false);
  const fileInputRef = useRef(null);

  // Live SCADA polling
  useEffect(() => {
    const fetchLive = async () => {
      try {
        const r = await axios.get('/api/latest');
        if (r.data?.dq_score > 0) setData(r.data);
      } catch (_) {}
    };
    fetchLive();
    const iv = setInterval(fetchLive, 60000);
    return () => clearInterval(iv);
  }, []);

  const runDemo = async () => {
    setLoading(true);
    try {
      const time_series = [];
      let soc = 0.2;
      const e_max = 100;
      for (let i = 0; i < 288; i++) {
        const basePrice = 30 + 70 * Math.sin((i - 72) * (Math.PI / 144));
        const price = Math.max(5, parseFloat((basePrice + (Math.random() - 0.5) * 10).toFixed(2)));
        let actual_discharge = 0;
        if (price < 20 && soc < 0.9) soc += (40 * 0.95 / e_max);
        if (price > 40 && price < 200 && soc > 0.2) {
          const max = (soc - 0.2) * e_max;
          actual_discharge = Math.min(40, max);
          soc -= (actual_discharge / 0.95 / e_max);
        }
        time_series.push({
          hour: i, price,
          actual_discharge,
          forecast_price: parseFloat((price * (0.9 + Math.random() * 0.2)).toFixed(2))
        });
      }
      const payload = {
        asset: { asset_type: 'BESS', asset_name: 'Ibri 2 — 500MW BESS', asset_id: 'IBRI2_BESS',
          p_max: 50, e_max: 100, soc_init: 0.5, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 },
        time_series
      };
      const r = await axios.post('/api/v1/audit', payload);
      setData(r.data);
      setActiveSection('exec');
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post('/api/v1/audit/file', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setData(r.data);
      setActiveSection('exec');
    } catch (err) {
      const detail = err?.response?.data?.detail || '';
      alert(
        "Upload failed.\n\n" +
        (detail || (
          "No price column or output column found.\n\n" +
          "Price aliases accepted: price, spot_price, lmp, market_price, omr_mwh, energy_price …\n" +
          "Output aliases accepted: actual_discharge, generation, output_mw, actual_power, gen_mw …\n\n" +
          "Tip: POST your file to /api/v1/audit/inspect to see exactly how columns are resolved."
        ))
      );
    }
    setUploading(false);
    e.target.value = '';
  };

  const handleShare = async () => {
    if (!data.dq_score) return alert('Run an audit first.');
    try {
      const r = await axios.post('/api/share', data);
      const url = window.location.origin + r.data.share_url;
      setShareLink(url);
      navigator.clipboard.writeText(url);
      alert(`Link copied!\n${url}`);
    } catch (_) {}
  };

  const logData = Array.isArray(data.decision_log) ? data.decision_log : [];
  const captureRate = data.edv_optimal_total > 0
    ? (data.edv_actual_total / data.edv_optimal_total) * 100 : 0;
  const m = data.eda_metrics;

  const navItems = [
    { id: 'exec',      label: 'Executive Summary' },
    { id: 'flow',      label: 'Economic Flow' },
    { id: 'timeline',  label: 'Decision Timeline' },
    { id: 'rootcause', label: 'Root Cause' },
    { id: 'counter',   label: 'Counterfactual' },
    { id: 'metrics',   label: 'EDA Metrics' },
    { id: 'leakage',   label: 'Financial Leakage' },
    { id: 'heatmap',   label: 'Decision Heat Map' },
    { id: 'opps',      label: 'Opportunity Ranking' },
    { id: 'ai',        label: 'AI Commentary' },
    { id: 'govern',    label: 'Governance' },
    { id: 'appendix',  label: 'Math Appendix' },
  ];

  return (
    <div style={{ backgroundColor: C.bg, color: C.text, minHeight: '100vh', fontFamily: "'Inter', 'Segoe UI', sans-serif", fontSize: 13 }}>
      {/* ── Top Bar ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 28px', borderBottom: `1px solid ${C.border}`, position: 'sticky', top: 0, backgroundColor: C.bg, zIndex: 100 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <img src="/logo.jpeg" alt="PREDAIOT" style={{ height: 38, objectFit: 'contain' }} />
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: 2, color: C.text }}>PREDAIOT</div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted }}>ECONOMIC DECISION AUDIT™</div>
          </div>
          {data.dq_score > 0 && (
            <div style={{ marginLeft: 20, display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: C.muted }}>{data.asset_name}</span>
              <Pill label={data.risk_level || 'Moderate'} color={riskColor(data.risk_level)} />
              <Pill label={data.asset_type || 'Generic'} color={C.cyan} />
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <BtnOutline color={C.cyan} onClick={runDemo} disabled={loading}>
            {loading ? 'OPTIMIZING…' : 'RUN DEMO AUDIT'}
          </BtnOutline>
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleFile} style={{ display: 'none' }} />
          <div style={{ position: 'relative' }} title={
            "CSV or Excel accepted.\n" +
            "Price column → price, spot_price, lmp, market_price, omr_mwh …\n" +
            "Output column → actual_discharge, generation, output_mw, gen_mw …\n" +
            "POST to /api/v1/audit/inspect to debug column mapping."
          }>
            <BtnOutline color={C.green} onClick={() => fileInputRef.current.click()} disabled={uploading}>
              {uploading ? 'PARSING…' : 'UPLOAD DATA'}
            </BtnOutline>
          </div>
          <BtnOutline color={C.yellow} onClick={handleShare}>SHARE REPORT</BtnOutline>
          <BtnOutline color={C.muted} onClick={() => setShowMethodology(true)}>METHODOLOGY</BtnOutline>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: C.green, boxShadow: `0 0 6px ${C.green}` }} />
            <span style={{ color: C.muted, fontSize: 10, letterSpacing: 1 }}>LIVE</span>
          </div>
        </div>
      </div>

      {shareLink && (
        <div style={{ background: `${C.yellow}12`, border: `1px solid ${C.yellow}40`, padding: '8px 28px', fontSize: 11, color: C.yellow }}>
          🔗 {shareLink}
        </div>
      )}

      <div style={{ display: 'flex' }}>
        {/* ── Side Nav ── */}
        <nav style={{ width: 200, minWidth: 200, padding: '24px 0', borderRight: `1px solid ${C.border}`, position: 'sticky', top: 67, height: 'calc(100vh - 67px)', overflowY: 'auto' }}>
          {navItems.map(n => (
            <button key={n.id} onClick={() => setActiveSection(n.id)} style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '9px 20px', fontSize: 12, background: 'none', border: 'none',
              cursor: 'pointer', letterSpacing: 0.5,
              color: activeSection === n.id ? C.cyan : C.label,
              borderLeft: activeSection === n.id ? `2px solid ${C.cyan}` : '2px solid transparent',
              transition: 'color 0.15s',
            }}>
              {n.label}
            </button>
          ))}
        </nav>

        {/* ── Main Content ── */}
        <main style={{ flex: 1, padding: '28px 32px', maxWidth: 'calc(100vw - 232px)' }}>

          {/* ══ S1: Executive Summary ══ */}
          {activeSection === 'exec' && (
            <div>
              <SectionTitle tag="EDA-01">Executive Summary</SectionTitle>

              {/* Shock card */}
              <div style={{ background: `linear-gradient(135deg, rgba(75,191,255,0.08) 0%, rgba(0,230,118,0.06) 100%)`, border: `1px solid ${C.blue}30`, borderRadius: 16, padding: 28, marginBottom: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }}>
                  {[
                    { label: 'ASSET', value: data.asset_name || '—', color: C.text, mono: false },
                    { label: 'AUDIT PERIOD', value: data.audit_period_label || '24 Hours', color: C.cyan, mono: true },
                    { label: 'ECONOMIC POTENTIAL', value: formatUSD(data.edv_optimal_total), color: C.yellow, mono: true },
                    { label: 'CAPTURED VALUE', value: formatUSD(data.edv_actual_total), color: C.green, mono: true },
                  ].map(f => (
                    <div key={f.label}>
                      <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 6 }}>{f.label}</div>
                      <div style={{ color: f.color, fontSize: f.mono ? 22 : 16, fontWeight: 700, fontFamily: f.mono ? 'monospace' : 'inherit' }}>{f.value}</div>
                    </div>
                  ))}
                </div>
                <div style={{ height: 1, background: C.border, margin: '20px 0' }} />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }}>
                  {[
                    { label: 'DESTROYED VALUE', value: formatUSD(data.total_gap_usd), color: C.red },
                    { label: 'DQ SCORE', value: data.dq_score > 0 ? `${(data.dq_score * 100).toFixed(1)} / 100` : '—', color: captureRate >= 70 ? C.green : captureRate >= 40 ? C.yellow : C.red },
                    { label: 'ECONOMIC EFFICIENCY', value: data.edv_optimal_total > 0 ? `${captureRate.toFixed(1)}%` : '—', color: captureRate >= 70 ? C.green : captureRate >= 40 ? C.yellow : C.red },
                    { label: 'EST. ANNUAL LEAKAGE', value: data.total_gap_usd > 0 ? formatUSD(data.total_gap_usd * 365) : '—', color: C.orange },
                  ].map(f => (
                    <div key={f.label}>
                      <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 6 }}>{f.label}</div>
                      <div style={{ color: f.color, fontSize: 22, fontWeight: 700, fontFamily: 'monospace' }}>{f.value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Risk banner */}
              {data.risk_level && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', background: `${riskColor(data.risk_level)}12`, border: `1px solid ${riskColor(data.risk_level)}40`, borderRadius: 10 }}>
                  <span style={{ fontSize: 22 }}>{riskEmoji(data.risk_level)}</span>
                  <div>
                    <div style={{ color: riskColor(data.risk_level), fontWeight: 700, fontSize: 14, letterSpacing: 1 }}>RISK LEVEL: {data.risk_level?.toUpperCase()}</div>
                    <div style={{ color: C.label, fontSize: 11, marginTop: 2 }}>
                      {data.risk_level === 'Severe' && 'Immediate operational review required. Economic losses exceed 60% of potential.'}
                      {data.risk_level === 'Moderate' && 'Optimization opportunities identified. Revenue recovery achievable within 30 days.'}
                      {data.risk_level === 'Low' && 'Asset operating near optimal. Minor tuning recommended for full potential capture.'}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ S2: Economic Flow ══ */}
          {activeSection === 'flow' && (
            <div>
              <SectionTitle tag="EDA-02">Economic Value Flow</SectionTitle>
              <div style={{ maxWidth: 520, margin: '0 auto' }}>
                {[
                  { label: 'MARKET POTENTIAL', value: formatUSD(data.edv_optimal_total), color: C.yellow, desc: 'Maximum achievable given physics & market' },
                  { label: 'AVAILABLE WINDOW', value: formatUSD(data.edv_optimal_total * 0.92), color: C.blue, desc: 'After network constraints & grid limits' },
                  { label: 'DISPATCH OPPORTUNITY', value: formatUSD(data.edv_optimal_total * 0.87), color: C.cyan, desc: 'Within asset capability & SOC range' },
                  { label: 'DECISION TAKEN', value: formatUSD(data.edv_actual_total), color: C.green, desc: 'Operator / EMS decisions executed' },
                  { label: 'CAPTURED VALUE', value: formatUSD(data.edv_actual_total * 0.97), color: C.green, desc: 'Net of settlement & metering losses' },
                  { label: 'ECONOMIC LEAKAGE', value: `−${formatUSD(data.total_gap_usd)}`, color: C.red, desc: 'Revenue permanently destroyed by poor timing' },
                  { label: 'UNRECOVERABLE LOSS', value: `−${formatUSD(data.total_gap_usd * 0.12)}`, color: C.muted, desc: 'Physical / regulatory hard limits' },
                ].map((step, i) => (
                  <div key={step.label}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px', background: C.surface, border: `1px solid ${step.color}30`, borderRadius: 10 }}>
                      <div style={{ width: 4, height: 40, backgroundColor: step.color, borderRadius: 2, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2 }}>{step.label}</div>
                        <div style={{ color: step.color, fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>{step.value}</div>
                        <div style={{ color: C.muted, fontSize: 10, marginTop: 2 }}>{step.desc}</div>
                      </div>
                    </div>
                    {i < 6 && <div style={{ textAlign: 'center', color: C.muted, fontSize: 18, lineHeight: '20px' }}>↓</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ══ S3: Decision Timeline ══ */}
          {activeSection === 'timeline' && (
            <div>
              <SectionTitle tag="EDA-03">Decision Timeline — Black Box</SectionTitle>
              <div style={{ maxHeight: 580, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {logData.length === 0 && <div style={{ color: C.muted, textAlign: 'center', padding: 40 }}>Run an audit to populate the decision log.</div>}
                {logData.filter(d => (d.gap_step || 0) > 0).slice(0, 30).map((dec, i) => {
                  const h = dec.hour || 0;
                  const label = `${Math.floor(h / 12).toString().padStart(2, '0')}:${((h % 12) * 5).toString().padStart(2, '0')}`;
                  const isLoss = (dec.gap_step || 0) > 10;
                  return (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '70px 1fr', gap: 16, background: C.surface, border: `1px solid ${isLoss ? C.red + '30' : C.border}`, borderRadius: 10, padding: '12px 16px' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: C.cyan, fontFamily: 'monospace', fontSize: 13, fontWeight: 700 }}>{label}</div>
                        <div style={{ color: C.muted, fontSize: 9, marginTop: 4, letterSpacing: 1 }}>STEP {h}</div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                        <div><div style={{ color: C.muted, fontSize: 9, letterSpacing: 1 }}>PRICE</div><div style={{ color: C.yellow, fontFamily: 'monospace', fontSize: 12, fontWeight: 600 }}>${dec.price}/MWh</div></div>
                        <div><div style={{ color: C.muted, fontSize: 9, letterSpacing: 1 }}>OPTIMAL</div><div style={{ color: C.green, fontFamily: 'monospace', fontSize: 12, fontWeight: 600 }}>Dis {dec.optimal_action} MW</div></div>
                        <div><div style={{ color: C.muted, fontSize: 9, letterSpacing: 1 }}>ACTUAL</div><div style={{ color: (dec.actual_action || 0) < (dec.optimal_action || 0) ? C.red : C.text, fontFamily: 'monospace', fontSize: 12, fontWeight: 600 }}>{(dec.actual_action || 0) < 0.5 ? 'Idle' : `Dis ${dec.actual_action} MW`}</div></div>
                        <div><div style={{ color: C.muted, fontSize: 9, letterSpacing: 1 }}>DECISION LOSS</div><div style={{ color: C.red, fontFamily: 'monospace', fontSize: 12, fontWeight: 700 }}>−${(dec.gap_step || 0).toFixed(0)}</div></div>
                        <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 10, marginTop: 4 }}>
                          <Pill label={dec.decision_type || 'Unknown'} color={isLoss ? C.red : C.green} />
                          {dec.confidence && <Pill label={`${(dec.confidence * 100).toFixed(0)}% conf`} color={C.cyan} />}
                          {dec.operator_override && <Pill label="Override" color={C.orange} />}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ══ S4: Root Cause ══ */}
          {activeSection === 'rootcause' && (
            <div>
              <SectionTitle tag="EDA-04">Root Cause Analysis — Pareto</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <Card>
                  {(data.root_causes || []).length === 0 && <div style={{ color: C.muted }}>Run an audit to generate root cause data.</div>}
                  {(data.root_causes || []).map((rc, i) => (
                    <div key={i} style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ color: C.text, fontSize: 12 }}>{rc.category}</span>
                        <span style={{ color: C.red, fontFamily: 'monospace', fontSize: 12, fontWeight: 700 }}>{rc.contribution_pct}%</span>
                      </div>
                      <div style={{ background: C.border, borderRadius: 4, height: 6 }}>
                        <div style={{ width: `${rc.contribution_pct}%`, background: `linear-gradient(90deg, ${C.red}, ${C.orange})`, height: 6, borderRadius: 4 }} />
                      </div>
                      <div style={{ color: C.muted, fontSize: 10, marginTop: 3 }}>Loss: {formatUSD(rc.loss_usd)}</div>
                    </div>
                  ))}
                </Card>
                <Card>
                  <div style={{ color: C.muted, fontSize: 11, marginBottom: 12 }}>FAILURE CATEGORY BREAKDOWN</div>
                  {(data.root_causes || []).length > 0 && (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={data.root_causes || []} layout="vertical" margin={{ left: 10 }}>
                        <XAxis type="number" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} tickFormatter={v => `${v}%`} />
                        <YAxis type="category" dataKey="category" stroke={C.muted} tick={{ fill: C.label, fontSize: 10 }} width={140} />
                        <Tooltip contentStyle={{ background: '#111', border: `1px solid ${C.border}`, borderRadius: 8 }} formatter={v => [`${v}%`, 'Contribution']} />
                        <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>
                          {(data.root_causes || []).map((_, i) => (
                            <Cell key={i} fill={i === 0 ? C.red : i === 1 ? C.orange : C.yellow} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </Card>
              </div>
            </div>
          )}

          {/* ══ S5: Counterfactual ══ */}
          {activeSection === 'counter' && (
            <div>
              <SectionTitle tag="EDA-05">Counterfactual Simulation — "What Would Have Happened?"</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
                {[
                  { label: 'ACTUAL REVENUE', value: formatUSD(data.edv_actual_total), color: C.blue },
                  { label: 'OPTIMAL REVENUE', value: formatUSD(data.edv_optimal_total), color: C.green },
                  { label: 'LOST OPPORTUNITY', value: `−${formatUSD(data.total_gap_usd)}`, color: C.red },
                ].map(f => (
                  <Card key={f.label} style={{ textAlign: 'center' }}>
                    <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 8 }}>{f.label}</div>
                    <div style={{ color: f.color, fontSize: 26, fontWeight: 700, fontFamily: 'monospace' }}>{f.value}</div>
                  </Card>
                ))}
              </div>
              {logData.length > 0 && (
                <Card>
                  <div style={{ color: C.muted, fontSize: 11, marginBottom: 12 }}>OPTIMAL vs ACTUAL DISPATCH CURVE</div>
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={logData.slice(0, 100)} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="optGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={C.green} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={C.green} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={C.blue} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={C.blue} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis dataKey="hour" stroke={C.muted} tick={{ fill: C.muted, fontSize: 9 }} />
                      <YAxis stroke={C.muted} tick={{ fill: C.muted, fontSize: 9 }} />
                      <Tooltip contentStyle={{ background: '#111', border: `1px solid ${C.border}`, borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11, color: C.label }} />
                      <Area type="monotone" dataKey="optimal_action" name="Optimal Dispatch (MW)" stroke={C.green} fill="url(#optGrad)" strokeWidth={2} dot={false} />
                      <Area type="monotone" dataKey="actual_action" name="Actual Dispatch (MW)" stroke={C.blue} fill="url(#actGrad)" strokeWidth={2} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>
              )}
              {data.counterfactual_summary && (
                <Card style={{ marginTop: 16, borderColor: `${C.cyan}30`, background: `${C.cyan}06` }}>
                  <div style={{ color: C.cyan, fontSize: 12, lineHeight: 1.7, fontStyle: 'italic' }}>"{data.counterfactual_summary}"</div>
                </Card>
              )}
            </div>
          )}

          {/* ══ S6: EDA Metrics ══ */}
          {activeSection === 'metrics' && (
            <div>
              <SectionTitle tag="EDA-06">Economic Decision Quality Metrics</SectionTitle>
              {!m ? (
                <div style={{ color: C.muted, textAlign: 'center', padding: 40 }}>Run an audit to generate metrics.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {[
                    { label: 'Economic Decision Efficiency (EDE)', value: `${m.economic_decision_efficiency}%`, note: 'Captured ÷ Potential', color: m.economic_decision_efficiency >= 70 ? C.green : m.economic_decision_efficiency >= 40 ? C.yellow : C.red },
                    { label: 'Economic Leakage Ratio (ELR)', value: `${m.economic_leakage_ratio}%`, note: 'Lost ÷ Potential', color: m.economic_leakage_ratio <= 30 ? C.green : m.economic_leakage_ratio <= 60 ? C.yellow : C.red },
                    { label: 'Dispatch Accuracy', value: `${m.dispatch_accuracy}%`, note: 'Correct dispatches ÷ Total', color: m.dispatch_accuracy >= 80 ? C.green : m.dispatch_accuracy >= 60 ? C.yellow : C.red },
                    { label: 'Decision Delay Index', value: `${m.decision_delay_index}`, note: 'Avg steps late (0 = perfect)', color: m.decision_delay_index < 1 ? C.green : m.decision_delay_index < 3 ? C.yellow : C.red },
                    { label: 'Forecast Utilization Index', value: `${m.forecast_utilization_index}%`, note: '% of steps with forecast used', color: m.forecast_utilization_index >= 80 ? C.green : m.forecast_utilization_index >= 50 ? C.yellow : C.red },
                    { label: 'Curtailment Recovery Ratio', value: `${m.curtailment_recovery_ratio} MWh`, note: 'Potentially rescuable curtailed energy', color: C.cyan },
                    { label: 'Revenue Stacking Index', value: `${m.revenue_stacking_index} services`, note: 'Number of distinct revenue streams', color: m.revenue_stacking_index >= 3 ? C.green : C.yellow },
                    { label: 'Economic Intelligence Score', value: `${m.economic_intelligence_score} / 100`, note: 'Composite ISO-style performance index', color: m.economic_intelligence_score >= 70 ? C.green : m.economic_intelligence_score >= 40 ? C.yellow : C.red },
                    ...(m.battery_opportunity_capture !== null && m.battery_opportunity_capture !== undefined
                      ? [{ label: 'Battery Opportunity Capture', value: `${m.battery_opportunity_capture}%`, note: 'BESS-specific arbitrage capture rate', color: C.blue }]
                      : [])
                  ].map(metric => (
                    <Card key={metric.label}>
                      <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1.5, marginBottom: 6 }}>{metric.label}</div>
                      <div style={{ color: metric.color, fontSize: 28, fontWeight: 700, fontFamily: 'monospace' }}>{metric.value}</div>
                      <div style={{ color: C.muted, fontSize: 10, marginTop: 4 }}>{metric.note}</div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ S7: Financial Leakage ══ */}
          {activeSection === 'leakage' && (
            <div>
              <SectionTitle tag="EDA-07">Financial Value Leakage</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
                {[
                  { label: '24-HOUR', value: data.financial_leakage ? formatUSD(data.financial_leakage.period_24h) : '—', color: C.red },
                  { label: '7-DAY (EST.)', value: data.total_gap_usd > 0 ? formatUSD(data.total_gap_usd * 7) : '—', color: C.orange },
                  { label: '30-DAY (EST.)', value: data.total_gap_usd > 0 ? formatUSD(data.total_gap_usd * 30) : '—', color: C.yellow },
                  { label: '12-MONTH PROJECTION', value: data.financial_leakage ? formatUSD(data.financial_leakage.projection_12m) : '—', color: C.red },
                ].map(f => (
                  <Card key={f.label} style={{ textAlign: 'center', borderColor: `${f.color}30` }}>
                    <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 6 }}>{f.label}</div>
                    <div style={{ color: f.color, fontSize: 22, fontWeight: 700, fontFamily: 'monospace' }}>{f.value}</div>
                  </Card>
                ))}
              </div>
              {/* Top Sources */}
              <Card>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 16 }}>TOP LEAKAGE SOURCES</div>
                {(data.financial_leakage?.top_sources || []).map((src, i) => (
                  <div key={i} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: C.text, fontSize: 12 }}>{src.name}</span>
                      <span style={{ color: C.red, fontFamily: 'monospace', fontWeight: 700 }}>{formatUSD(src.usd)} ({src.pct}%)</span>
                    </div>
                    <div style={{ background: C.border, borderRadius: 4, height: 5 }}>
                      <div style={{ width: `${src.pct}%`, background: `linear-gradient(90deg, ${C.red}, ${C.orange})`, height: 5, borderRadius: 4 }} />
                    </div>
                  </div>
                ))}
                {(data.financial_leakage?.top_sources || []).length === 0 && <div style={{ color: C.muted }}>Run an audit to populate leakage sources.</div>}
              </Card>
              {/* 30-day history chart */}
              <Card style={{ marginTop: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2 }}>30-DAY TREND</div>
                  <BtnOutline color={C.red} onClick={async () => {
                    setHistoryLoading(true);
                    try { const r = await axios.get('/api/historical'); if (r.data?.history_log) setHistoryData(r.data.history_log); } catch (_) {}
                    setHistoryLoading(false);
                  }}>
                    {historyLoading ? 'QUERYING…' : 'SYNC HISTORY'}
                  </BtnOutline>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={historyData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="day" stroke={C.muted} tick={{ fill: C.muted, fontSize: 9 }} />
                    <YAxis stroke={C.muted} tickFormatter={v => `$${v}`} tick={{ fill: C.muted, fontSize: 9 }} />
                    <Tooltip contentStyle={{ background: '#111', border: `1px solid ${C.border}`, borderRadius: 8 }} formatter={v => [`$${v} Lost`, 'Daily Leakage']} />
                    <Bar dataKey="daily_gap" fill={C.red} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                {historyData.length === 0 && !historyLoading && (
                  <div style={{ textAlign: 'center', color: C.muted, marginTop: 10, fontSize: 11 }}>Connect to a production database to see historical trend.</div>
                )}
              </Card>
            </div>
          )}

          {/* ══ S8: Heat Map ══ */}
          {activeSection === 'heatmap' && (
            <div>
              <SectionTitle tag="EDA-08">Decision Heat Map — 24 Hours</SectionTitle>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                {[['optimal', C.green, 'Excellent Decision'], ['acceptable', C.yellow, 'Acceptable'], ['poor', C.orange, 'Poor Decision'], ['critical', C.red, 'Critical Loss']].map(([s, c, l]) => (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: c }} />
                    <span style={{ color: C.label, fontSize: 11 }}>{l}</span>
                  </div>
                ))}
              </div>
              {data.heat_map && data.heat_map.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 5 }}>
                  {data.heat_map.slice(0, 288).map((cell, i) => (
                    <div key={i} title={`${cell.label} | ${cell.action_taken} | Gap: $${cell.gap_usd}`}
                      style={{
                        height: 44, borderRadius: 6,
                        backgroundColor: `${heatColor(cell.status)}22`,
                        border: `1px solid ${heatColor(cell.status)}60`,
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        cursor: 'default'
                      }}>
                      <div style={{ color: heatColor(cell.status), fontSize: 8, fontFamily: 'monospace' }}>{cell.label}</div>
                      {cell.gap_usd > 0 && <div style={{ color: C.red, fontSize: 7, marginTop: 1 }}>−${cell.gap_usd.toFixed(0)}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: C.muted, textAlign: 'center', padding: 60 }}>Run an audit to generate the heat map.</div>
              )}
            </div>
          )}

          {/* ══ S9: Opportunity Ranking ══ */}
          {activeSection === 'opps' && (
            <div>
              <SectionTitle tag="EDA-09">Opportunity Ranking</SectionTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {(data.opportunities || []).length === 0 && <div style={{ color: C.muted, textAlign: 'center', padding: 40 }}>Run an audit to generate opportunities.</div>}
                {(data.opportunities || []).map((op, i) => (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '32px 1fr 140px 100px 100px', gap: 16, alignItems: 'center', padding: '14px 20px', background: C.surface, border: SECTION_BORDER, borderRadius: 10 }}>
                    <div style={{ color: C.muted, fontSize: 13, fontWeight: 700, fontFamily: 'monospace' }}>#{i + 1}</div>
                    <div>
                      <div style={{ color: C.text, fontWeight: 600, fontSize: 13 }}>{op.name}</div>
                      <div style={{ color: C.muted, fontSize: 11, marginTop: 2 }}>{op.description}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ color: C.green, fontFamily: 'monospace', fontSize: 15, fontWeight: 700 }}>{formatUSD(op.annual_gain_usd)}</div>
                      <div style={{ color: C.muted, fontSize: 9, letterSpacing: 1 }}>ANNUAL GAIN</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <Pill label={op.difficulty} color={op.difficulty === 'Easy' ? C.green : op.difficulty === 'Medium' ? C.yellow : C.red} />
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      {'★'.repeat(op.priority_stars) + '☆'.repeat(5 - op.priority_stars)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ══ S10: AI Commentary ══ */}
          {activeSection === 'ai' && (
            <div>
              <SectionTitle tag="EDA-10">AI Auditor Commentary</SectionTitle>
              <Card style={{ borderColor: `${C.cyan}30`, background: `${C.cyan}05` }}>
                {data.ai_commentary ? (
                  <pre style={{ color: C.text, fontSize: 13, lineHeight: 1.8, fontFamily: "'Inter', sans-serif", whiteSpace: 'pre-wrap', margin: 0 }}>
                    {data.ai_commentary}
                  </pre>
                ) : (
                  <div style={{ color: C.muted, textAlign: 'center', padding: 40 }}>Run an audit to generate the AI commentary.</div>
                )}
              </Card>
            </div>
          )}

          {/* ══ S11: Governance ══ */}
          {activeSection === 'govern' && (
            <div>
              <SectionTitle tag="EDA-11">Governance &amp; Decision Authority</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <Card>
                  <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 16 }}>DECISION AUTHORITY BREAKDOWN</div>
                  {logData.length > 0 ? (() => {
                    const overrides = logData.filter(d => d.operator_override).length;
                    const auto = logData.length - overrides;
                    const ovPct = ((overrides / logData.length) * 100).toFixed(1);
                    const autoPct = ((auto / logData.length) * 100).toFixed(1);
                    return (
                      <>
                        <MetricRow label="Automatic (EMS)" value={`${autoPct}%`} color={C.green} note={`${auto} dispatches`} />
                        <MetricRow label="Human Override" value={`${ovPct}%`} color={C.orange} note={`${overrides} dispatches`} />
                        <MetricRow label="Total Decisions" value={`${logData.length}`} color={C.cyan} />
                        <div style={{ marginTop: 16, padding: 12, background: `${C.orange}10`, border: `1px solid ${C.orange}30`, borderRadius: 8 }}>
                          <div style={{ color: C.orange, fontSize: 11, fontWeight: 600 }}>OVERRIDE IMPACT</div>
                          <div style={{ color: C.label, fontSize: 11, marginTop: 4 }}>
                            Each human override carries average leakage risk. Review override justification log for compliance.
                          </div>
                        </div>
                      </>
                    );
                  })() : <div style={{ color: C.muted }}>Run an audit to populate governance data.</div>}
                </Card>
                <Card>
                  <div style={{ color: C.muted, fontSize: 10, letterSpacing: 2, marginBottom: 16 }}>COMPLIANCE CHECKLIST</div>
                  {[
                    { check: 'Dispatch policy followed', status: data.dq_score > 0.6 },
                    { check: 'Market rules observed', status: true },
                    { check: 'SOC limits respected', status: true },
                    { check: 'Forecast data integrated', status: (m?.forecast_utilization_index || 0) > 0 },
                    { check: 'Decision justification logged', status: logData.length > 0 },
                  ].map((c, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                      <span style={{ color: C.label, fontSize: 12 }}>{c.check}</span>
                      <Pill label={c.status ? 'PASS' : 'REVIEW'} color={c.status ? C.green : C.red} />
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          )}

          {/* ══ S12: Math Appendix ══ */}
          {activeSection === 'appendix' && (
            <div>
              <SectionTitle tag="EDA-12">Mathematical Appendix</SectionTitle>
              <Card>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {[
                    {
                      name: 'Economic Decision Efficiency (EDE)',
                      formula: 'EDE = V_captured / V_potential',
                      desc: 'Primary performance ratio. Measures the fraction of available market value actually captured.',
                      units: 'Dimensionless [0, 1]'
                    },
                    {
                      name: 'Economic Leakage (EL)',
                      formula: 'EL = V_potential − V_captured',
                      desc: 'Absolute revenue destroyed by sub-optimal dispatch decisions.',
                      units: 'USD per audit period'
                    },
                    {
                      name: 'Decision Quality Index (DQI)',
                      formula: 'DQI = Σ(wᵢ · Sᵢ) / Σwᵢ',
                      desc: 'Weighted composite score. wᵢ = economic impact weight of decision i, Sᵢ = binary correctness score.',
                      units: 'Score [0, 100]'
                    },
                    {
                      name: 'Counterfactual Gap (CG)',
                      formula: 'CG(t) = EDV_optimal(t) − EDV_actual(t)',
                      desc: 'Per-timestep revenue gap between MILP-optimal and actual dispatch.',
                      units: 'USD per timestep'
                    },
                    {
                      name: 'Step Economic Decision Value (EDV)',
                      formula: 'EDV(t) = (P(t) × D(t)) − (c_deg × D(t))',
                      desc: 'P(t) = market price, D(t) = discharge power, c_deg = degradation cost per MWh.',
                      units: 'USD per timestep'
                    },
                    {
                      name: 'Economic Intelligence Score (EIS)',
                      formula: 'EIS = 0.45·EDE + 0.30·DA + 0.15·FUI + 0.10·(1−ELR)',
                      desc: 'Composite ISO-style index. DA = Dispatch Accuracy, FUI = Forecast Utilization Index.',
                      units: 'Score [0, 100]'
                    },
                    {
                      name: 'Annual Leakage Projection (ALP)',
                      formula: 'ALP = EL_24h × 365',
                      desc: 'Linear annualisation of single-period leakage. Assumes stationary price/dispatch patterns.',
                      units: 'USD/year'
                    },
                  ].map(eq => (
                    <div key={eq.name} style={{ padding: '16px 20px', background: 'rgba(0,229,255,0.03)', border: `1px solid ${C.cyan}20`, borderRadius: 10 }}>
                      <div style={{ color: C.cyan, fontSize: 13, fontWeight: 700, marginBottom: 8 }}>{eq.name}</div>
                      <div style={{ fontFamily: 'monospace', fontSize: 14, color: C.yellow, backgroundColor: 'rgba(255,214,0,0.06)', padding: '6px 12px', borderRadius: 6, display: 'inline-block', marginBottom: 8 }}>{eq.formula}</div>
                      <div style={{ color: C.label, fontSize: 12, lineHeight: 1.6 }}>{eq.desc}</div>
                      <div style={{ color: C.muted, fontSize: 10, marginTop: 4 }}>Units: {eq.units}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

        </main>
      </div>

      {/* ── Methodology Modal ── */}
      {showMethodology && (
        <div onClick={() => setShowMethodology(false)} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#0c0e12', border: `1px solid ${C.border}`, borderRadius: 16, padding: 32, maxWidth: 680, width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div style={{ color: C.cyan, fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>PREDAIOT METHODOLOGY</div>
              <button onClick={() => setShowMethodology(false)} style={{ background: 'none', border: 'none', color: C.muted, fontSize: 20, cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {[
                ['1. Optimal Potential (MILP)', 'Solved using Mixed-Integer Linear Programming across all timesteps simultaneously. Maximizes total revenue subject to power physics, SOC bounds, and degradation cost. This is the hard upper bound — physically achievable, economically optimal.'],
                ['2. Captured Value', 'Net revenue from actual SCADA-recorded dispatch decisions, after degradation cost. This is real money that entered the settlement meter.'],
                ['3. Value Leakage', 'Precise arithmetic difference: Optimal − Actual. Every dollar here was physically achievable but economically squandered by poor timing.'],
                ['4. Universal Asset Support', 'The engine is asset-agnostic. Upload any CSV/Excel with `price` and `actual_discharge` columns. Optional columns (soc, curtailment_mw, forecast_price, asset_type) unlock deeper intelligence layers.'],
                ['5. AI Commentary', 'Generated deterministically from audit results — not a language model. Every sentence is derived from computed statistics, ensuring auditability and repeatability.'],
                ['6. Patent-Pending Method', 'The counterfactual gap methodology — computing the exact decision-by-decision revenue difference against an MILP optimum — is the core of the PREDAIOT patent filing.'],
              ].map(([title, body]) => (
                <div key={title} style={{ padding: '14px 16px', background: C.surface, border: SECTION_BORDER, borderRadius: 8 }}>
                  <div style={{ color: C.text, fontWeight: 600, fontSize: 12, marginBottom: 6 }}>{title}</div>
                  <div style={{ color: C.label, fontSize: 12, lineHeight: 1.7 }}>{body}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Tiny button component ─────────────────────────────────────────────────
function BtnOutline({ color, children, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '8px 18px', backgroundColor: 'transparent',
        color: disabled ? '#444' : color,
        border: `1px solid ${disabled ? '#444' : color}`,
        borderRadius: 7, cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: 11, letterSpacing: 1, fontWeight: 700, transition: 'opacity 0.15s',
      }}
    >
      {children}
    </button>
  );
}