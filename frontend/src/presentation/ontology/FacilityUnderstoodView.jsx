// ============================================================================
// PREDAIOT — Facility Understood View (understand-first upload)
// Rendered when the backend classified the upload as an ENGINEERING / nameplate
// file: the platform understood the facility but has no operational data to run
// an economic audit. Pure renderer of `facility_profile` — zero industrial
// vocabulary, zero fabricated economics. Composes the same ontology instruments
// the audit view uses (digital twin + understanding panel) + a guidance CTA.
// ============================================================================
import React from 'react';
import { MC } from '../../design/ds';
import DigitalTwinRenderer from './DigitalTwinRenderer';
import FacilityUnderstanding from './FacilityUnderstanding';
import { facilityName, capabilityLabels } from './TerminologyResolver';

const Chip = ({ children }) => (
  <span style={{ background: 'var(--pdm-panel)', border: '1px solid var(--pds-border, #1B2536)',
                 color: 'var(--pds-text, #EAF1F8)', borderRadius: 999, padding: '5px 13px',
                 fontSize: 12, fontWeight: 600 }}>{children}</span>
);

// A labelled 0..100% bar — the platform's honesty made visible (No Guess Without
// Evidence): how sure we are WHAT this is vs. whether we can economically AUDIT it.
const Meter = ({ label, value, tone }) => {
  const pct = Math.round((value || 0) * 100);
  return (
    <div style={{ flex: 1, minWidth: 200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span className="mission-kicker" style={{ color: 'var(--pds-text-3)' }}>{label}</span>
        <span className="mission-num" style={{ color: tone, fontWeight: 700, fontSize: 12 }}>{pct}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 4, background: 'var(--pds-border, #1B2536)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: tone,
                      boxShadow: `0 0 8px ${tone}`, transition: 'width .5s ease' }} />
      </div>
    </div>
  );
};

export default function FacilityUnderstoodView({ data, onUploadOperational }) {
  const profile = data?.facility_profile || null;
  const guidance = data?.guidance || {};
  const readiness = data?.readiness || {};
  const recognized = !!data?.recognized;
  const uConf = readiness.understanding_confidence ?? profile?.understanding_confidence ?? 0;
  const oConf = readiness.operational_confidence ?? 0;
  const caps = capabilityLabels(profile);
  const equip = (profile?.equipment || [])
    .map((e) => e?.identity?.value)
    .filter((v) => v && v !== 'Unknown');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--ws-zone-gap, 28px)' }}>
      {/* Status header — success, not failure */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
        <span className="mission-kicker" style={{ color: recognized ? MC.verified : 'var(--pds-warn)' }}>
          {recognized ? '✓ Facility identified' : 'File received'}
        </span>
        <span style={{ fontSize: 26, fontWeight: 800, color: 'var(--pds-text, #EAF1F8)' }}>
          {data?.asset_name || facilityName(profile)}
        </span>
      </div>

      {/* Two honest gauges: what it IS vs. whether we can economically AUDIT it. */}
      <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Meter label="Understanding confidence" value={uConf} tone={MC.verified} />
        <Meter label="Operational readiness" value={oConf}
               tone={readiness.economic_audit ? MC.optimal : 'var(--pds-warn, #F5A623)'} />
      </div>

      {/* Digital twin — auto-generated from the ontology topology */}
      <DigitalTwinRenderer topology={profile?.topology || []}
        caption={recognized ? 'DIGITAL TWIN — GENERATED FROM RECOGNIZED ONTOLOGY' : undefined} />

      {/* Recognized equipment + capabilities, at a glance */}
      {(equip.length > 0 || caps.length > 0) && (
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {equip.length > 0 && (
            <div>
              <div className="mission-kicker" style={{ color: 'var(--pds-text-3)', marginBottom: 8 }}>Equipment</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {equip.map((e, i) => <Chip key={i}>{String(e).replace(/_/g, ' ')
                  .replace(/\b\w/g, (c) => c.toUpperCase())}</Chip>)}
              </div>
            </div>
          )}
          {caps.length > 0 && (
            <div>
              <div className="mission-kicker" style={{ color: 'var(--pds-text-3)', marginBottom: 8 }}>Capabilities</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {caps.map((c, i) => <Chip key={i}>{c}</Chip>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* The evidence-backed understanding (Facts → equipment → capabilities) */}
      <FacilityUnderstanding profile={profile} />

      {/* Guidance CTA — what's needed for the economic audit (no fake numbers) */}
      <div style={{ background: MC.void, border: '1px solid var(--pds-border, #1B2536)',
                    borderRadius: 12, padding: '18px 20px' }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--pds-text, #EAF1F8)', marginBottom: 6 }}>
          {guidance.headline || 'Facility identified.'}
        </div>
        <div style={{ fontSize: 13, color: 'var(--pds-text-2, #97A6BC)', marginBottom: 14, maxWidth: 620 }}>
          {guidance.message
            || 'To perform an economic audit, upload operational measurements (price + power + timestamps).'}
        </div>
        {(guidance.required || []).length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {guidance.required.map((r, i) => (
              <span key={i} style={{ fontSize: 11, letterSpacing: '0.04em', color: 'var(--pds-text-3)',
                        border: '1px dashed var(--pds-border, #1B2536)', borderRadius: 6, padding: '4px 9px' }}>
                {r}
              </span>
            ))}
          </div>
        )}
        {onUploadOperational && (
          <button onClick={onUploadOperational}
            style={{ background: 'transparent', border: `1px solid ${MC.optimal}`, color: MC.optimal,
                     borderRadius: 8, padding: '9px 18px', fontSize: 12, fontWeight: 700,
                     letterSpacing: '0.06em', cursor: 'pointer' }}>
            UPLOAD OPERATIONAL DATA
          </button>
        )}
      </div>
    </div>
  );
}
