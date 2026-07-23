// SPEC-MI · MISSION CONTROL — the Economic Command HUD that sits ABOVE the
// six-act ExecutiveCommandCenter (augment, never replace). A composition of the
// existing Mission instruments into one console with its own visual DNA:
// deep void, bracket-corner HUD frame, graph-paper texture, high-chroma
// live-motion accents, tabular-mono figures. Feels like a command terminal —
// NOT a dashboard.
//
// MI-0 — every element maps to a real audit field (annotated inline). No backend
// calls, no invented data. Bands render only when their evidence exists.
import React from 'react';
import { MC } from '../design/ds';
import { MissionMetric } from '../design/missionAtoms';
import MissionStatusBanner from './MissionStatusBanner';
import LeakageRadar from './LeakageRadar';
import PredictiveTimeline from './PredictiveTimeline';
import DigitalFingerprint from './DigitalFingerprint';
import MissionMeter from './MissionMeter';
import DigitalTwinRenderer from '../presentation/ontology/DigitalTwinRenderer';
import FacilityUnderstanding from '../presentation/ontology/FacilityUnderstanding';

// Collapse the multi-column instrument grid to a single column on narrow
// viewports (the radar/timeline need full width below tablet).
function useNarrow(bp = 760) {
  const [narrow, setNarrow] = React.useState(
    typeof window !== 'undefined' ? window.innerWidth < bp : false);
  React.useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia(`(max-width: ${bp - 1}px)`);
    const on = () => setNarrow(mq.matches);
    on(); mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [bp]);
  return narrow;
}

const money0 = (v, cur) =>
  `${Math.abs(Number(v) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })} ${cur}`;

// HH:MM from an ISO timestamp (display only; no tz math beyond the recorded offset).
const hhmm = (iso) => {
  if (!iso) return '—';
  const m = String(iso).match(/T(\d{2}:\d{2})/);
  return m ? m[1] : '—';
};
const ymd = (iso) => (iso ? String(iso).slice(0, 10) : '—');

// HUD bracket corner (thin L). Decorative frame only — carries no data.
const Bracket = ({ v, h }) => (
  <span aria-hidden style={{
    position: 'absolute', [v]: -1, [h]: -1, width: 14, height: 14, pointerEvents: 'none',
    [`border${v[0].toUpperCase()}${v.slice(1)}`]: `1.5px solid ${MC.optimal}`,
    [`border${h[0].toUpperCase()}${h.slice(1)}`]: `1.5px solid ${MC.optimal}`,
    opacity: 0.55, borderTopLeftRadius: v === 'top' && h === 'left' ? 12 : 0,
    borderTopRightRadius: v === 'top' && h === 'right' ? 12 : 0,
    borderBottomLeftRadius: v === 'bottom' && h === 'left' ? 12 : 0,
    borderBottomRightRadius: v === 'bottom' && h === 'right' ? 12 : 0,
  }} />
);

// One instrument cell: kicker header + optional reference tag + body.
const Cell = ({ label, tag, span, minH, children }) => (
  <section style={{
    position: 'relative', gridColumn: span, minHeight: minH,
    background: 'var(--mission-void)', border: '1px solid var(--mission-border)',
    borderRadius: 12, padding: '14px 16px 16px',
  }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                     gap: 10, marginBottom: 12 }}>
      <span className="mission-kicker" style={{ color: 'var(--mission-text-dim)' }}>{label}</span>
      {tag && <span className="mission-num" style={{ fontSize: 9, letterSpacing: '0.06em',
                    color: 'var(--mission-text-dim)' }}>{tag}</span>}
    </header>
    {children}
  </section>
);

export default function MissionControl({ data, log = [], certificate }) {
  const narrow = useNarrow(760);
  if (!data) return null;
  const cur = data.currency || 'USD';
  const man = data.audit_manifest || {};
  const eda = data.eda_metrics || {};
  const ga = data.gap_attribution || {};
  const gap = Number(data.total_gap_usd) || 0;
  const hasLeak = gap > 0;
  // Phase 5 — the ontology-driven understanding + twin (backend-provided).
  const fp = data.facility_profile || null;
  const topo = (fp && fp.topology) || [];
  const risk = data.risk_level || '—';

  // System-status master light — driven by risk_level (real).
  const sys = risk === 'Low' ? { t: 'NOMINAL', c: MC.optimal }
    : risk === 'Severe' ? { t: 'CRITICAL', c: MC.leak }
    : { t: 'ELEVATED', c: MC.warning };

  // Decisions benchmarked + how many landed at/above optimum (real gap_step).
  const n = log.length;
  const optimal = log.filter((d) => (Number(d.gap_step) || 0) <= 0).length;

  // Recoverable slice: forecast-execution split if attributed, else ceiling gap.
  const recoverable = ga.execution_gap != null ? Math.abs(Number(ga.execution_gap)) : Math.abs(gap);

  // Cryptographic artifact — a real signature/hash only.
  const sig = (certificate && (certificate.signature_ed25519 || certificate.payload_sha256))
    || man.input_sha256 || null;
  const signed = certificate && certificate.signature_status === 'SIGNED';

  const asset = data.asset_name || man.original_filename || 'ECONOMIC DECISION AUDIT';
  const assetId = data.asset_id || null;
  const tr = man.timestamp_range || {};
  const window = tr.first ? `${ymd(tr.first)} · ${hhmm(tr.first)} → ${hhmm(tr.last)}` : null;
  const causes = (data.root_causes || []).slice().sort((a, b) => (b.loss_usd || 0) - (a.loss_usd || 0));

  return (
    <div style={{ position: 'relative', background: 'var(--mission-void)',
                  border: `1px solid ${sys.c}33`, borderRadius: 14, overflow: 'hidden',
                  boxShadow: `var(--mission-elevation), 0 0 60px -30px ${sys.c}` }}>
      {/* Graph-paper texture — the engineering-console surface (decorative). */}
      <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.5,
        backgroundImage:
          'linear-gradient(var(--mission-border) 1px, transparent 1px), linear-gradient(90deg, var(--mission-border) 1px, transparent 1px)',
        backgroundSize: '32px 32px', maskImage: 'radial-gradient(120% 120% at 50% 0%, #000 30%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(120% 120% at 50% 0%, #000 30%, transparent 75%)' }} />
      <Bracket v="top" h="left" /><Bracket v="top" h="right" />
      <Bracket v="bottom" h="left" /><Bracket v="bottom" h="right" />

      <div style={{ position: 'relative', padding: 18 }}>
        {/* ── HUD title rail ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      gap: 16, flexWrap: 'wrap', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ color: MC.optimal, fontSize: 12, fontWeight: 800, letterSpacing: '0.06em' }}>◢</span>
            <span className="mission-kicker" style={{ color: 'var(--mission-text)', letterSpacing: '0.28em' }}>
              MISSION CONTROL
            </span>
            <span style={{ width: 1, height: 12, background: 'var(--mission-border)' }} />
            <span style={{ fontSize: 12, color: 'var(--mission-text-2)' }}>
              {assetId && <span className="mission-num" style={{ color: 'var(--mission-accent)' }}>{assetId} · </span>}
              {asset}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            {window && <span className="mission-num" style={{ fontSize: 10.5, color: 'var(--mission-text-dim)' }}>
              {window} · {man.steps_audited || n} STEPS</span>}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 12px',
                           borderRadius: 999, border: `1px solid ${sys.c}55`, background: `${sys.c}14` }}>
              <span className="pds-live-dot" style={{ background: sys.c }} />
              <span className="mission-num" style={{ fontSize: 11, fontWeight: 700, color: sys.c, letterSpacing: '0.14em' }}>
                SYSTEM {sys.t}
              </span>
            </span>
          </div>
        </div>

        {/* ── Status rail (MI-8) ─────────────────────────────────────── */}
        <div style={{ marginBottom: 16 }}>
          <MissionStatusBanner data={data} certificate={certificate} />
        </div>

        {/* ── Primary readout — the Bloomberg big-figure row ─────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                      gap: 12, marginBottom: 16 }}>
          <Cell label="Total Gap · vs Theoretical Optimum" tag="TOTAL">
            <MissionMetric label="Total economic gap" tone="leak" size={30}
              value={money0(gap, cur)} sub="vs perfect-foresight optimum (ceiling)" />
          </Cell>
          <Cell label="Recoverable Opportunity" tag="CH 8.2">
            <MissionMetric label="With day-ahead forecast" tone="warning" size={30}
              value={money0(recoverable, cur)} sub="execution-gap slice" />
          </Cell>
          {eda.economic_decision_efficiency != null && (
            <Cell label="Value Captured" tag="EDE">
              <MissionMeter label="of optimum" tone="optimal" decimals={1}
                value={eda.economic_decision_efficiency} max={100} showPct
                sublabel={`${optimal}/${n} intervals at optimum`} />
            </Cell>
          )}
          {eda.economic_leakage_ratio != null && (
            <Cell label="Economic Leakage" tag="ELR">
              <MissionMeter label="surrendered" tone="leak" decimals={1}
                value={eda.economic_leakage_ratio} max={100} showPct
                sublabel="100 − EDE" />
            </Cell>
          )}
        </div>

        {/* ── Instrument grid ────────────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : 'repeat(12, 1fr)', gap: 12 }}>
          {/* Facility Understanding — ontology-driven, what the FUE recognized */}
          {fp && (
            <div style={{ gridColumn: narrow ? '1 / -1' : 'span 12 / span 12' }}>
              <Cell label="Facility Understanding" tag="FUE"><FacilityUnderstanding profile={fp} compact /></Cell>
            </div>
          )}

          <Cell label="Digital Twin · Economic Topology"
                tag={topo.length ? `${(topo[0].label || '').toUpperCase()} → ${(topo[topo.length - 1].label || '').toUpperCase()}` : 'GRID·BESS·LOAD'}
                span={narrow ? 'auto' : 'span 12 / span 12'} minH={0}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr)', gap: 6 }}>
              {/* Always the ontology renderer — it falls back to a GENERIC graph
                  (never a battery schematic) when the backend sent no topology. */}
              <DigitalTwinRenderer topology={topo} hasLeak={hasLeak}
                caption={hasLeak ? 'ECONOMIC LEAK ON THE DECISION EDGE' : 'FLOW AT ECONOMIC OPTIMUM'} />
            </div>
          </Cell>

          {causes.length > 0 && (
            <div style={{ gridColumn: narrow ? '1 / -1' : 'span 5', position: 'relative' }}>
              <Cell label="Value-Leakage Radar" tag={`${causes.length} ROOT CAUSES`} minH="100%">
                <LeakageRadar causes={causes} currency={cur} size={narrow ? 240 : 280} />
              </Cell>
            </div>
          )}

          {log.length > 0 && (
            <div style={{ gridColumn: narrow ? '1 / -1' : (causes.length ? 'span 7' : 'span 12') }}>
              <Cell label="Temporal · Captured vs Optimal" tag={`${n} STEPS`} minH="100%">
                <PredictiveTimeline log={log} currency={cur} width={640} height={210} />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px,1fr))',
                              gap: 14, marginTop: 12 }}>
                  <MissionMetric label="Benchmarked" value={n.toLocaleString('en-US')} tone="accent" size={22} />
                  <MissionMetric label="At Optimum" value={optimal.toLocaleString('en-US')} unit={`/ ${n}`}
                    tone="optimal" size={22} />
                  {eda.dispatch_accuracy != null && (
                    <MissionMetric label="Dispatch Acc." value={eda.dispatch_accuracy.toFixed(1)} unit="%"
                      tone="verified" size={22} />
                  )}
                </div>
              </Cell>
            </div>
          )}
        </div>

        {/* ── Cryptographic verification ─────────────────────────────── */}
        {sig && (
          <div style={{ marginTop: 12 }}>
            <Cell label="Cryptographic Verification" tag={signed ? 'ED25519' : 'SHA-256'}>
              <DigitalFingerprint hash={sig} certId={certificate ? certificate.certificate_id : null}
                verified={!!signed}
                statusText={signed ? 'VERIFIED · TAMPER-PROOF' : 'SIGNABLE — RUN EDPC CERTIFICATION'} />
            </Cell>
          </div>
        )}
      </div>
    </div>
  );
}
