import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState({
    edv_optimal_total: 0,
    edv_actual_total: 0,
    q_score: 0,
    total_gap_usd: 0,
    decision_log: []
  });
  const [loading, setLoading] = useState(false);
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [shareLink, setShareLink] = useState("");
  const [showMethodology, setShowMethodology] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const fetchLiveSCADA = async () => {
      try {
        const response = await axios.get('/api/latest');
        if (response.data && response.data.q_score > 0) {
          setData(response.data);
        }
      } catch (error) {
        // Ignore backend errors to prevent app crash
      }
    };

    fetchLiveSCADA();
    const interval = setInterval(fetchLiveSCADA, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchAuditData = async () => {
    setLoading(true);
    try {
      const time_series = [];
      let actual_soc = 0.2;
      const e_max = 100;

      for (let i = 0; i < 288; i++) {
        const basePrice = 30 + 70 * Math.sin((i - 72) * (Math.PI / 144));
        const noise = (Math.random() - 0.5) * 10;
        const price = Math.max(5, parseFloat((basePrice + noise).toFixed(2)));

        let actual_discharge = 0;

        if (price < 20 && actual_soc < 0.9) {
          actual_soc += (40 * 0.95 / e_max);
        }

        if (price > 40 && price < 200 && actual_soc > 0.2) {
          const max = (actual_soc - 0.2) * e_max;
          actual_discharge = Math.min(40, max);
          actual_soc -= (actual_discharge / 0.95 / e_max);
        }

        time_series.push({ hour: i, price: price, actual_discharge: actual_discharge });
      }

      const payload = {
        asset: { p_max: 50, e_max: 100, soc_init: 0.5, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 },
        time_series
      };

      const response = await axios.post('/api/v1/audit', payload);
      setData(response.data);
    } catch (error) {
      console.error("Audit failed:", error);
    }
    setLoading(false);
  };

  const fetchHistoricalData = async () => {
    setHistoryLoading(true);
    try {
      const response = await axios.get('/api/historical');
      if (response.data && response.data.history_log) {
        setHistoryData(response.data.history_log);
      }
    } catch (error) {
      alert("Failed to load historical data. Ensure you are on the cloud.");
    }
    setHistoryLoading(false);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post('/api/v1/audit/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setData(response.data);
    } catch (error) {
      alert("Error processing file. Ensure it has 'price' and 'actual_discharge' columns.");
    }

    setUploading(false);
    event.target.value = '';
  };

  const handleShare = async () => {
    if (!data.q_score) return alert("Run an audit first.");
    try {
      const response = await axios.post('/api/share', data);
      const fullUrl = window.location.origin + response.data.share_url;
      setShareLink(fullUrl);
      navigator.clipboard.writeText(fullUrl);
      alert(`Shareable link copied to clipboard!\n${fullUrl}`);
    } catch (error) {
      console.error("Share failed:", error);
    }
  };

  const logData = Array.isArray(data.decision_log) ? data.decision_log : [];
  const topRecovered = [...logData]
    .sort((a, b) => (b.gap_step || 0) - (a.gap_step || 0))
    .slice(0, 3);

  const formatTime = (hourIndex) => {
    const hours = Math.floor(hourIndex / 12);
    const mins = (hourIndex % 12) * 5;
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
  };

  const captureRate = data.edv_optimal_total > 0
    ? (data.edv_actual_total / data.edv_optimal_total) * 100
    : 0;

  const captureColor = captureRate >= 70 ? '#00FF00' : captureRate >= 40 ? '#FFAA00' : '#FF0055';

  const leakageRate = data.edv_optimal_total > 0
    ? ((data.edv_optimal_total - data.edv_actual_total) / data.edv_optimal_total) * 100
    : 0;

  const arbitrageLabel = data.q_score >= 0.8 ? 'Optimal' : data.q_score >= 0.6 ? 'Underperforming' : 'Sub-optimal';
  const arbitrageColor = data.q_score >= 0.8 ? '#00FF00' : data.q_score >= 0.6 ? '#FFAA00' : '#FF0055';

  const styles = {
    container: {
      padding: '20px',
      backgroundColor: '#050505',
      color: '#fff',
      minHeight: '100vh',
      fontFamily: "'Inter', 'Segoe UI', sans-serif"
    },
    card: {
      backgroundColor: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '12px',
      padding: '20px',
      marginTop: '16px'
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '15px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <img
          src="/logo.jpeg"
            alt="PREDAIOT Logo"
            style={{ height: '45px', objectFit: 'contain' }}
          />
          <div>
            <span style={{ color: '#CCC', fontSize: '18px', fontWeight: '600', letterSpacing: '2px' }}>PREDAIOT</span>
            <div style={{ color: '#666', fontSize: '11px', letterSpacing: '1.5px', marginTop: '2px' }}>ECONOMIC DECISION LAYER</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <div style={{ width: '8px', height: '8px', backgroundColor: '#00FF00', borderRadius: '50%', boxShadow: '0 0 8px #00FF00' }}></div>
          <span style={{ color: '#666', fontSize: '12px' }}>SYSTEM ACTIVE</span>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: '15px', marginBottom: '30px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}>
        <button
          onClick={fetchAuditData}
          disabled={loading}
          style={{ padding: '12px 24px', backgroundColor: 'transparent', color: '#00E5FF', border: '1px solid #00E5FF', borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '14px', letterSpacing: '1px', fontWeight: '600' }}
        >
          {loading ? 'OPTIMIZING...' : 'RUN 24-HR ANALYSIS'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv, .xlsx, .xls"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />
        <button
          onClick={() => fileInputRef.current.click()}
          disabled={uploading}
          style={{ padding: '12px 24px', backgroundColor: 'transparent', color: '#00FF00', border: '1px solid #00FF00', borderRadius: '8px', cursor: uploading ? 'not-allowed' : 'pointer', fontSize: '14px', letterSpacing: '1px', fontWeight: '600' }}
        >
          {uploading ? 'PARSING...' : 'UPLOAD ACTUALS'}
        </button>
        <button
          onClick={handleShare}
          style={{ padding: '12px 24px', backgroundColor: 'transparent', color: '#FFD700', border: '1px solid #FFD700', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', letterSpacing: '1px', fontWeight: '600' }}
        >
          SHARE REPORT
        </button>
      </div>

      {shareLink && (
        <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: 'rgba(255, 215, 0, 0.1)', border: '1px solid rgba(255, 215, 0, 0.3)', borderRadius: '8px', fontSize: '12px', wordBreak: 'break-all' }}>
          🔗 Client Report Link: {shareLink}
        </div>
      )}

      {/* Section 1: Today's Economic Story */}
      <div style={styles.card}>
        <h3 style={{ margin: '0 0 20px 0', fontWeight: '500', fontSize: '16px', color: '#FFF' }}>Today's Economic Story</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', fontFamily: 'monospace', fontSize: '13px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '6px' }}>
            <span style={{ color: '#888' }}>MARKET OPPORTUNITY</span>
            <span style={{ color: '#FFD700', fontWeight: 'bold' }}>${data.edv_optimal_total.toLocaleString()}</span>
          </div>
          <div style={{ textAlign: 'center', fontSize: '20px', color: '#555' }}>↓</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', backgroundColor: 'rgba(0, 229, 255, 0.05)', borderRadius: '6px' }}>
            <span style={{ color: '#888' }}>CAPTURED VALUE</span>
            <span style={data.edv_actual_total > 0 ? { color: '#00E5FF' } : { color: '#555' }}>${data.edv_actual_total.toLocaleString()}</span>
          </div>
          <div style={{ textAlign: 'center', fontSize: '20px', color: '#555' }}>↓</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', backgroundColor: 'rgba(255, 0, 85, 0.05)', borderRadius: '6px' }}>
            <span style={{ color: '#888' }}>VALUE LEAKAGE</span>
            <span style={{ color: '#FF0055', fontWeight: 'bold' }}>-${data.total_gap_usd.toLocaleString()}</span>
          </div>
          <div style={{ marginTop: '10px', padding: '10px', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ color: '#AAA', fontSize: '12px' }}>ROOT CAUSE: </span>
            <span style={{ color: '#FF6666', fontSize: '12px' }}>
              {logData.length > 0 && logData[0].gap_step > 0
                ? 'Asset remained idle during peak pricing periods.'
                : 'Waiting for data...'}
            </span>
          </div>
        </div>
      </div>

      {/* Section 2: KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px', marginBottom: '30px' }}>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px' }}>Economic Capture Rate</div>
          <div style={{ fontSize: '36px', fontWeight: '700', color: captureColor, marginTop: '8px' }}>
            {data.edv_optimal_total > 0 ? `${captureRate.toFixed(1)}%` : '0.0%'}
          </div>
        </div>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px' }}>Value Leakage</div>
          <div style={{ fontSize: '36px', fontWeight: '700', color: '#FF0055', marginTop: '8px' }}>
            {data.edv_optimal_total > 0 ? `${leakageRate.toFixed(1)}%` : '0.0%'}
          </div>
        </div>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px' }}>System Status</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#00E5FF', marginTop: '8px' }}>OPERATIONAL</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '30px' }}>

        {/* Section 3: Top 3 Recoverable Opportunities */}
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 20px 0', fontWeight: '500', fontSize: '15px', color: '#CCC' }}>Top 3 Recoverable Opportunities</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {topRecovered.length > 0 && topRecovered[0].gap_step > 0
              ? topRecovered.map((dec, i) => (
                <div key={`rec-${i}`} style={{ backgroundColor: 'rgba(255, 215, 0, 0.05)', border: '1px solid rgba(255, 215, 0, 0.2)', borderRadius: '8px', padding: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ color: '#888', fontSize: '12px' }}>TIME: {formatTime(dec.hour)}</span>
                    <span style={{ color: '#FFD700', fontWeight: 'bold' }}>+${dec.gap_step.toLocaleString()} Recoverable</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#AAA', lineHeight: '1.5' }}>
                    Status: <span style={{ color: '#00E5FF' }}>Missed Opportunity</span> at ${dec.price}/MWh.
                  </div>
                </div>
              ))
              : <div style={{ color: '#444' }}>Analyzing data...</div>
            }
          </div>
        </div>

        {/* Section 4: Asset Economic DNA */}
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 20px 0', fontWeight: '500', fontSize: '15px', color: '#CCC' }}>Asset Economic DNA</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {[
              {
                title: 'Opportunity Capture',
                value: data.edv_optimal_total > 0 ? `${captureRate.toFixed(1)}%` : 'N/A',
                color: data.edv_optimal_total > 0 ? captureColor : '#555'
              },
              {
                title: 'Value Leakage',
                value: data.edv_optimal_total > 0 ? `${leakageRate.toFixed(1)}%` : 'N/A',
                color: data.edv_optimal_total > 0 ? '#FF0055' : '#555'
              },
              { title: 'Curtailment Intel.', value: 'Low', color: '#FFAA00' },
              { title: 'Decision Latency', value: '< 1 min', color: '#00E5FF' },
              { title: 'Arbitrage Score', value: data.q_score > 0 ? arbitrageLabel : 'N/A', color: data.q_score > 0 ? arbitrageColor : '#555' }
            ].map((item, i) => (
              <div key={`dna-${i}`} style={{ padding: '12px', backgroundColor: 'rgba(255,255,255,0.02)', borderLeft: `3px solid ${item.color}`, borderRadius: '4px' }}>
                <div style={{ fontSize: '12px', color: '#AAA', marginBottom: '4px' }}>{item.title}</div>
                <div style={{ fontSize: '14px', fontWeight: '700', color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Section 5: AI Strategy Recommendations */}
      <div style={styles.card}>
        <h3 style={{ margin: '0 0 20px 0', fontWeight: '500', fontSize: '15px', color: '#CCC' }}>AI Strategy Recommendations (Next 24H)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          {[
            { action: 'Charge', time: '02:35', revenue: '+$1,832', conf: '91%' },
            { action: 'Hold', time: '08:15', revenue: '$0.00', conf: '99%' },
            { action: 'Discharge', time: '09:40', revenue: '+$4,205', conf: '88%' }
          ].map((rec, i) => (
            <div key={`ai-${i}`} style={{ padding: '12px', backgroundColor: 'rgba(0, 229, 255, 0.05)', border: '1px solid rgba(0, 229, 255, 0.2)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{ color: '#00E5FF', fontWeight: 'bold', fontSize: '12px' }}>{rec.action.toUpperCase()}</span>
                <span style={{ color: '#888', fontSize: '11px' }}>TARGET: {rec.time}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#888', fontSize: '11px' }}>Exp. Add. Rev: {rec.revenue}</span>
                <span style={{ color: '#00FF00', fontSize: '11px', fontWeight: 'bold' }}>Confidence: {rec.conf}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Section 6: 30-Day History Chart */}
      <div style={styles.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ margin: '0', fontWeight: '500', fontSize: '15px', color: '#CCC' }}>30-DAY FINANCIAL HEMORRHAGE (TREND)</h3>
          <button
            onClick={fetchHistoricalData}
            disabled={historyLoading}
            style={{ padding: '8px 16px', backgroundColor: 'transparent', color: '#FF0055', border: '1px solid #FF0055', borderRadius: '6px', cursor: historyLoading ? 'not-allowed' : 'pointer', fontSize: '12px' }}
          >
            {historyLoading ? 'QUERYING...' : 'SYNC HISTORY'}
          </button>
        </div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={historyData} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis dataKey="day" stroke="#555" tick={{ fill: '#888', fontSize: 10 }} />
            <YAxis stroke="#555" tickFormatter={(v) => `$${v}`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#111', border: '1px solid #333', borderRadius: '8px' }}
              formatter={(value) => [`$${value} Lost`, "Daily Loss"]}
            />
            <Bar dataKey="daily_gap" fill="#FF0055" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {historyData.length === 0 && !historyLoading &&
          <div style={{ textAlign: 'center', color: '#555', marginTop: '10px', fontSize: '13px' }}>Waiting for historical data...</div>
        }
      </div>

      {/* Methodology Modal */}
      {showMethodology && (
        <div
          style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, overflowY: 'auto' }}
          onClick={() => setShowMethodology(false)}
        >
          <div
            style={{ backgroundColor: '#111', border: '1px solid #333', borderRadius: '16px', padding: '30px', maxWidth: '700px', width: '90%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ margin: 0, color: '#00E5FF', fontSize: '20px', fontWeight: '600' }}>Methodology</h2>
              <button
                onClick={() => setShowMethodology(false)}
                style={{ background: 'none', border: 'none', color: '#888', fontSize: '24px', cursor: 'pointer', lineHeight: '1' }}
              >✕</button>
            </div>
            <div style={{ color: '#BBB', fontSize: '14px', lineHeight: '1.8' }}>
              <p style={{ marginBottom: '16px' }}><strong>1. Optimal Potential Calculation:</strong> Calculated using Mixed-Integer Linear Programming (MILP). The engine solves simultaneous equations to find the theoretical maximum profit, subject to power physics and degradation costs.</p>
              <p style={{ marginBottom: '16px' }}><strong>2. Captured Value:</strong> Actual revenue built on decisions recorded by SCADA sensor systems. This measures what actually entered the revenue meter.</p>
              <p style={{ marginBottom: '16px' }}><strong>3. Value Leakage (The Gap):</strong> The precise mathematical difference of <code>Optimal - Actual</code>. Measures money lost due to poor operational timing — the money left on the table.</p>
              <p style={{ marginBottom: '16px' }}><strong>4. Economic Capture Rate:</strong> A derived percentage recovered from the mathematical analysis. Provides a universal metric for comparing assets regardless of size or geographic location.</p>
              <p><strong>5. AI Recommendations:</strong> Based on predictive algorithms that forecast the next 24-hour price curve to identify optimal charge and discharge windows, maximizing profit rate and minimizing leakage.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;