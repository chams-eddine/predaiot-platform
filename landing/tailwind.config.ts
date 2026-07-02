import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // PREDAIOT operations-console palette. Deep bg, cyan brand, alert red.
        canvas: {
          DEFAULT: '#050505',
          raised:  '#0A0A0A',
          card:    '#0A1420',
          hairline:'rgba(255,255,255,0.06)',
        },
        brand: {
          cyan:    '#00FFFF',
          cyanDim: '#4DDDDD',
          red:     '#FF3366',
          amber:   '#FFB020',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        // Electric-cyan primary CTA glow. Two intensities for hover.
        'glow-cyan':    '0 0 40px rgba(0, 255, 255, 0.35), 0 0 12px rgba(0, 255, 255, 0.15)',
        'glow-cyan-lg': '0 0 60px rgba(0, 255, 255, 0.60), 0 0 20px rgba(0, 255, 255, 0.30)',
        'glow-red':     '0 0 30px rgba(255, 51, 102, 0.30)',
      },
      backgroundImage: {
        'radial-cyan':   'radial-gradient(circle at center, rgba(0, 255, 255, 0.10), transparent 60%)',
        'radial-red':    'radial-gradient(circle at center, rgba(255, 51, 102, 0.10), transparent 60%)',
        'grid-fade':     'linear-gradient(180deg, transparent, rgba(0,0,0,0.85))',
      },
      animation: {
        'pulse-slow':  'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer':     'shimmer 3s linear infinite',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
