# PREDAIOT Landing Page

Standalone Next.js 14 (App Router) marketing landing for
`platform.preda-iot.com`. Isolated from the existing Vite audit app so it
can be deployed independently (Vercel / Render Static / Cloudflare Pages)
or dropped-in behind the current app on a different route.

## Stack

- **Next.js 14** (App Router)
- **Tailwind CSS** (logical properties throughout — `ms-*`, `me-*`, `ps-*`, `pe-*`, `text-start`, `text-end`) for bilingual/RTL support
- **@react-three/fiber** + **@react-three/drei** for the Hero backdrop and interactive BESS asset
- **Framer Motion** for entry animations and staggers
- **Lucide React** for iconography

## Run locally

```bash
cd landing
npm install
npm run dev
# → http://localhost:3000
```

## Bilingual / RTL

Switch the `<html dir="...">` attribute in `app/layout.tsx` to `"rtl"`
for Arabic — every layout primitive uses logical properties, so mirroring
is transparent. Arrows use `rtl:rotate-180` where directional.

## Files

```
landing/
├── app/
│   ├── layout.tsx           Root layout, fonts, metadata, viewport
│   ├── page.tsx             Composition of the 5 landing sections
│   └── globals.css          Tailwind directives + text-gradient utilities
├── components/
│   ├── HeroSection.tsx      Headline + CTAs + 3D backdrop
│   ├── HeroBackground3D.tsx 2,000-point network field, lazy-loaded
│   ├── TrustBanner.tsx      Security / integration / compliance strip
│   ├── ProofSection.tsx     Split layout: 3D BESS + 3 bullets
│   ├── InteractiveAsset3D.tsx Low-poly BESS with pulse + leakage tooltip
│   ├── SocialProof.tsx      5 placeholder logos, grayscale → color on hover
│   └── FinalCTA.tsx         Gradient-border push card
├── package.json
├── tailwind.config.ts
├── tsconfig.json
├── next.config.js
└── postcss.config.js
```

## Deploy notes

- The 3D scenes are `next/dynamic({ ssr: false })` — SSR / static export
  both work; three.js only ships to the client.
- Replace `PLACEHOLDER_LOGOS` in `components/SocialProof.tsx` with real
  customer marks (SVG components or imported files).
- Update the CTA anchor targets (`#start`, `#demo`, `#upload`) to point at
  the existing trial-gate + upload flows in the Vite app, or to hosted
  routes on the app subdomain (`app.preda-iot.com/...`).
