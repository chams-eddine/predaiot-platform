// SPEC-MI atomic: DigitalFingerprint — the Ed25519 seal "laser-etched" onto the
// report. MI-0: renders ONLY a real signature/hash passed in (never generated
// client-side); the etch animation plays because the artifact exists.
// verified=true → green glow "Verified · Tamper-Proof"; false → red "Unverified".
import React from 'react';

const truncate = (h) => {
  if (!h) return '—';
  const s = String(h);
  return s.length <= 28 ? s : `${s.slice(0, 16)}…${s.slice(-8)}`;
};

// Concentric cryptographic-seal arcs; pathLength lets one etch length fit all.
const SEAL_ARCS = [
  'M 32 6 A 26 26 0 1 1 31.9 6',
  'M 32 14 A 18 18 0 1 1 31.9 14',
  'M 32 22 A 10 10 0 1 1 31.9 22',
];

export default function DigitalFingerprint({ hash, certId, verified = false, statusText }) {
  const color = verified ? 'var(--pdm-optimal)' : 'var(--pdm-leak)';
  const glow = verified ? 'var(--pdm-optimal-glow)' : 'var(--pdm-leak-glow)';
  return (
    <div style={{ background: 'var(--pdm-panel)', border: `1px solid ${verified ? 'rgba(0,250,154,0.25)' : 'rgba(255,51,102,0.25)'}`,
                  borderRadius: 12, padding: '18px 20px', display: 'flex', gap: 18, alignItems: 'center',
                  boxShadow: `0 0 28px -12px ${glow}` }}>
      <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="Cryptographic seal">
        {SEAL_ARCS.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round"
                pathLength="320" className="pdm-etch"
                style={{ '--pdm-etch-len': 320, animationDelay: `${i * 0.25}s`,
                         filter: `drop-shadow(0 0 5px ${glow})` }} />
        ))}
        <circle cx="32" cy="32" r="2.5" fill={color} />
      </svg>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 10, letterSpacing: '0.2em', color: 'var(--pds-text-3, #7A89A3)',
                      fontWeight: 700, marginBottom: 6 }}>
          ED25519 SIGNATURE{certId ? ` · ${certId}` : ''}
        </div>
        <code className="pdm-mono"
              style={{ display: 'block', fontSize: 13, color: 'var(--pds-text, #EAF1F8)',
                       background: 'var(--pdm-void)', border: '1px solid var(--pds-border, #1B2536)',
                       borderRadius: 8, padding: '8px 12px', marginBottom: 8,
                       overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {truncate(hash)}
        </code>
        <div className="pdm-mono" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', color }}>
          {statusText || (verified ? 'VERIFIED · TAMPER-PROOF' : 'UNVERIFIED — NO SIGNING KEY')}
        </div>
      </div>
    </div>
  );
}
