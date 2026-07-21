// ============================================================================
// PREDAIOT — MISSION API (public composition layer)
// One import for the "Economic Mission Control" surfaces (Command Center Canvas,
// Landing film). This is a FACADE: it re-exports the canonical primitives under
// their Mission* names — it does NOT reimplement them. Implementations stay
// single-sourced in design/components.jsx and motion/* (SPEC-DS: one source of
// truth). If a name maps to something that already exists, that is intentional —
// we consolidated rather than forked a second design system.
// ============================================================================

// — Tokens (Mission-Control high-chroma layer + PDS analysis layer) —
export { MC, PDS, gradeColor, riskColor, decisionColor, severityColor,
         verdictColor, lifecycleColor, opportunityColor, fmtMoney, fmtPct } from './ds';

// — Mission atoms (new in Phase 3.5 — the two primitives the library lacked) —
export { MissionLabel, MissionMetric } from './missionAtoms';

// — Structural primitives (from the design system; renamed for the Mission API) —
export {
  Panel as MissionPanel,
  KpiCard as MissionCard,
  AnimatedNumber as MissionCounter,
  GradeBadge as MissionGradeBadge,
  EvidenceBadge as MissionBadge,
  StatusDot as MissionDot,
  SectionShell as MissionSection,
  SectionTitle as MissionSectionTitle,
  Sparkline as MissionSparkline,
  Divider as MissionDivider,
} from './components';

// — Motion instruments (each already MI-0 data-bound) —
export { default as MissionStatus }        from '../motion/MissionStatusBanner';
export { default as MissionEnergyFlow }    from '../motion/EnergyFlowNetwork';
export { default as MissionDecisionEngine } from '../motion/DecisionEngine';
export { default as MissionRadar }         from '../motion/LeakageRadar';
export { default as MissionTimeline }      from '../motion/PredictiveTimeline';
export { default as MissionFingerprint }   from '../motion/DigitalFingerprint';
export { default as MissionHealthOrb }     from '../motion/EconomicHealthOrb';
export { default as MissionRecovery }      from '../motion/RecoveryCounter';
export { default as MissionPrime }         from '../motion/PrimeCounter';
export { default as MissionMeter }         from '../motion/MissionMeter';
