const STYLES = {
    DISCHARGE: {
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/50',
      text: 'text-emerald-400',
      icon: 'fa-bolt',
    },
    CHARGE: {
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/50',
      text: 'text-blue-400',
      icon: 'fa-arrow-down',
    },
    HOLD: {
      bg: 'bg-slate-800/30',
      border: 'border-slate-600',
      text: 'text-slate-400',
      icon: 'fa-pause-circle',
    },
    STOP: {
      bg: 'bg-red-500/10',
      border: 'border-red-500/50',
      text: 'text-red-400',
      icon: 'fa-hand',
    },
    ADJUST: {
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/50',
      text: 'text-orange-400',
      icon: 'fa-sliders-h',
    },
  };
  
  const SEVERITY_COLORS = {
    CRITICAL: '#ef4444',
    HIGH: '#f97316',
    MEDIUM: '#fbbf24',
    LOW: '#22c55e',
  };
  
  export default function RecommendationBanner({ data }) {
    if (!data) {
      return (
        <div className="rounded-xl p-5 border-2 border-slate-700 bg-slate-800/30">
          <div className="flex items-center gap-2 mb-2">
            <i className="fas fa-satellite-dish text-slate-600 text-sm" />
            <span className="text-[11px] font-mono font-bold tracking-[3px] text-slate-600">
              AWAITING DATA
            </span>
          </div>
          <div className="text-5xl font-extrabold font-mono text-slate-700 leading-none">
            --
          </div>
          <div className="text-[11px] text-slate-600 mt-3">
            Connect to SCADA stream or start demo
          </div>
        </div>
      );
    }
  
    const s = STYLES[data.recommendation] || STYLES.HOLD;
    const sevColor = SEVERITY_COLORS[data.severity] || '#475569';
    const isPulsing = data.severity === 'CRITICAL' || data.severity === 'HIGH';
  
    return (
      <div
        className={`relative overflow-hidden rounded-xl p-5 border-2 ${s.bg} ${s.border} transition-all duration-400`}
      >
        {/* Pulse ring for critical/high severity */}
        {isPulsing && (
          <div
            className="absolute inset-0 rounded-xl pointer-events-none"
            style={{
              animation: data.severity === 'CRITICAL'
                ? 'pulse-critical 1.5s infinite'
                : 'pulse-high 2s infinite',
            }}
          />
        )}
  
        <div className="relative z-10">
          {/* Label row */}
          <div className="flex items-center gap-2 mb-2">
            <i className={`fas ${s.icon} ${s.text} text-sm`} />
            <span
              className={`text-[11px] font-mono font-bold tracking-[3px] ${s.text}`}
            >
              {data.recommendation}
            </span>
          </div>
  
          {/* Power value */}
          <div className="flex items-baseline gap-1">
            <span className="text-5xl font-extrabold font-mono text-white leading-none">
              {data.recommended_power != null
                ? data.recommended_power.toFixed(1)
                : '--'}
            </span>
            <span className="text-sm font-mono text-slate-500">MW</span>
          </div>
  
          {/* Message */}
          <div className="text-[11px] text-slate-500 mt-3 leading-relaxed">
            {data.message}
          </div>
        </div>
      </div>
    );
  }