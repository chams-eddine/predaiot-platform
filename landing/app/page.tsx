import HeroSection from "@/components/sections/HeroSection";
import ProofSection from "@/components/sections/ProofSection";
import SocialProofSection from "@/components/sections/SocialProofSection";
import FinalCTASection from "@/components/sections/FinalCTASection";
import LanguageSwitcher from "@/components/LanguageSwitcher";

export default function Home() {
  return (
    <main className="bg-[#050505]">
      {/* Floating EN / FR / AR pill — top-end corner, above every section */}
      <LanguageSwitcher />

      {/* 1. Hook & Awe — 3D Core + CTA */}
      <HeroSection />

      {/* 2. Proof & Financial Shock — 3D BESS + Leakage tooltip */}
      <ProofSection />

      {/* 3. Trust & Legitimacy — Social Proof */}
      <SocialProofSection />

      {/* 4. Final Push — CTA card */}
      <FinalCTASection />
    </main>
  );
}
