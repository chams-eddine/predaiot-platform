import HeroSection from '@/components/HeroSection';
import TrustBanner from '@/components/TrustBanner';
import ProofSection from '@/components/ProofSection';
import SocialProof from '@/components/SocialProof';
import FinalCTA from '@/components/FinalCTA';

export default function LandingPage() {
  return (
    <main className="relative bg-canvas text-white min-h-screen">
      <HeroSection />
      <TrustBanner />
      <ProofSection />
      <SocialProof />
      <FinalCTA />
      <footer className="border-t border-canvas-hairline ps-6 pe-6 py-8">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-white/40">
          <div>
            © {new Date().getFullYear()} PREDAIOT — Economic Decision Intelligence.
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Security</a>
            <a href="mailto:chams@preda-iot.com" className="hover:text-white transition-colors">
              chams@preda-iot.com
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
