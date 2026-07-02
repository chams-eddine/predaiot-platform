'use client';

import { motion } from 'framer-motion';

/**
 * Authority-builder strip. Five placeholder logos — generic energy-sector
 * wordmarks paired with an abstract glyph, drawn as inline SVG so the page
 * has no image-asset dependency. Grayscale by default; brand color on hover.
 *
 * ══════════════════════════════════════════════════════════════════════
 * ⚠  BEFORE THIS SECTION IS TRUSTWORTHY: SWAP REAL LOGOS.
 *
 *   Ethically, "Trusted by" with fake companies invites blowback the moment
 *   a prospect Googles one. Options in increasing order of effort:
 *
 *   1. Delete this whole section until you have real design partners.
 *   2. Replace the H2 with "Built to serve" and keep the placeholder marks
 *      as aspirational branding (still borderline).
 *   3. Replace `PLACEHOLDER_LOGOS` with real customer logos — either
 *      inline SVG (best; scales cleanly, no image request) or import an
 *      SVG file per company.
 *
 * To swap in real logos:
 *
 *   const PLACEHOLDER_LOGOS: CompanyLogo[] = [
 *     { name: 'OQ Alternative Energy',
 *       glyph: <path d="…real path from their brand guidelines…" /> },
 *     …
 *   ];
 *
 *   or replace the LogoBadge internals with:
 *     <Image src="/logos/oq.svg" alt="OQ" width={120} height={40}
 *            className="grayscale hover:grayscale-0 transition-all duration-500" />
 * ══════════════════════════════════════════════════════════════════════
 */

type Glyph = React.ReactNode;

interface CompanyLogo {
  name: string;
  glyph: Glyph;
}

const PLACEHOLDER_LOGOS: CompanyLogo[] = [
  {
    name: 'Global Energy Co.',
    glyph: (
      <>
        <circle cx="20" cy="20" r="13" fill="none" strokeWidth="2.5" />
        <circle cx="20" cy="20" r="6" fill="currentColor" opacity="0.3" />
      </>
    ),
  },
  {
    name: 'TechWind',
    glyph: (
      <>
        <path d="M20 6 L34 30 L6 30 Z" fill="none" strokeWidth="2.5" strokeLinejoin="round" />
        <circle cx="20" cy="22" r="2.5" fill="currentColor" />
      </>
    ),
  },
  {
    name: 'Voltaic IPP',
    glyph: (
      <path
        d="M22 5 L10 22 L18 22 L14 36 L30 18 L22 18 Z"
        fill="currentColor"
      />
    ),
  },
  {
    name: 'Nexus Power',
    glyph: (
      <>
        <path d="M8 20 L20 8 L32 20 L20 32 Z" fill="none" strokeWidth="2.5" strokeLinejoin="round" />
        <path d="M20 8 L20 32 M8 20 L32 20" strokeWidth="2" />
      </>
    ),
  },
  {
    name: 'Aeolus Grid',
    glyph: (
      <>
        <circle cx="20" cy="20" r="13" fill="none" strokeWidth="2.5" />
        <circle cx="20" cy="20" r="6"  fill="none" strokeWidth="2" />
        <path d="M20 7 L20 33 M7 20 L33 20" strokeWidth="1.5" />
      </>
    ),
  },
];

function LogoBadge({ name, glyph }: CompanyLogo) {
  return (
    <div
      className="
        group flex items-center gap-3.5
        transition-all duration-500
        opacity-50 hover:opacity-100
        cursor-default
      "
    >
      <svg
        viewBox="0 0 40 40"
        className="
          w-9 h-9 text-white/60 group-hover:text-brand-cyan
          transition-colors duration-500
        "
        stroke="currentColor"
        fill="none"
        aria-hidden="true"
      >
        {glyph}
      </svg>
      <span
        className="
          text-base md:text-lg font-bold tracking-wider
          text-white/60 group-hover:text-white
          transition-colors duration-500
          uppercase whitespace-nowrap
          font-mono
        "
      >
        {name}
      </span>
    </div>
  );
}

export default function SocialProof() {
  return (
    <section
      className="
        relative ps-6 pe-6 py-20
        border-y border-canvas-hairline
        bg-canvas-raised
      "
      aria-labelledby="social-proof-heading"
    >
      <div className="max-w-6xl mx-auto">
        <motion.h2
          id="social-proof-heading"
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.6 }}
          transition={{ duration: 0.7 }}
          className="
            text-center text-xs md:text-sm
            text-white/50 tracking-[0.3em] uppercase font-semibold
            mb-12
          "
        >
          Trusted by Energy Leaders &amp; Independent Power Producers
        </motion.h2>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.9, staggerChildren: 0.1 }}
          className="
            flex flex-wrap justify-center items-center
            gap-x-10 gap-y-8 md:gap-x-16
          "
        >
          {PLACEHOLDER_LOGOS.map((company) => (
            <LogoBadge key={company.name} {...company} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
