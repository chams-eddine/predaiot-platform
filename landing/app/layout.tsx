import type { Metadata, Viewport } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'PREDAIOT — Economic Decision Audit™ for Energy Assets',
  description:
    'Stop leaving money on the table. Free 7-Day Economic Decision Audit for one asset. No CAPEX, no SCADA connection required. BESS, Solar, Wind, Hydrogen.',
  keywords: [
    'Economic Decision Audit',
    'BESS optimization',
    'battery energy storage',
    'solar dispatch',
    'wind curtailment',
    'green hydrogen',
    'energy asset audit',
    'PREDAIOT',
  ],
  openGraph: {
    title: 'PREDAIOT — Economic Decision Audit™ for Energy Assets',
    description:
      'See the invisible financial leakage in your dispatch decisions. Free 7-day diagnostic — CSV upload, no SCADA integration.',
    type: 'website',
    url: 'https://platform.preda-iot.com',
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: '#050505',
  colorScheme: 'dark',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // `dir` here defaults to LTR; switch to "rtl" for Arabic without any
    // layout rework — all components use logical properties (ms-, me-, ps-, pe-,
    // text-start, text-end) so mirroring is free.
    <html
      lang="en"
      dir="ltr"
      className={`${inter.variable} ${jetbrainsMono.variable} dark`}
    >
      <body className="font-sans bg-canvas text-white antialiased overflow-x-hidden">
        {children}
      </body>
    </html>
  );
}
