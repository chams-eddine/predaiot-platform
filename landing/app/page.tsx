import HeroSection from "@/components/sections/HeroSection";
import ProofSection from "@/components/sections/ProofSection";
import SocialProofSection from "@/components/sections/SocialProofSection";
import FinalCTASection from "@/components/sections/FinalCTASection";

export default function Home() {
  return (
    <main className="bg-[#050505]">
      {/* 1. الخطاف والانبهار — Hook & Awe (3D Core + CTA) */}
      <HeroSection />

      {/* 2. الإثبات والصدمة المالية — Proof & Financial Shock (3D BESS + Leakage) */}
      <ProofSection />

      {/* 3. الثقة والشرعية — Trust & Legitimacy (Social Proof) */}
      <SocialProofSection />

      {/* 4. الدفع النهائي — Final Push (Final CTA) */}
      <FinalCTASection />
    </main>
  );
}
