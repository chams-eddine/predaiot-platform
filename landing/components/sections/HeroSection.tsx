"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";

// Load the 3D core lazily, no SSR. The Canvas absolutely must not block
// hydration or first paint — Hero copy has to be visible immediately.
const EconomicCore3D = dynamic(() => import("../three/EconomicCore3D"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-[#050505]" />,
});

// Prospect deep-link into the live audit app. Both hero CTAs target this
// URL — the trial gate handles routing from there.
const APP_URL = "https://predaiot-platform.onrender.com/";
const DEMO_MAILTO =
  "mailto:chams@preda-iot.com?subject=PREDAIOT%20Demo%20Request&body=Hi%20Chams%2C%0A%0AI%27d%20like%20to%20see%20a%20live%20demo%20of%20PREDAIOT.%20My%20asset%20class%20is%3A%20%5BBESS%20%2F%20Solar%20%2F%20Wind%20%2F%20Gas%20%2F%20Hydro%20%2F%20other%5D.";

export default function HeroSection() {
  return (
    <section className="relative w-full h-screen flex items-center justify-center overflow-hidden bg-[#050505]">
      {/* 1. 3D backdrop — the "Economic Core". */}
      <EconomicCore3D />

      {/* 2. Vertical fade for legibility over the 3D scene. */}
      <div className="absolute inset-0 z-10 bg-gradient-to-b from-transparent via-[#050505]/70 to-[#050505]" />

      {/* 3. Foreground copy. */}
      <div className="relative z-20 text-center px-6 max-w-4xl">
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-5xl md:text-7xl font-extrabold tracking-tight text-white leading-tight"
        >
          Stop Leaving Money
          <br />
          <span className="text-glow-cyan">On The Table.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
          className="mt-6 text-lg md:text-xl text-gray-400 max-w-2xl mx-auto"
        >
          Get a free Economic Decision Audit™ for one asset. No CAPEX. No SCADA
          connection required.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-10 flex flex-col sm:flex-row gap-4 justify-center"
        >
          <a
            href={APP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="px-8 py-4 bg-[#00FFFF] text-black font-bold rounded-lg hover:bg-white transition-colors duration-300 shadow-[0_0_20px_rgba(0,255,255,0.4)]"
          >
            Start Free 7-Day Diagnostic
          </a>

          <a
            href={DEMO_MAILTO}
            className="px-8 py-4 border border-gray-600 text-white font-medium rounded-lg hover:border-[#00FFFF] hover:text-[#00FFFF] transition-all duration-300"
          >
            Watch 2-Min Demo
          </a>
        </motion.div>
      </div>

      {/* 4. Trust bar — bottom-anchored objection handling. */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
        className="absolute bottom-10 z-20 w-full flex justify-center px-4"
      >
        <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-xs text-gray-500">
          <span className="flex items-center gap-2">
            <svg
              className="w-4 h-4 text-green-500"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            Bank-Level Encryption
          </span>
          <span className="flex items-center gap-2">
            <svg
              className="w-4 h-4 text-green-500"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            Zero SCADA Connection
          </span>
          <span className="flex items-center gap-2">
            <svg
              className="w-4 h-4 text-green-500"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            ISO 27001 Compliant
          </span>
        </div>
      </motion.div>
    </section>
  );
}
