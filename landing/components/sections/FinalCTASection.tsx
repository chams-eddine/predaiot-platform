"use client";

import { motion } from "framer-motion";
import { useLanguage } from "@/lib/LanguageContext";

const APP_URL = "https://platform.preda-iot.com/";

export default function FinalCTASection() {
  const { t } = useLanguage();

  return (
    <section className="w-full py-32 bg-[#050505] relative overflow-hidden">
      {/* Ambient radial glow behind the card */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,255,255,0.05)_0%,transparent_70%)]" />

      <div className="relative z-10 max-w-4xl mx-auto px-6">
        {/* Gradient-border card wrapper */}
        <div className="bg-gradient-to-r from-[#00FFFF] via-[#00FFFF]/20 to-[#FF3366] p-[1px] rounded-2xl shadow-[0_0_40px_rgba(0,255,255,0.1)]">
          <div className="bg-[#0A0A0A] rounded-2xl px-8 py-16 md:py-20 text-center">
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              viewport={{ once: true }}
              className="text-3xl md:text-5xl font-extrabold text-white leading-tight mb-6"
            >
              {t.final.headlineLine1}
              <br />
              <span className="text-glow-cyan">{t.final.headlineLine2}</span>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              viewport={{ once: true }}
              className="text-gray-400 text-lg mb-10 max-w-2xl mx-auto"
            >
              {t.final.subheadline}
            </motion.p>

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              viewport={{ once: true }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <a
                href={APP_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 border border-gray-600 text-white font-medium rounded-lg hover:border-white transition-all duration-300"
              >
                {t.final.ctaDemo}
              </a>

              <a
                href={APP_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 bg-[#00FFFF] text-black font-bold rounded-lg hover:bg-white transition-colors duration-300 shadow-[0_0_20px_rgba(0,255,255,0.4)]"
              >
                {t.final.ctaUpload}
              </a>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
