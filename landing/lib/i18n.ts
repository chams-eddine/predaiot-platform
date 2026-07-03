/**
 * PREDAIOT landing translations — EN / FR / AR.
 *
 * Add a new locale by:
 *   1. Adding its key to LOCALES + LOCALE_LABELS + IS_RTL.
 *   2. Adding a full block to `translations` — TypeScript will flag any
 *      missing keys because the shape is derived from translations.en.
 */

export type Locale = "en" | "fr" | "ar";

export const LOCALES: Locale[] = ["en", "fr", "ar"];

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  fr: "FR",
  ar: "AR",
};

export const IS_RTL: Record<Locale, boolean> = {
  en: false,
  fr: false,
  ar: true,
};

const en = {
  hero: {
    headlineLine1: "Stop Leaving Money",
    headlineLine2: "On The Table.",
    subheadline:
      "Get a free Economic Decision Audit™ for one asset. No CAPEX. No SCADA connection required.",
    ctaPrimary: "Start Free 7-Day Diagnostic",
    ctaSecondary: "Watch 2-Min Demo",
    trust1: "Bank-Level Encryption",
    trust2: "Zero SCADA Connection",
    trust3: "ISO 27001 Compliant",
  },
  proof: {
    headlineLine1: "See the Invisible",
    headlineLine2: "Financial Leakage.",
    subheadline:
      "Don't just monitor your assets. Audit every economic decision they make in real-time.",
    bullet1: "Pinpoint the exact dispatch decision that cost you capital.",
    bullet2:
      "Counterfactual Simulation: See what optimal would have yielded.",
    bullet3: "Actionable Economic Plan to close the gap immediately.",
    cta: "Explore the Math Methodology →",
    leakageLabel: "Live Leakage Detected",
    leakagePerHour: "/ hour",
  },
  social: {
    title: "Trusted by Energy Leaders & Independent Power Producers",
  },
  final: {
    headlineLine1: "The Universal Economic Engine",
    headlineLine2: "for Energy Infrastructure.",
    subheadline:
      "Stop guessing. Start auditing. Upload your data today and see the financial gap in seconds.",
    ctaDemo: "Run Demo Audit",
    ctaUpload: "Upload My Data",
  },
};

const fr: typeof en = {
  hero: {
    headlineLine1: "Arrêtez de laisser",
    headlineLine2: "de l'argent sur la table.",
    subheadline:
      "Obtenez un Audit de Décision Économique™ gratuit pour un actif. Aucun CAPEX. Aucune connexion SCADA requise.",
    ctaPrimary: "Démarrer le diagnostic gratuit 7 jours",
    ctaSecondary: "Regarder la démo (2 min)",
    trust1: "Chiffrement bancaire",
    trust2: "Aucune connexion SCADA",
    trust3: "Conforme ISO 27001",
  },
  proof: {
    headlineLine1: "Voyez la fuite financière",
    headlineLine2: "invisible.",
    subheadline:
      "Ne vous contentez pas de surveiller vos actifs. Auditez chaque décision économique qu'ils prennent en temps réel.",
    bullet1:
      "Identifiez la décision de dispatch exacte qui vous a coûté du capital.",
    bullet2:
      "Simulation contrefactuelle : voyez ce que la décision optimale aurait rapporté.",
    bullet3:
      "Plan Économique Actionnable pour combler l'écart immédiatement.",
    cta: "Explorer la méthodologie mathématique →",
    leakageLabel: "Fuite en direct détectée",
    leakagePerHour: "/ heure",
  },
  social: {
    title:
      "Approuvé par les leaders de l'énergie et les producteurs indépendants",
  },
  final: {
    headlineLine1: "Le moteur économique universel",
    headlineLine2: "pour l'infrastructure énergétique.",
    subheadline:
      "Cessez de deviner. Commencez à auditer. Chargez vos données aujourd'hui et voyez l'écart financier en secondes.",
    ctaDemo: "Lancer un audit de démonstration",
    ctaUpload: "Charger mes données",
  },
};

const ar: typeof en = {
  hero: {
    headlineLine1: "توقف عن ترك المال",
    headlineLine2: "على الطاولة.",
    subheadline:
      "احصل على تدقيق قرار اقتصادي™ مجاني لأحد الأصول. بدون نفقات رأسمالية. بدون اتصال بـ SCADA.",
    ctaPrimary: "ابدأ التشخيص المجاني لمدة 7 أيام",
    ctaSecondary: "شاهد العرض التوضيحي (دقيقتان)",
    trust1: "تشفير بمستوى البنوك",
    trust2: "بدون اتصال SCADA",
    trust3: "متوافق مع ISO 27001",
  },
  proof: {
    headlineLine1: "شاهد التسرب المالي",
    headlineLine2: "الخفي.",
    subheadline:
      "لا تكتفِ بمراقبة أصولك. دقّق كل قرار اقتصادي يتخذونه في الوقت الفعلي.",
    bullet1: "حدد بدقة قرار التوزيع الذي كلفك رأس المال.",
    bullet2: "المحاكاة الافتراضية: شاهد ما كان يمكن أن يحققه القرار الأمثل.",
    bullet3: "خطة اقتصادية قابلة للتنفيذ لإغلاق الفجوة فوراً.",
    cta: "← استكشاف المنهجية الرياضية",
    leakageLabel: "تم اكتشاف تسرب مباشر",
    leakagePerHour: "/ ساعة",
  },
  social: {
    title: "موثوق به من قادة الطاقة والمنتجين المستقلين للكهرباء",
  },
  final: {
    headlineLine1: "المحرك الاقتصادي الشامل",
    headlineLine2: "للبنية التحتية للطاقة.",
    subheadline:
      "توقف عن التخمين. ابدأ التدقيق. حمّل بياناتك اليوم وشاهد الفجوة المالية في ثوانٍ.",
    ctaDemo: "تشغيل تدقيق تجريبي",
    ctaUpload: "حمّل بياناتي",
  },
};

export const translations: Record<Locale, typeof en> = { en, fr, ar };
export type Translations = typeof en;
