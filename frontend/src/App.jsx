import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState({
    edv_optimal_total: 0, 
    edv_actual_total: 0, 
    dq_score: 0, 
    total_gap_usd: 0, 
    decision_log: []
  });
  const [loading, setLoading] = useState(false);

  // جلب البيانات الحية تلقائياً من جسر الـ SCADA
  useEffect(() => {
    const fetchLiveSCADA = async () => {
      try {
        const response = await axios.get('/api/latest');
        if (response.data && response.data.dq_score > 0) {
          setData(response.data);
        }
      } catch (error) {
        // تجاهل الأخطاء في الخلفية لمنع توقف التطبيق
      }
    };
    
    fetchLiveSCADA();
    const interval = setInterval(fetchLiveSCADA, 60000); // تحديث كل 60 ثانية
    return () => clearInterval(interval);
  }, []);

  const fetchAuditData = async () => {
    setLoading(true);
    try {
      const time_series = [];
      let actual_soc = 0.2; 
      const e_max = 100;
      
      for (let i = 0; i < 288; i++) {
        const basePrice = 30 + 70 * Math.sin((i - 36) * (Math.PI / 180));
        const noise = (Math.random() - 0.5) * 10;
        const price = Math.max(0, parseFloat((basePrice + noise).toFixed(2)));
        
        let actual_discharge = 0; 
        
        // محاكاة فيزيائية واقعية دون متغيرات غير مستخدمة
        if (price < 20 && actual_soc < 0.9) {
          actual_soc += (40 * 0.95 / e_max); // شحن
        }
        
        if (price > 40 && price < 80 && actual_soc > 0.2) {
          const max_possible_discharge = (actual_soc - 0.2) * e_max;
          actual_discharge = Math.min(40, max_possible_discharge); // تفريغ خاطئ
          actual_soc -= (actual_discharge / 0.95 / e_max);
        }
        
        time_series.push({ hour: i, price: price, actual_discharge: actual_discharge });
      }
      
      const payload = { 
        asset: { p_max: 50, e_max: 100, soc_init: 0.2, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 }, 
        time_series 
      };
      
      const response = await axios.post('/api/v1/audit', payload);
      setData(response.data);
    } catch (error) {
      console.error("Audit failed:", error);
    }
    setLoading(false);
  };

  // استخراج أسوأ 3 قرارات بشكل آمن (تجنب انهيار التطبيق إذا كان المصفوفة فارغة)
  const logData = Array.isArray(data.decision_log) ? data.decision_log : [];
  const worstDecisions = [...logData]
    .sort((a, b) => (b.gap_step || 0) - (a.gap_step || 0))
    .slice(0, 3);

  const formatTime = (hourIndex) => {
    const hours = Math.floor(hourIndex / 12);
    const mins = (hourIndex % 12) * 5;
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
  };

  const styles = {
    container: { padding: '20px', backgroundColor: '#050505', color: '#fff', minHeight: '100vh', fontFamily: "'Inter', 'Segoe UI', sans-serif" },
    card: { backgroundColor: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' },
    neonText: { textShadow: '0 0 10px rgba(0, 229, 255, 0.7)' },
    redGlow: { textShadow: '0 0 15px rgba(255, 0, 85, 0.8)' }
  };

  return (
    <div style={styles.container}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '15px' }}>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '300', letterSpacing: '2px' }}>
          PREDAIOT <span style={{ color: '#00E5FF', ...styles.neonText }}>INTELLIGENCE</span>
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '10px', height: '10px', backgroundColor: '#00FF00', borderRadius: '50%', boxShadow: '0 0 8px #00FF00' }}></div>
          <span style={{ color: '#888', fontSize: '14px' }}>LIVE ASSET MONITORING</span>
        </div>
      </div>

      {/* الكروت الرئيسية */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '30px' }}>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Optimal Potential</div>
          <div style={{ fontSize: '32px', fontWeight: '700', color: '#FFD700', marginTop: '10px' }}>${data.edv_optimal_total.toLocaleString()}</div>
        </div>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Actual Captured</div>
          <div style={{ fontSize: '32px', fontWeight: '700', color: '#00E5FF', marginTop: '10px' }}>${data.edv_actual_total.toLocaleString()}</div>
        </div>
        <div style={{ ...styles.card, borderColor: 'rgba(255, 0, 85, 0.3)' }}>
          <div style={{ color: '#FF0055', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Value Destroyed (Gap)</div>
          <div style={{ fontSize: '32px', fontWeight: '700', color: '#FF0055', marginTop: '10px', ...styles.redGlow }}>-${data.total_gap_usd.toLocaleString()}</div>
        </div>
        <div style={styles.card}>
          <div style={{ color: '#888', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Decision Quality (DQ)</div>
          <div style={{ fontSize: '42px', fontWeight: '800', color: data.dq_score >= 0.8 ? '#00FF00' : data.dq_score >= 0.6 ? '#FFAA00' : '#FF0055', marginTop: '10px' }}>
            {(data.dq_score * 100).toFixed(1)}<span style={{ fontSize: '20px' }}>%</span>
          </div>
        </div>
      </div>

      <button 
        onClick={fetchAuditData} 
        disabled={loading}
        style={{ padding: '12px 24px', backgroundColor: 'transparent', color: '#00E5FF', border: '1px solid #00E5FF', borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer', marginBottom: '30px', fontSize: '14px', letterSpacing: '1px', fontWeight: '600' }}
      >
        {loading ? 'OPTIMIZING 288 NODES...' : 'RUN 24-HR FORENSIC AUDIT'}
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        
        {/* الرسم البياني المتقدم (كتلة الفجوة الحمراء) */}
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 20px 0', fontWeight: '400', fontSize: '16px', color: '#CCC' }}>ECONOMIC VALUE FUNNEL (24-HR)</h3>
          <ResponsiveContainer width="100%" height={350}>
            <ComposedChart data={logData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gapFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FF0055" stopOpacity={0.4}/>
                  <stop offset="100%" stopColor="#FF0055" stopOpacity={0.05}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#222" />
              <XAxis dataKey="hour" stroke="#555" tickFormatter={formatTime} interval={23} />
              <YAxis stroke="#555" tickFormatter={(v) => `$${v}`} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#111', border: '1px solid #333', borderRadius: '8px' }} 
                labelFormatter={formatTime}
                formatter={(value, name) => {
                  const colors = { 'Optimal Path': '#FFD700', 'Actual Path': '#00E5FF', 'Economic Gap': '#FF0055' };
                  return [`$${value}`, <span key={name} style={{ color: colors[name] }}>{name}</span>];
                }} 
              />
              <Bar dataKey="gap_step" fill="url(#gapFill)" name="Economic Gap" barSize={4} />
              <Line type="monotone" dataKey="edv_optimal_step" stroke="#FFD700" dot={false} strokeWidth={2} name="Optimal Path" />
              <Line type="monotone" dataKey="edv_actual_step" stroke="#00E5FF" dot={false} strokeWidth={2} name="Actual Path" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* مصفوفة الفضيحة */}
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 20px 0', fontWeight: '400', fontSize: '16px', color: '#CCC' }}>TOP 3 DECISION FAILURES</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {worstDecisions.length > 0 && worstDecisions[0].gap_step > 0 ? worstDecisions.map((dec, index) => (
              <div key={`failure-${index}`} style={{ backgroundColor: 'rgba(255, 0, 85, 0.05)', border: '1px solid rgba(255, 0, 85, 0.2)', borderRadius: '8px', padding: '15px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#888', fontSize: '13px' }}>TIME: {formatTime(dec.hour)}</span>
                  <span style={{ color: '#FF0055', fontWeight: 'bold' }}>-${dec.gap_step.toLocaleString()}</span>
                </div>
                <div style={{ fontSize: '12px', color: '#AAA', lineHeight: '1.5' }}>
                  <span style={{ color: '#FFD700' }}>Should have:</span> Discharge {dec.optimal_action} MW @ ${dec.price}<br/>
                  <span style={{ color: '#00E5FF' }}>Actually did:</span> Discharge {dec.actual_action} MW @ ${dec.price}
                </div>
              </div>
            )) : <div style={{ color: '#444', fontStyle: 'italic' }}>Waiting for data...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
export default App;