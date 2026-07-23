// SPEC-MI atomic: MissionStatusBanner (MI-8) — the Economic Mission Control
// status strip. MI-0: every badge maps to a real backend field (annotated
// inline); nothing hardcoded. Pure UI — reads the audit response + optional cert.
import React from 'react';

const Badge = ({ label, value, tone = 'accent', live }) => {
  const color = tone === 'optimal' ? 'var(--pdm-optimal)'
    : tone === 'leak' ? 'var(--pdm-leak)'
    : tone === 'warn' ? 'var(--pds-warn, #F3B24C)'
    : 'var(--pds-accent, #34E0C8)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 12px',
                  borderRight: '1px solid var(--pds-border, #1B2536)', whiteSpace: 'nowrap' }}>
      {live && <span className="pds-live-dot" style={{ background: color }} />}
      <span style={{ fontSize: 9, letterSpacing: '0.16em', color: 'var(--pds-text-3, #7A89A3)', fontWeight: 700 }}>
        {label}
      </span>
      <span className="pdm-mono" style={{ fontSize: 12, fontWeight: 700, color }}>{value}</span>
    </div>
  );
};

export default function MissionStatusBanner({ data, certificate }) {
  if (!data) return null;
  const man = data.audit_manifest || {};
  const n = (data.decision_log || []).length;
  const cur = data.currency || 'USD';
  const gap = data.total_gap_usd;
  const risk = data.risk_level;
  const riskTone = risk === 'Low' ? 'optimal' : risk === 'Severe' ? 'leak' : 'warn';
  // ED25519 status only from a real certificate response; never invented.
  // audit_manifest.solver is an object {name, library_version, ...} — render a
  // readable string, never the object.
  const solver = man.solver && typeof man.solver === 'object'
    ? [man.solver.name, man.solver.library_version].filter(Boolean).join(' · ')
    : (man.solver || 'CBC via PuLP');
  const signed = certificate && certificate.signature_status === 'SIGNED';
  const certTone = certificate ? (signed ? 'optimal' : 'warn') : 'accent';
  const certVal = certificate ? (signed ? 'ED25519 VERIFIED' : (certificate.signature_status || 'UNSIGNED')) : 'SIGNABLE';

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center',
                  background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                  borderRadius: 10, overflow: 'hidden' }}>
      {/* audit_manifest.audit_engine_version */}
      <Badge label="ENGINE" value={`CERTIFIED v${man.audit_engine_version || '—'}`} tone="optimal" live />
      {/* decision_log length */}
      <Badge label="DECISIONS" value={n ? n.toLocaleString('en-US') : '—'} />
      {/* audit_manifest.solver (constant from the engine) */}
      <Badge label="SOLVER" value={solver} />
      {/* total_gap_usd + currency */}
      <Badge label="TOTAL GAP" value={gap != null ? `${Math.abs(gap).toLocaleString('en-US', { maximumFractionDigits: 0 })} ${cur}` : '—'} tone="leak" />
      {/* data_quality_index.grade + audit_confidence.grade */}
      <Badge label="DQI" value={(data.data_quality_index || {}).grade || '—'} />
      <Badge label="CONFIDENCE" value={(data.audit_confidence || {}).grade || '—'} />
      {/* certificate signature_status (real cert only) */}
      <Badge label="SEAL" value={certVal} tone={certTone} />
      {/* risk_level */}
      <div style={{ marginLeft: 'auto', padding: '5px 14px' }}>
        <Badge label="RISK" value={(risk || '—').toUpperCase()} tone={riskTone} />
      </div>
    </div>
  );
}
