"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import {
  IS_RTL,
  LOCALES,
  Locale,
  Translations,
  translations,
} from "./i18n";

interface LanguageContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translations;
  isRtl: boolean;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(
  undefined,
);

const STORAGE_KEY = "predaiot.locale";

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Default to English so the static-export first paint is deterministic;
  // the effect below swaps to the stored / browser-preferred locale on hydration.
  const [locale, setLocaleState] = useState<Locale>("en");

  // On first client render, resolve the actual locale.
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (stored && LOCALES.includes(stored)) {
        setLocaleState(stored);
        return;
      }
      // Fall back to browser language when no preference stored.
      const browserLang = navigator.language.slice(0, 2).toLowerCase();
      if (LOCALES.includes(browserLang as Locale)) {
        setLocaleState(browserLang as Locale);
      }
    } catch {
      // localStorage / navigator may be unavailable — English stays.
    }
  }, []);

  // Whenever locale changes, sync <html lang> + <html dir> so RTL applies
  // globally + assistive tech reads the right language.
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute(
      "dir",
      IS_RTL[locale] ? "rtl" : "ltr",
    );
    document.documentElement.setAttribute("lang", locale);
  }, [locale]);

  const setLocale = (next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage full / disabled — the choice just won't persist.
    }
  };

  const value: LanguageContextValue = {
    locale,
    setLocale,
    t: translations[locale],
    isRtl: IS_RTL[locale],
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used inside <LanguageProvider>.");
  }
  return ctx;
}
