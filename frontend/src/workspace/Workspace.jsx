// ============================================================================
// PREDAIOT Workspace primitives (SPEC-WS / WS-1.0 §6, §12).
// Every dashboard composes these — no page defines its own layout grid.
//   <Workspace>            column of zones; owns zone-gap (and padding when
//                          not already provided by the app shell).
//   <Zone row="full|split|primary">  named row templates (§6.2):
//                          full 1fr · split 1fr 1fr · primary 65fr 35fr.
//                          Collapses to a single column on T1.
//   <Region kind>          macro-grid for T4/T5 (§6.1): main+rail (T4),
//                          analysis|command|evidence (T5). Renders children
//                          in a plain column below T4.
// Layout values come exclusively from the --ws-* tokens (tokens.css).
// ============================================================================
import React from 'react';
import { useWorkspaceTier, tierAtLeast } from './tier';

export function Workspace({ children, pad = false, style }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 'var(--ws-zone-gap)',
      width: '100%', minWidth: 0,
      padding: pad ? 'var(--ws-pad)' : 0,
      ...style,
    }}>{children}</div>
  );
}

const ROW_TEMPLATES = {
  full: '1fr',
  split: '1fr 1fr',
  primary: '65fr 35fr',
};

export function Zone({ row = 'full', children, style }) {
  const tier = useWorkspaceTier();
  const cols = tier === 'T1' ? '1fr' : (ROW_TEMPLATES[row] || ROW_TEMPLATES.full);
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: cols,
      gap: 'var(--ws-card-gap)', minWidth: 0, alignItems: 'stretch',
      ...style,
    }}>{children}</div>
  );
}

const MACRO_TEMPLATES = {
  T4: '65fr 35fr',            /* Main + Intelligence Rail */
  T5: '30fr 45fr 25fr',       /* Analysis | Command | Evidence/Live */
};

export function RegionSplit({ children, style }) {
  const tier = useWorkspaceTier();
  if (!tierAtLeast(tier, 'T4')) {
    return <Workspace style={style}>{children}</Workspace>;
  }
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: MACRO_TEMPLATES[tier] || MACRO_TEMPLATES.T4,
      gap: 'var(--ws-zone-gap)', alignItems: 'start', minWidth: 0, ...style,
    }}>{children}</div>
  );
}

export function Region({ children, style }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 'var(--ws-zone-gap)',
      minWidth: 0, ...style,
    }}>{children}</div>
  );
}

export { useWorkspaceTier, tierAtLeast };
