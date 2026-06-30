export default function DQGauge({ value = 0, size = 200 }) {
    const radius = 80;
    const arcLength = Math.PI * radius; // ~251.3
    const clamped = Math.min(100, Math.max(0, value));
    const offset = arcLength * (1 - clamped / 100);
  
    const color = clamped > 70 ? '#22c55e' : clamped > 40 ? '#fbbf24' : '#ef4444';
    const textColor = clamped > 70 ? '#22c55e' : clamped > 40 ? '#fbbf24' : '#ef4444';
  
    return (
      <div className="text-center">
        <div className="text-[10px] tracking-[2px] uppercase text-slate-500 mb-2">
          Decision Quality Index
        </div>
        <svg
          viewBox={`0 0 ${size} ${size * 0.575}`}
          className="w-full max-w-[220px] mx-auto"
        >
          {/* Background arc */}
          <path
            d={`M 20 ${size * 0.5} A ${radius} ${radius} 0 0 1 ${size - 20} ${size * 0.5}`}
            fill="none"
            stroke="#1a2435"
            strokeWidth="14"
            strokeLinecap="round"
          />
          {/* Value arc */}
          <path
            d={`M 20 ${size * 0.5} A ${radius} ${radius} 0 0 1 ${size - 20} ${size * 0.5}`}
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={arcLength}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.5s ease' }}
          />
          {/* Value text */}
          <text
            x={size / 2}
            y={size * 0.4}
            textAnchor="middle"
            fill={textColor}
            fontFamily="JetBrains Mono, monospace"
            fontSize="32"
            fontWeight="700"
          >
            {value.toFixed(1)}
          </text>
          <text
            x={size / 2}
            y={size * 0.49}
            textAnchor="middle"
            fill="#334155"
            fontFamily="JetBrains Mono, monospace"
            fontSize="10"
          >
            %
          </text>
        </svg>
      </div>
    );
  }