"use client";

import { useLanguage } from "@/lib/LanguageContext";
import { LOCALE_LABELS, LOCALES } from "@/lib/i18n";

/**
 * Floating language switcher — top-right corner (mirrored to top-left in RTL
 * because we use logical top-4 + start-4). Three pill buttons EN / FR / AR
 * with active state highlighted in brand cyan.
 */
export default function LanguageSwitcher() {
  const { locale, setLocale } = useLanguage();

  return (
    <div
      className="fixed top-4 end-4 z-50 flex gap-1 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-1 py-1 shadow-[0_0_20px_rgba(0,0,0,0.6)]"
      role="group"
      aria-label="Language selector"
    >
      {LOCALES.map((l) => {
        const active = locale === l;
        return (
          <button
            key={l}
            onClick={() => setLocale(l)}
            aria-pressed={active}
            className={
              "px-3 py-1 rounded-full text-xs font-bold tracking-widest transition-all duration-200 " +
              (active
                ? "bg-[#00FFFF] text-black shadow-[0_0_15px_rgba(0,255,255,0.5)]"
                : "text-gray-400 hover:text-white")
            }
          >
            {LOCALE_LABELS[l]}
          </button>
        );
      })}
    </div>
  );
}
