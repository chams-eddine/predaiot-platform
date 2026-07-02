'use client';

import { motion } from 'framer-motion';
import dynamic from 'next/dynamic';
import { ArrowRight, Play } from 'lucide-react';

/**
 * 3D hero backdrop — lazy-loaded, client-only, non-blocking. Falls back to a
 * pure-CSS gradient during load so First Contentful Paint isn't gated on
 * three.js download.
 */
const HeroBackground3D = dynamic(
  () => import('./HeroBackground3D'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gradient-to-b from-canvas via-[#0A1420] to-canvas" />
    ),
  }
);

export default function HeroSection() {
  return (
    <section
      className="
        relative overflow-hidden
        min-h-screen flex items-center justify-center
        ps-6 pe-6 md:ps-12 md:pe-12
        pt-24 pb-24
      "
    >
      {/* 3D backdrop — subtle, non-distracting */}
      <div className="absolute inset-0 opacity-60" aria-hidden="true">
        <HeroBackground3D />
      </div>

      {/* Radial spotlight over the CTA to lift it off the 3D field */}
      <div
        className="absolute inset-0 pointer-events-none bg-radial-cyan"
        aria-hidden="true"
      />

      {/* Static dot-grid overlay for texture */}
      <div
        className="absolute inset-0 pointer-events-none bg-dot-grid opacity-40"
        aria-hidden="true"
      />

      {/* Content */}
      <div className="relative z-10 max-w-6xl text-center">
        {/* Pre-headline chip */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="inline-flex items-center gap-2 ps-4 pe-4 py-1.5 mb-8 rounded-full border border-brand-cyan/30 bg-brand-cyan/5 backdrop-blur-sm"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan shadow-[0_0_8px_rgba(0,255,255,0.8)] animate-pulse" />
          <span className="text-xs tracking-[0.2em] text-brand-cyan font-semibold uppercase">
            Economic Decision Audit™ · Now Live
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="
            text-5xl sm:text-6xl md:text-7xl lg:text-[7.5rem]
            font-black tracking-tight leading-[0.95]
            mb-6
          "
        >
          <span className="text-gradient-cyan block">Stop Leaving Money</span>
          <span className="text-gradient-cyan block">on the Table.</span>
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.3, ease: 'easeOut' }}
          className="
            text-lg sm:text-xl md:text-2xl
            text-white/70 max-w-3xl mx-auto
            mb-12 leading-relaxed
          "
        >
          Get a free{' '}
          <span className="text-white font-semibold">Economic Decision Audit™</span>{' '}
          for one asset.
          <br className="hidden sm:block" />
          <span className="text-white/90">
            No CAPEX. No SCADA connection required.
          </span>
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.5, ease: 'easeOut' }}
          className="flex flex-col sm:flex-row gap-4 justify-center items-center"
        >
          {/* Primary CTA → live audit app on Render. Opens in new tab so
              the landing stays open behind it (higher return-to-landing rate). */}
          <a
            href="https://predaiot-platform.onrender.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="
              group relative inline-flex items-center gap-3
              ps-8 pe-8 py-4
              bg-brand-cyan text-black font-bold text-base
              rounded-lg
              shadow-glow-cyan hover:shadow-glow-cyan-lg
              transition-all duration-300
              hover:-translate-y-0.5
            "
          >
            <span>Start Free 7-Day Diagnostic</span>
            <ArrowRight
              className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1 rtl:group-hover:-translate-x-1 rtl:rotate-180"
              aria-hidden="true"
            />
            {/* Shimmer sweep */}
            <span
              className="
                absolute inset-0 rounded-lg overflow-hidden pointer-events-none
                bg-gradient-to-r from-transparent via-white/25 to-transparent
                opacity-0 group-hover:opacity-100 group-hover:animate-shimmer
                bg-[length:200%_100%]
              "
              aria-hidden="true"
            />
          </a>

          {/* Secondary CTA — no demo video exists yet, so this is a mailto
              rather than a link that scrolls to nothing. Honest > slick. */}
          <a
            href="mailto:chams@preda-iot.com?subject=PREDAIOT%20Demo%20Request&body=Hi%20Chams%2C%0A%0AI%27d%20like%20to%20see%20a%20live%20demo%20of%20PREDAIOT.%20My%20asset%20class%20is%3A%20%5BBESS%20%2F%20Solar%20%2F%20Wind%20%2F%20Gas%20%2F%20Hydro%20%2F%20other%5D."
            className="
              inline-flex items-center gap-3
              ps-8 pe-8 py-4
              border border-white/20 text-white font-medium text-base
              rounded-lg backdrop-blur-sm
              hover:border-white/40 hover:bg-white/5
              transition-all duration-300
            "
          >
            <Play className="w-4 h-4" aria-hidden="true" />
            <span>Watch 2-Min Demo</span>
          </a>
        </motion.div>

        {/* Micro-proof under CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.9, delay: 0.8 }}
          className="mt-10 text-xs text-white/40 tracking-wider"
        >
          CSV upload · Results in 24h · Confidentiality guaranteed
        </motion.div>
      </div>

      {/* Bottom fade into TrustBanner */}
      <div
        className="absolute bottom-0 inset-x-0 h-40 bg-gradient-to-t from-canvas to-transparent pointer-events-none"
        aria-hidden="true"
      />
    </section>
  );
}
