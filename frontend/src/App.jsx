import React, { useState } from 'react';
import axios from 'axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  // الحالة الابتدائية للبيانات (أصفار)
  const [data, setData] = useState({
    edv_optimal_total: 0, 
    edv_actual_total: 0, 
    dq_score: 0, 
    total_gap_usd: 0, 
    decision_log: []
  });
  const [loading, setLoading] = useState(false);

  // دالة الاتصال بالخادم وتوليد محاكاة 24 ساعة حقيقية
  const fetchAuditData = async () => {
    setLoading(true);
    try {
      // 1. توليد بيانات 24 ساعة (288 نقطة، كل نقطة تمثل 5 دقائق)
      const time_series = [];
      let actual_soc = 0.2; // تتبع حالة شحن المشغل الفعلية لضمان الواقعية
      const e_max = 100;
      
      for (let i = 0; i < 288; i++) {
        // معادلة توليد سعر واقعي (يقلب ليلاً ويرتفع مساءً)
        const basePrice = 30 + 70 * Math.sin((i - 36) * (Math.PI / 180));
        const noise = (Math.random() - 0.5) * 10; // ضوضى سوقية عشوائية
        const price = Math.max(0, parseFloat((basePrice + noise).toFixed(2)));

        let actual_discharge = 0;
        let actual_charge = 0;

        // قرارات "مشغل بشري" يرتكب خطأ توقيت كلاسيكي:
        // 1. يشحن في الصباح الباكر عندما يكون السعر منخفضاً
        if (price < 20 && actual_soc < 0.9) {
            actual_charge = 40;
        }
        // 2. الخطأ القاتل: يبدأ بالتفريغ عندما يكون السعر "مقبولاً" (40-60$) بدلاً من انتظار الذروة
        if (price > 40 && price < 80 && actual_soc > 0.2) {
            actual_discharge = 40;
        }
        
        // حساب الحد الأقصى المسموح به فيزيائياً لعدم سرقة طاقة من المستقبل
        let max_possible_discharge = (actual_soc - 0.2) * e_max;
        if (actual_discharge > max_possible_discharge) {
            actual_discharge = max_possible_discharge;
        }

        // تحديث حالة الشحن الفعلية للمشغل للحظة التالية
        actual_soc = actual_soc + (actual_charge * 0.95 / e_max) - (actual_discharge / 0.95 / e_max);
        
        // نرسل التفريغ فقط لأن محرك PREDAIOT يعوض التكاليف بناءً عليه
        time_series.push({ hour: i, price: price, actual_discharge: actual_discharge });
      }

      const payload = {
        asset: { p_max: 50, e_max: 100, soc_init: 0.2, eta_ch: 0.95, eta_dis: 0.95, deg_cost: 5.0 },
        time_series: time_series
      };
      
      // 2. إرسال البيانات إلى خادم PREDAIOT
      const response = await axios.post('/api/v1/audit', payload);
      setData(response.data);
    } catch (error) {
      alert("خطأ في الاتصال بالخادم، تأكد أن خادم البايثون يعمل في الخلفية");
    }
    setLoading(false);
  };

  // دالة تحديد لون معامل الجودة بناءً على الأداء
  const getDQColor = (score) => {
    if (score >= 0.8) return '#00ff00'; // أخضر (ممتاز)
    if (score >= 0.6) return '#ffaa00'; // برتقالي (ضعيف)
    return '#ff3333'; // أحمر (كارثي)
  };

  return (
    <div style={{ padding: '20px', backgroundColor: '#0a0a0a', color: 'white', minHeight: '100vh', fontFamily: 'Arial' }}>
      
      <h1 style={{ borderBottom: '2px solid #333', paddingBottom: '10px' }}>
        PREDAIOT: Economic War Room (24-Hour Simulation)
      </h1>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '30px' }}>
        
        {/* بطاقة معامل جودة القرار DQ */}
        <div style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '10px', width: '30%' }}>
          <h3 style={{ color: '#888', margin: 0 }}>Decision Quality (DQ)</h3>
          <div style={{ fontSize: '48px', fontWeight: 'bold', color: getDQColor(data.dq_score) }}>
            {(data.dq_score * 100).toFixed(1)}%
          </div>
        </div>

        {/* بطاقة الفجوة الاقتصادية (عداد التسريب) */}
        <div style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '10px', width: '30%', border: '1px solid #ff3333' }}>
          <h3 style={{ color: '#ff3333', margin: 0 }}>Economic Gap (Lost $)</h3>
          <div style={{ fontSize: '48px', fontWeight: 'bold', color: '#ff3333' }}>
            -${data.total_gap_usd.toLocaleString()}
          </div>
        </div>

        {/* بطاقة القيمة المثلى */}
        <div style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '10px', width: '30%' }}>
          <h3 style={{ color: '#ffd700', margin: 0 }}>Optimal Potential</h3>
          <div style={{ fontSize: '48px', fontWeight: 'bold', color: '#ffd700' }}>
            ${data.edv_optimal_total.toLocaleString()}
          </div>
        </div>

      </div>

      {/* زر إعادة الحساب */}
      <button 
        onClick={fetchAuditData} 
        disabled={loading}
        style={{ padding: '10px 20px', backgroundColor: '#0056b3', color: 'white', border: 'none', borderRadius: '5px', cursor: loading ? 'not-allowed' : 'pointer', marginBottom: '20px', fontSize: '16px' }}
      >
        {loading ? 'Calculating 24-Hour MILP (288 Nodes)...' : 'Run PREDAIOT 24-Hour Engine'}
      </button>

      {/* التوأم الرقمي الاقتصادي (المنحنى الذهبي مقابل الأزرق) */}
      <div style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '10px' }}>
        <h3 style={{ marginBottom: '20px' }}>Economic Digital Twin (Actual vs Optimal over 24 Hours)</h3>
        <ResponsiveContainer width="100%" height={400}>
          <AreaChart data={data.decision_log} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              {/* تدرج لوني ذهبي للقرار الأمثل */}
              <linearGradient id="colorOpt" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffd700" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#ffd700" stopOpacity={0}/>
              </linearGradient>
              {/* تدرج لوني أزرق للقرار الفعلي */}
              <linearGradient id="colorAct" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#007bff" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#007bff" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis 
              dataKey="hour" 
              stroke="#888" 
              tickFormatter={(hourIndex) => {
                // تحويل المؤشر (0-288) إلى ساعات زمنية حقيقية لتبدو احترافية
                const hours = Math.floor(hourIndex / 12);
                const mins = (hourIndex % 12) * 5;
                return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
              }}
            />
            <YAxis stroke="#888" label={{ value: 'Value ($)', angle: -90, position: 'insideLeft' }} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#222', border: '1px solid #555' }}
              labelFormatter={(hourIndex) => {
                const hours = Math.floor(hourIndex / 12);
                const mins = (hourIndex % 12) * 5;
                return `Time: ${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
              }}
              formatter={(value, name) => [`$${value}`, name === 'edv_optimal_step' ? 'Optimal Value (d*)' : 'Actual Value (d_actual)']}
            />
            
            {/* المنحنى الذهبي (الغائب/المفقود) */}
            <Area type="monotone" dataKey="edv_optimal_step" stroke="#ffd700" fillOpacity={1} fill="url(#colorOpt)" strokeWidth={2} dot={false} />
            
            {/* المنحنى الأزرق (الواقع/المحقق) */}
            <Area type="monotone" dataKey="edv_actual_step" stroke="#007bff" fillOpacity={1} fill="url(#colorAct)" strokeWidth={2} dot={false} />
            
          </AreaChart>
        </ResponsiveContainer>
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#888' }}>
          * The shaded gap between the Gold (Optimal) and Blue (Actual) areas represents permanently lost revenue due to sub-optimal decisions.
        </div>
      </div>

    </div>
  );
}

export default App;