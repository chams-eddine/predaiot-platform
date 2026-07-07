"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";

// Client-only BESS visualisation. Fallback is a plain dark box so the layout
// grid doesn't jump while the three.js chunk streams in.
const BessModel3D = dynamic(() => import("../three/BessModel3D"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-[#050505]" />,
});

// Official platform — the "Explore Math Methodology" CTA opens the
// audit app's Math Appendix section.
const APP_URL = "https://platform.preda-iot.com/";

export default function ProofSection() {
  return (
    <section className="relative w-full py-32 bg-[#050505] overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center">
        {/* LEFT — marketing copy */}
        <motion.div
          initial={{ opacity: 0, x: -50 }}
          whileInView={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          viewport={{ once: true, amount: 0.5 }}
        >
          <h2 className="text-4xl md:text-5xl font-extrabold text-white leading-tight mb-8">
            See the Invisible
            <br />
            <span className="text-[#FF3366] drop-shadow-[0_0_15px_rgba(255,51,102,0.5)]">
              Financial Leakage.
            </span>
          </h2>

          <p className="text-gray-400 text-lg mb-10 leading-relaxed">
            Don&apos;t just monitor your assets. Audit every economic decision they
            make in real-time.
          </p>

          <ul className="space-y-6">
            {[
              "Pinpoint the exact dispatch decision that cost you capital.",
              "Counterfactual Simulation: See what optimal would have yielded.",
              "Actionable Economic Plan to close the gap immediately.",
            ].map((text, index) => (
              <motion.li
                key={text}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.2, duration: 0.5 }}
                viewport={{ once: true }}
                className="flex items-start gap-4"
              >
                <div className="mt-1 flex-shrink-0 w-5 h-5 rounded-full bg-[#00FFFF]/20 flex items-center justify-center">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#00FFFF]" />
                </div>
                <span className="text-gray-300 text-lg">{text}</span>
              </motion.li>
            ))}
          </ul>

          <motion.a
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            href={`${APP_URL}#math-methodology`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-12 px-8 py-4 border border-gray-700 text-gray-300 font-medium rounded-lg hover:border-[#00FFFF] hover:text-[#00FFFF] transition-all duration-300"
          >
            Explore the Math Methodology →
          </motion.a>
        </motion.div>

        {/* RIGHT — 3D BESS asset with floating leakage tooltip overlay */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, ease: "easeOut" }}
          viewport={{ once: true, amount: 0.3 }}
          className="relative h-[400px] md:h-[500px] w-full"
        >
          <div className="absolute inset-0">
            <BessModel3D />
          </div>

          {/* Floating tooltip — pinned above the battery, animated in on scroll */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.5 }}
            viewport={{ once: true }}
            className="absolute top-[15%] left-1/2 -translate-x-1/2 z-10 pointer-events-none"
          >
            <div className="bg-black/90 backdrop-blur-md border border-red-500/50 text-white px-5 py-3 rounded-xl whitespace-nowrap font-mono shadow-[0_0_25px_rgba(255,51,102,0.4)]">
              <div className="flex items-center gap-2 mb-1">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                </span>
                <span className="text-red-400 text-xs font-sans uppercase tracking-widest">
                  Live Leakage Detected
                </span>
              </div>
              <div className="text-2xl font-bold text-red-500">
                -$1,205{" "}
                <span className="text-sm text-gray-500 font-normal">/ hour</span>
              </div>
              <div className="text-[10px] text-gray-600 mt-1 font-sans normal-case tracking-normal">
                Illustrative demo figure — not measured data
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
