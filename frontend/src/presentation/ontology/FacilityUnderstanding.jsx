// ============================================================================
// PREDAIOT — Facility Understanding panel (Phase 5)
// Renders the evidence-backed `facility_profile` the backend produced BEFORE the
// audit: detected evidence → recognized equipment → capabilities → facility
// hypothesis, each with confidence. Pure renderer; carries no industrial words.
// ============================================================================
import React from 'react';
import { MC } from '../../design/ds';
import { label, facilityName, facilityConfidence } from './TerminologyResolver';

const pct = (c) => (c == null ? '' : `${Math.round(c * 100)}%`);
const Row = ({ ok, children, tone }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '3px 0', fontSize: 13,
                color: 'var(--pds-text, #EAF1F8)' }}>
    <span style={{ color: tone || MC.optimal, fontWeight: 700 }}>{ok ? '✓' : '·'}</span>
    <span>{children}</span>
  </div>
);
const Kicker = ({ children }) => (
  <div className="mission-kicker" style={{ color: 'var(--pds-text-3)', margin: '14px 0 6px' }}>{children}</div>
);

export default function FacilityUnderstanding({ profile, compact = false }) {
  if (!profile) return null;
  const eq = profile.equipment?.[0] || {};
  const caps = eq.capabilities || [];
  const signals = eq.signal_map || eq.signals || {};
  const evidence = Object.values(signals);
  const ftConf = facilityConfidence(profile);
  const identity = eq.identity || {};

  return (
    <div style={{ background: MC.void, border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 12, padding: '16px 18px' }}>
      <div className="mission-kicker" style={{ color: MC.verified, marginBottom: 4 }}>
        Understanding your facility
      </div>
      <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--pds-text, #EAF1F8)', marginBottom: 2 }}>
        {facilityName(profile)}
        {ftConf != null && (
          <span className="mission-num" style={{ fontSize: 13, color: 'var(--pds-text-3)', marginLeft: 10 }}>
            {profile.facility_type?.value === 'Unknown'
              ? 'hypothesis: not yet determined'
              : `confidence ${pct(ftConf)}`}
          </span>
        )}
      </div>

      {!compact && evidence.length > 0 && (
        <>
          <Kicker>Detected evidence</Kicker>
          {evidence.slice(0, 8).map((inf, i) => (
            <Row key={i} ok>{(inf.evidence || []).join(', ') || label(inf.value)}
              <span style={{ color: 'var(--pds-text-3)' }}> → {label(inf.value)}</span></Row>
          ))}
        </>
      )}

      <Kicker>Recognized equipment</Kicker>
      <Row ok={identity.value && identity.value !== 'Unknown'}
           tone={identity.value === 'Unknown' ? 'var(--pds-warn)' : MC.optimal}>
        {label(identity.value)}
        {identity.confidence != null && (
          <span className="mission-num" style={{ color: 'var(--pds-text-3)' }}> · {pct(identity.confidence)}</span>)}
        {(identity.alternatives || []).length > 0 && (
          <span style={{ color: 'var(--pds-text-3)', fontSize: 11 }}>
            {' '}— or {identity.alternatives.map((a) => `${label(a.value)} (${pct(a.confidence)})`).join(', ')} · need more evidence
          </span>)}
      </Row>

      {caps.length > 0 && (
        <>
          <Kicker>Recognized capabilities</Kicker>
          {caps.map((c, i) => (
            <Row key={i} ok>{label(c.value)}
              <span className="mission-num" style={{ color: 'var(--pds-text-3)' }}> · {pct(c.confidence)}</span></Row>
          ))}
        </>
      )}

      {(profile.unknowns || []).length > 0 && !compact && (
        <div style={{ fontSize: 11, color: 'var(--pds-text-3)', marginTop: 12 }}>
          Ungrounded signals (no economic meaning found): {profile.unknowns.join(', ')}
        </div>
      )}
    </div>
  );
}
