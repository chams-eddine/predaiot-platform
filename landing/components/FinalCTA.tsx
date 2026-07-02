'use client';

import { motion } from 'framer-motion';
import { ArrowRight, Zap } from 'lucide-react';

/**
 * The last push. Framed in a card with a soft gradient border to feel like
 * a "premium terminal" — deliberate visual contrast with the wide-open
 * sections above. Two CTAs: Run Demo (secondary, low friction) and Upload
 * My Data (primary, real-audit intent).
 */

export default function FinalCTA() {
  return (
    <section
      className="relative ps-6 pe-6 py-24 md:py-32"
      aria-labelledby="final-cta-heading"
    >
      <div className="max-w-5xl mx-auto">
        {/* Gradient-border wrapper */}
        <div
          className="
            relative rounded-3xl p-[1.5px]
            bg-gradient-to-br from-brand-cyan/40 via-white/5 to-brand-red/30
          "
        >
          <div
            className="
              relative rounded-3xl overflow-hidden
              bg-gradient-to-b from-canvas-card via-canvas to-canvas-raised
              p-10 md:p-16 lg:p-20 text-center
            "
          >
            {/* Ambient radial */}
            <div
              className="absolute inset-0 bg-radial-cyan opacity-40 pointer-events-none"
              aria-hidden="true"
            />

            <motion.h2
              id="final-cta-heading"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              className="
                relative text-4xl md:text-5xl lg:text-6xl
                font-bold tracking-tight leading-[1.05]
                mb-6
              "
            >
              <span className="text-gradient-cyan">
                The Universal Economic Engine
              </span>
              <br />
              <span className="text-white">for Energy Infrastructure.</span>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.9, delay: 0.15 }}
              className="
                relative text-base md:text-lg
                text-white/60 max-w-2xl mx-auto
                mb-12
              "
            >
              BESS · Solar · Wind · Hydrogen · Gas · Hydro · Desalination.
              <br className="hidden sm:block" />
              One engine. Every asset class. Every dispatch decision, audited.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.9, delay: 0.3 }}
              className="
                relative flex flex-col sm:flex-row
                gap-4 justify-center items-center
              "
            >
              <a
                href="#demo"
                className="
                  inline-flex items-center gap-3
                  ps-8 pe-8 py-4
                  border border-white/20 text-white font-medium
                  rounded-lg backdrop-blur-sm
                  hover:border-white/40 hover:bg-white/5
                  transition-all duration-300
                "
              >
                <Zap className="w-4 h-4" aria-hidden="true" />
                <span>Run Demo Audit</span>
              </a>

              <a
                href="#upload"
                className="
                  group inline-flex items-center gap-3
                  ps-8 pe-8 py-4
                  bg-brand-cyan text-black font-bold
                  rounded-lg
                  shadow-glow-cyan hover:shadow-glow-cyan-lg
                  transition-all duration-300
                  hover:-translate-y-0.5
                "
              >
                <span>Upload My Data</span>
                <ArrowRight
                  className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1 rtl:group-hover:-translate-x-1 rtl:rotate-180"
                  aria-hidden="true"
                />
              </a>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.9, delay: 0.5 }}
              className="relative mt-10 text-xs text-white/40 tracking-wider"
            >
              CSV upload · Free 7-day diagnostic · Confidentiality NDA on request
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
