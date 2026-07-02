'use client';

import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

/**
 * Split layout — the "invisible leakage" pitch. Left column is the 3D BESS
 * with the floating leakage tooltip; right column is three high-signal
 * bullets. On mobile we stack, with the 3D under the bullets so the pitch
 * lands first-scroll.
 */

const InteractiveAsset3D = dynamic(() => import('./InteractiveAsset3D'), {
  ssr: false,
  loading: () => (
    <div
      className="
        w-full aspect-square md:aspect-[4/3] lg:aspect-square
        rounded-2xl bg-canvas-card border border-canvas-hairline
      "
    />
  ),
});

const BULLETS = [
  {
    title: 'Pinpoint the exact dispatch decision that cost you capital.',
    detail:
      'Every step. Every override. Timestamped, priced, and attributed to a root cause.',
  },
  {
    title: 'Counterfactual Simulation: See what optimal would have yielded.',
    detail:
      'MILP-optimal dispatch against your own price series — the ceiling, not a benchmark.',
  },
  {
    title: 'Actionable Economic Plan to close the gap.',
    detail:
      '5-item prioritised action plan with owner, payback, and expected annual gain.',
  },
];

export default function ProofSection() {
  return (
    <section
      className="relative ps-6 pe-6 py-24 md:py-32"
      aria-labelledby="proof-heading"
    >
      <div
        className="
          max-w-6xl mx-auto
          grid grid-cols-1 lg:grid-cols-2
          gap-12 lg:gap-20 items-center
        "
      >
        {/* LEFT — 3D visualisation */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="order-2 lg:order-1"
        >
          <InteractiveAsset3D />
        </motion.div>

        {/* RIGHT — headline + bullets */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className="order-1 lg:order-2 text-start"
        >
          <div className="inline-flex items-center gap-2 ps-3 pe-3 py-1 mb-6 rounded-full border border-brand-red/30 bg-brand-red/5">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-red" />
            <span className="text-[10px] tracking-[0.25em] text-brand-red font-semibold uppercase">
              What SCADA Doesn&rsquo;t Show You
            </span>
          </div>

          <h2
            id="proof-heading"
            className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.05] mb-8"
          >
            <span className="text-gradient-cyan">See the Invisible</span>
            <br />
            <span className="text-gradient-red">Financial Leakage.</span>
          </h2>

          <p className="text-base md:text-lg text-white/60 leading-relaxed mb-10 max-w-xl">
            SCADA tells you the asset ran. It doesn&rsquo;t tell you whether
            running was the right economic decision. That gap — the one you
            can&rsquo;t see on any dashboard you own today — is where the money
            goes.
          </p>

          <ul className="space-y-6">
            {BULLETS.map(({ title, detail }, i) => (
              <motion.li
                key={title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: 0.7, delay: 0.25 + i * 0.12 }}
                className="flex items-start gap-4"
              >
                <div
                  className="
                    flex-shrink-0 mt-0.5
                    w-7 h-7 rounded-full
                    bg-brand-cyan/10 border border-brand-cyan/40
                    flex items-center justify-center
                    shadow-[0_0_16px_rgba(0,255,255,0.25)]
                  "
                >
                  <Check
                    className="w-4 h-4 text-brand-cyan"
                    strokeWidth={3}
                    aria-hidden="true"
                  />
                </div>
                <div className="min-w-0">
                  <div className="text-lg md:text-xl text-white font-semibold leading-snug">
                    {title}
                  </div>
                  <div className="text-sm text-white/50 mt-1 leading-relaxed">
                    {detail}
                  </div>
                </div>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      </div>
    </section>
  );
}
