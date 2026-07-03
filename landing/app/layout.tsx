import type { Metadata, Viewport } from "next";
import "./globals.css";
import { LanguageProvider } from "@/lib/LanguageContext";

export const metadata: Metadata = {
  title: "PREDAIOT — Economic Decision Audit™ for Energy Assets",
  description:
    "Stop leaving money on the table. Free 7-Day Economic Decision Audit for one asset. No CAPEX, no SCADA connection required. BESS, Solar, Wind, Hydrogen.",
  keywords: [
    "Economic Decision Audit",
    "BESS optimization",
    "battery energy storage",
    "solar dispatch",
    "wind curtailment",
    "green hydrogen",
    "energy asset audit",
    "PREDAIOT",
  ],
  openGraph: {
    title: "PREDAIOT — Economic Decision Audit™ for Energy Assets",
    description:
      "See the invisible financial leakage in your dispatch decisions. Free 7-day diagnostic — CSV upload, no SCADA integration.",
    type: "website",
    url: "https://platform.preda-iot.com",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#050505",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // dir/lang are dynamically updated by LanguageProvider on the client — the
  // "en" / "ltr" values here are the deterministic first-paint defaults for
  // static export, before hydration swaps them to the user's preference.
  return (
    <html lang="en" dir="ltr" className="dark">
      <body className="bg-[#050505] text-white antialiased overflow-x-hidden">
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
