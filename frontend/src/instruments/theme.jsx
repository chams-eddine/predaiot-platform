// ============================================================================
// PREDAIOT Decision Instruments — shared render discipline (SPEC-DV).
// Every visualization is a registered SPEC-CH instrument and consumes these
// primitives. No default library styling may remain visible (SPEC-DV rule 1):
// quiet solid hairline grids (horizontal only), tertiary mono axes, panel-
// styled tooltips with mono numerals, gradient-to-transparent area fills.
// Colors are semantic tokens only — series never pick arbitrary hues.
// ============================================================================
import React from 'react';

export const AXIS_TICK = {
  fill: 'var(--pds-text-3)',
  fontSize: 10,
  fontFamily: 'var(--pds-font-mono)',
};

/* <CartesianGrid {...GRID_PROPS} /> — solid hairline, horizontal only. */
export const GRID_PROPS = {
  stroke: 'var(--pds-hairline)',
  strokeOpacity: 0.6,
  vertical: false,
};

/* Tooltip: contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL}
            itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} */
export const TOOLTIP_STYLE = {
  background: 'var(--pds-panel)',
  border: '1px solid var(--pds-border)',
  borderRadius: 10,
  boxShadow: 'var(--pds-shadow-2)',
  fontSize: 11,
  fontFamily: 'var(--pds-font-mono)',
  color: 'var(--pds-text)',
};
export const TOOLTIP_LABEL = {
  color: 'var(--pds-text-2)',
  fontFamily: 'var(--pds-font-mono)',
  fontSize: 10,
};
export const TOOLTIP_ITEM = {
  color: 'var(--pds-text)',
  fontFamily: 'var(--pds-font-mono)',
  fontSize: 11,
};
export const TOOLTIP_CURSOR = { stroke: 'var(--pds-hairline)' };

/* SPEC-IX loading state: a still, panel-shaped placeholder the size of the
   incoming instrument — no spinners, no shimmer (SPEC-MO). */
export const ChartSkeleton = ({ h = 200 }) => (
  <div aria-hidden style={{ height: h, borderRadius: 'var(--pds-r)',
    background: 'var(--pds-panel-2)', border: '1px solid var(--pds-border)' }} />
);

/* Shared area-fill gradient — accent fades to transparent (SPEC-DV). */
export function AreaGradient({ id, color, from = 0.28 }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={from} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  );
}
