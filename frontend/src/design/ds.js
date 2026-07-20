// ============================================================================
// PREDAIOT DESIGN SYSTEM — JS token mirror + semantic helpers.
// The app renders via inline styles; these read from the CSS variables so the
// single source of truth stays in tokens.css (theming works automatically).
// ============================================================================
export const v = (name) => `var(--pds-${name})`;
// Mission-Control / live-motion layer resolver (see tokens.css "two-layer color law").
export const vm = (name) => `var(--pdm-${name})`;

export const PDS = {
  // surfaces
  bg0: v('bg-0'), bg1: v('bg-1'),
  panel: v('panel'), panel2: v('panel-2'), panel3: v('panel-3'),
  border: v('border'), borderStrong: v('border-strong'), hairline: v('hairline'),
  // text
  text: v('text'), text2: v('text-2'), text3: v('text-3'),
  // accent
  accent: v('accent'), accent2: v('accent-2'), accentDeep: v('accent-deep'), accentSoft: v('accent-soft'),
  // economic
  loss: v('loss'), lossSoft: v('loss-soft'),
  recover: v('recover'), recoverSoft: v('recover-soft'),
  warn: v('warn'), warnSoft: v('warn-soft'),
  info: v('info'), infoSoft: v('info-soft'),
  // trust / evidence
  verified: v('verified'), provisional: v('provisional'), seal: v('seal'), evidence: v('evidence'),
  // grid / content caps (SPEC-WS §6.3)
  cardMin: v('card-min'), cardMax: v('card-max'), proseMax: v('prose-max'),
  // type
  sans: v('font-sans'), mono: v('font-mono'),
  // spacing
  s1: v('s1'), s2: v('s2'), s3: v('s3'), s4: v('s4'), s5: v('s5'), s6: v('s6'), s7: v('s7'), s8: v('s8'),
  // radii
  rSm: v('r-sm'), r: v('r'), rLg: v('r-lg'), rXl: v('r-xl'), rPill: v('r-pill'),
  // elevation / motion
  shadow1: v('shadow-1'), shadow2: v('shadow-2'), glowAccent: v('glow-accent'), glowLoss: v('glow-loss'),
  ease: v('ease'), easeOut: v('ease-out'), dur: v('dur'), durFast: v('dur-fast'), durSlow: v('dur-slow'),
};

// — Mission-Control layer (the high-chroma "live-motion" palette) —
// Use ONLY on moving / live-bound elements: flows, meters, the mission banner,
// the command canvas. Static analysis surfaces stay on PDS. This is the JS
// mirror of the --pdm-* tokens so motion components never hard-code hexes.
export const MC = {
  void: vm('void'), panel: vm('panel'),
  optimal: vm('optimal'), leak: vm('leak'), warning: vm('warning'), verified: vm('verified'),
  optimalGlow: vm('optimal-glow'), leakGlow: vm('leak-glow'), verifiedGlow: vm('verified-glow'),
  mono: v('font-mono'),
};

// — Semantic color resolvers (economic meaning drives color) —
export const gradeColor = (g) => ({
  A: v('grade-a'), B: v('grade-b'), C: v('grade-c'), D: v('grade-d'), E: v('grade-e'),
}[(g || '').toUpperCase()] || v('text-3'));

export const decisionColor = (t) => ({
  CORRECTIVE: v('dec-corrective'), OPTIMIZATION: v('dec-optimization'),
  RECOVERY: v('dec-recovery'), MONITORING: v('dec-monitoring'),
}[(t || '').toUpperCase()] || v('accent'));

// Severity by fraction of a reference (0 = fine → 1 = severe). Non-fabricating:
// callers pass an already-computed ratio; this only maps to a hue.
export const severityColor = (ratio) => {
  if (ratio == null) return v('text-3');
  if (ratio >= 0.66) return v('loss');
  if (ratio >= 0.33) return v('warn');
  return v('recover');
};

export const riskColor = (level) => ({
  low: v('risk-low'), moderate: v('risk-moderate'), severe: v('risk-severe'),
}[(level || '').toLowerCase()] || v('text-3'));

// Decision lifecycle states (EDA-DEC-LIFE-1.0).
export const lifecycleColor = (state) => ({
  PROPOSED: v('life-proposed'), ACCEPTED: v('life-accepted'),
  IN_EXECUTION: v('life-execution'), EXECUTED: v('life-executed'),
  DEFERRED: v('life-deferred'), REJECTED: v('life-rejected'),
}[(state || '').toUpperCase()] || v('text-3'));

// Governance verdicts (EDA-GOV-1.0).
export const verdictColor = (verdict) => ({
  VERIFIED: v('gov-verified'), REJECTED: v('gov-rejected'),
  INCONCLUSIVE: v('gov-inconclusive'), PENDING: v('gov-pending'),
}[(verdict || '').toUpperCase()] || v('gov-pending'));

// Opportunities (SPEC-EV money-recoverable; EXPERIMENTAL quarantined).
export const opportunityColor = (experimental) =>
  experimental ? v('opportunity-exp') : v('opportunity');

// — Money / number formatting (institutional, compact when large) —
export const fmtMoney = (val, currency = '') => {
  if (val == null || Number.isNaN(Number(val))) return '—';
  const n = Number(val);
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  let body;
  if (abs >= 1e9) body = (abs / 1e9).toFixed(2) + 'B';
  else if (abs >= 1e6) body = (abs / 1e6).toFixed(2) + 'M';
  else if (abs >= 1e3) body = (abs / 1e3).toFixed(1) + 'K';
  else body = abs.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return `${sign}${body}${currency ? ' ' + currency : ''}`;
};

export const fmtPct = (val, digits = 1) =>
  (val == null || Number.isNaN(Number(val))) ? '—' : `${Number(val).toFixed(digits)}%`;
