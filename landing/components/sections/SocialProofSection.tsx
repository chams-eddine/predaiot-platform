"use client";

import { motion } from "framer-motion";
import { useLanguage } from "@/lib/LanguageContext";

// Asset classes the engine audits — factual capability claims. The previous
// list showed invented company names implying customers that do not exist
// (docs/REMOVED_HEURISTICS.md); real logos go here once customers sign.
const partners = [
  "BESS & Storage",
  "Solar PV",
  "Wind",
  "Gas & Thermal",
  "Green Hydrogen",
  "Desalination",
];

export default function SocialProofSection() {
  const { t } = useLanguage();

  return (
    <section className="w-full py-20 bg-[#050505] border-t border-b border-gray-800/50">
      <div className="max-w-7xl mx-auto px-6">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center text-gray-500 text-sm uppercase tracking-widest mb-10"
        >
          {t.social.title}
        </motion.p>

        <div className="flex flex-wrap justify-center items-center gap-x-12 gap-y-6">
          {partners.map((name, index) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.4 }}
              viewport={{ once: true }}
              className="text-xl font-bold text-gray-700 hover:text-gray-400 transition-colors duration-300 cursor-default select-none"
              style={{
                fontFamily: "system-ui, sans-serif",
                letterSpacing: "0.05em",
              }}
            >
              {name}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
