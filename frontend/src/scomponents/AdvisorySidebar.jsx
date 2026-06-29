import { useState } from 'react';
import RecommendationBanner from './RecommendationBanner';
import DQGauge from './DQGauge';

const RATING_COLORS = {
  AAA: '#22c55e', AA: '#4ade80', A: '#86efac',
  BBB: '#fbbf24', BB: '#f97316', B: '#ef4444', CCC: '#dc2626',
};

const RATING_LABELS = {
  AAA: 'Excellent', AA: 'Very Good', A: 'Good',
  BBB: 'Acceptable', BB: 'Below Average', B: 'Poor', CCC: 'Critical',
};

const SEVERITY_COLORS = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24', LOW: '#22c55e',
};

export default function AdvisorySidebar({
  step,
  connected,
  onStartDemo,
  onStopDemo,
  isDemoRunning,
}) {
  const [showSettings, setShowSettings] = useState(false);
  const [wsUrl, setWsUrl] = useState('');

  const d = step;

  const handleConnect = () => {
    if (wsUrl) {
      // Dispatch custom event or call parent connect function
      window.dispatchEvent(new CustomEvent('predaiot:ws-connect', { detail: wsUrl }));
      setShowSettings(false);
    }
  };

  const handleDisconnect = () => {
    window.dispatchEvent(new CustomEvent('predaiot:ws-disconnect'));
    setShowSettings(false);
  };

  return (
    <>
      <aside className="w-[320px] flex-shrink-0 border-r border-[#1a2435] bg-[#060a13] overflow-y-auto p-4 flex flex-col gap-4">
        {/* Connection Banner */}
        <div className="text-center py-2 px-3 rounded-lg bg-[#111827] border border-[#1a2435]">
          <div className="text-[10px] tracking-[2px] text-slate-500">
            {connected ? 'LIVE STREAM' : isDemoRunning ? 'DEMO MODE' : 'OBSERVATION MODE'}
          </div>
          <div
            className={`text-xs font-mono mt-0.5 ${
              connected ? 'text-emerald-400' : isDemoRunning ? 'text-cyan-400' : 'text-slate-500'
            }`}
          >
            {connected ? 'SCADA Connected' : isDemoRunning ? 'Simulation Active' : 'Economic Advisory Observer'}
          </div>
        </div>

        {/* ─── RECOMMENDATION BANNER ─── */}
        <RecommendationBanner data={d} />

        {/* ─── EXPECTED GAIN & CONFIDENCE ─── */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-[#111827] border border-[#1a2435] rounded-lg p-3">
            <div className="text-[10px] tracking-[1.5px] uppercase text-slate-500">
              Expected Gain
            </div>
            <div
              className={`font-mono font-semibold text-lg mt-1 ${
                (d?.expected_gain || 0) > 0 ? 'text-emerald-400' : 'text-slate-400'
              }`}
            >
              ${d?.expected_gain?.toFixed(2) || '0.00'}
            </div>
          </div>
          <div className="bg-[#111827] border border-[#1a2435] rounded-lg p-3">
            <div className="text-[10px] tracking-[1.5px] uppercase text-slate-500">
              Confidence
            </div>
            <div className="flex items-center gap-2 mt-2">
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${d?.confidence || 0}%`,
                    background:
                      (d?.confidence || 0) > 90
                        ? '#22c55e'
                        : (d?.confidence || 0) > 70
                        ? '#fbbf24'
                        : '#ef4444',
                  }}
                />
              </div>
              <span
                className="font-mono text-sm font-semibold"
                style={{
                  color:
                    (d?.confidence || 0) > 90
                      ? '#22c55e'
                      : (d?.confidence || 0) > 70
                      ? '#fbbf24'
                      : '#ef4444',
                }}
              >
                {d?.confidence?.toFixed(1) || '0'}%
              </span>
            </div>
          </div>
        </div>

        {/* ─── SEVERITY ─── */}
        <div className="bg-[#111827] border border-[#1a2435] rounded-lg p-3 flex items-center justify-between">
          <span className="text-[10px] tracking-[1.5px] uppercase text-slate-500">
            Severity
          </span>
          <div className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: SEVERITY_COLORS[d?.severity] || '#475569' }}
            />
            <span
              className="font-mono text-sm font-semibold"
              style={{ color: SEVERITY_COLORS[d?.severity] || '#475569' }}
            >
              {d?.severity || '--'}
            </span>
          </div>
        </div>

        <hr className="border-[#1a2435]" />

        {/* ─── ECONOMIC RATING BADGE ─── */}
        <div className="text-center">
          <div className="text-[10px] tracking-[1.5px] uppercase text-slate-500 mb-3">
            Economic Decision Rating
          </div>
          <div
            className="inline-flex items-center justify-center w-20 h-20 rounded-2xl border-2"
            style={{
              borderColor: (RATING_COLORS[d?.rating] || '#475569') + '80',
              background: (RATING_COLORS[d?.rating] || '#475569') + '15',
            }}
          >
            <span
              className="text-4xl font-extrabold font-mono"
              style={{ color: RATING_COLORS[d?.rating] || '#475569' }}
            >
              {d?.rating || '--'}
            </span>
          </div>
          <div
            className="text-[11px] mt-2"
            style={{ color: (RATING_COLORS[d?.rating] || '#475569') + 'cc' }}
          >
            {RATING_LABELS[d?.rating] || 'No Audit Data'}
          </div>
        </div>

        <hr className="border-[#1a2435]" />

        {/* ─── DQ GAUGE ─── */}
        <DQGauge value={d?.dq_score_live || 0} />

        <hr className="border-[#1a2435]" />

        {/* ─── CUMULATIVE VALUE LEAKAGE ─── */}
        <div className="bg-[#111827] border border-[#1a2435] rounded-lg p-3">
          <div className="text-[10px] tracking-[1.5px] uppercase text-slate-500">
            Cumulative Value Leakage
          </div>
          <div
            className={`font-mono font-semibold text-2xl mt-1 ${
              (d?.cumulative_gap || 0) > 0 ? 'text-red-400' : 'text-slate-400'
            }`}
          >
            ${(d?.cumulative_gap || 0).toFixed(2)}
          </div>
          <div className="flex items-center gap-1 mt-1.5">
            <i className="fas fa-arrow-down text-[9px] text-red-500" />
            <span className="text-[11px] font-mono text-red-400">
              ${d?.cumulative_gap ? (d.cumulative_gap / Math.max(0.1, (d.dq_score_live ? 1 : 0.1))).toFixed(2) : '0.00'}/h
            </span>
          </div>
        </div>

        {/* ─── MARKET CONTEXT ─── */}
        <div className="bg-[#111827] border border-[#1a2435] rounded-lg p-3 space-y-2">
          <div className="flex justify-between">
            <span className="text-[10px] tracking-[1.5px] uppercase text-slate-500">Market Price</span>
            <span className="font-mono text-sm text-slate-400">
              ${d?.price?.toFixed(2) || '--'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[10px] tracking-[1.5px] uppercase text-slate-500">Steps Processed</span>
            <span className="font-mono text-sm text-slate-400">
              {d?.step || 0}
            </span>
          </div>
        </div>

        {/* ─── QUICK ACTIONS ─── */}
        <div className="mt-auto space-y-2">
          {!isDemoRunning ? (
            <button
              onClick={onStartDemo}
              className="w-full py-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-sm font-semibold hover:bg-cyan-500/20 transition flex items-center justify-center gap-2"
            >
              <i className="fas fa-play text-xs" /> Start Demo Simulation
            </button>
          ) : (
            <button
              onClick={onStopDemo}
              className="w-full py-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-semibold hover:bg-red-500/20 transition flex items-center justify-center gap-2"
            >
              <i className="fas fa-stop text-xs" /> Stop Simulation
            </button>
          )}
          <button
            onClick={() => setShowSettings(true)}
            className="w-full py-2 rounded-lg bg-[#111827] border border-[#1a2435] text-slate-500 text-xs hover:text-slate-300 hover:border-slate-600 transition flex items-center justify-center gap-2"
          >
            <i className="fas fa-plug text-[10px]" /> Connect WebSocket
          </button>
        </div>
      </aside>

      {/* ─── SETTINGS MODAL ─── */}
      {showSettings && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
          onClick={() => setShowSettings(false)}
        >
          <div
            className="bg-[#0d1219] border border-[#1a2435] rounded-xl p-6 w-[420px]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-bold text-white">Connection Settings</h3>
              <button
                onClick={() => setShowSettings(false)}
                className="text-slate-500 hover:text-white"
              >
                <i className="fas fa-times" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-[10px] tracking-[1.5px] uppercase text-slate-500 block mb-1.5">
                  WebSocket URL
                </label>
                <input
                  type="text"
                  value={wsUrl}
                  onChange={(e) => setWsUrl(e.target.value)}
                  placeholder="ws://localhost:8000/ws/live"
                  className="w-full px-3 py-2 bg-[#111827] border border-[#1a2435] rounded-lg text-sm font-mono text-slate-300 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleConnect}
                  className="flex-1 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-sm font-semibold hover:bg-cyan-500/20 transition"
                >
                  Connect
                </button>
                <button
                  onClick={handleDisconnect}
                  className="flex-1 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-semibold hover:bg-red-500/20 transition"
                >
                  Disconnect
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}