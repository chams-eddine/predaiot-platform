// ============================================================================
// PREDAIOT Workspace — density tier detection (SPEC-WS / WS-1.0 §7).
// One source of truth for T1–T5. matchMedia-driven; SSR-safe default T2.
//   T1 COMPACT   < 1024px      (tablet, small laptop; drawer < 720px)
//   T2 STANDARD  1024–1679px   (1280 / 1440 / 1600)
//   T3 EXTENDED  1680–2239px   (1920 / 2048)
//   T4 COMMAND   2240–3199px   (2560)
//   T5 WALL      ≥ 3200px      (3440 ultrawide / 49-inch / video walls)
// ============================================================================
import { useEffect, useState } from 'react';

export const TIERS = ['T1', 'T2', 'T3', 'T4', 'T5'];

const QUERIES = {
  T5: '(min-width: 3200px)',
  T4: '(min-width: 2240px)',
  T3: '(min-width: 1680px)',
  T2: '(min-width: 1024px)',
};

export function currentTier() {
  if (typeof window === 'undefined' || !window.matchMedia) return 'T2';
  for (const t of ['T5', 'T4', 'T3', 'T2']) {
    if (window.matchMedia(QUERIES[t]).matches) return t;
  }
  return 'T1';
}

export function useWorkspaceTier() {
  const [tier, setTier] = useState(currentTier);
  useEffect(() => {
    const mqls = Object.values(QUERIES).map((q) => window.matchMedia(q));
    const onChange = () => setTier(currentTier());
    mqls.forEach((m) => (m.addEventListener
      ? m.addEventListener('change', onChange) : m.addListener(onChange)));
    // Belt-and-braces: some embedded/driven browsers deliver window resize
    // without MediaQueryList change events. Same-value setState is a no-op,
    // so this costs nothing when mql events do fire.
    window.addEventListener('resize', onChange);
    return () => {
      mqls.forEach((m) => (m.removeEventListener
        ? m.removeEventListener('change', onChange) : m.removeListener(onChange)));
      window.removeEventListener('resize', onChange);
    };
  }, []);
  return tier;
}

/* tierAtLeast('T3', tier) — zone-visibility gate per the WS matrix (§9). */
export const tierAtLeast = (tier, min) => TIERS.indexOf(tier) >= TIERS.indexOf(min);
