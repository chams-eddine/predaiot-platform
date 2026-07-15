// ============================================================================
// PREDAIOT Decision Instruments — chart components (SPEC-CH / SPEC-DV).
// This module is code-split (SPEC-PF rule 2): recharts loads with it, on
// demand, after an audit exists — never on the initial path.
// Every component is a registered instrument; render discipline from theme.
// ============================================================================
import React from 'react';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
  ComposedChart,
} from 'recharts';
import { AXIS_TICK, GRID_PROPS, TOOLTIP_STYLE, TOOLTIP_LABEL, TOOLTIP_ITEM, TOOLTIP_CURSOR } from './theme';

// Token bridge (SPEC-DS sanctioned): raw hex mirrors of the tokens for SVG
// presentation attributes (gradients, cells), which cannot resolve var().
const C = {
  border: '#1B2536', text2: '#97A6BC',
  loss: '#FF5C7A', recover: '#2FD69B', warn: '#F3B24C',
  info: '#5AA9FF', accent: '#34E0C8', accentSoft: 'rgba(52, 224, 200, 0.10)',
  gradeD: '#F5945B', decRecovery: '#7C9CFF',
};

/* IN-13 Financial Timeline — money over time: market price context line +
   per-step EDV bars (recover = captured, loss = destroyed). */
export function FinancialTimeline({ log }) {
  if (!log || log.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={230}>
      <ComposedChart data={log} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="opsPriceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.text2} stopOpacity={0.28} />
            <stop offset="100%" stopColor={C.text2} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="hour" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <YAxis yAxisId="L" stroke={C.border} tick={AXIS_TICK} tickLine={false} tickFormatter={(v) => `$${v}`} />
        <YAxis yAxisId="R" orientation="right" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR}
          formatter={(v, name) => [typeof v === 'number' ? `$${v.toFixed(2)}` : v, name]}
          labelFormatter={(h) => `Step ${h}`}
        />
        <Area yAxisId="L" type="monotone" dataKey="price" name="Market Price"
              stroke={C.text2} strokeWidth={2} fill="url(#opsPriceFill)" dot={false} />
        <Bar yAxisId="R" dataKey="edv_actual_step" name="AI Action">
          {log.map((entry, i) => (
            <Cell key={i} fill={(entry.edv_actual_step || 0) >= 0 ? C.recover : C.loss} />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* IN-06 Leakage Flow — recorded leakage decomposed by root cause. */
export function LeakageFlow({ rootCauses }) {
  const data = rootCauses || [];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis type="number" stroke={C.border} tick={AXIS_TICK} tickLine={false} tickFormatter={(v) => `${v}%`} />
        <YAxis type="category" dataKey="category" stroke={C.border} tick={AXIS_TICK} tickLine={false} width={140} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} formatter={(v) => [`${v}%`, 'Contribution']} />
        <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={[C.loss, C.gradeD, C.warn, C.info, C.accent, C.decRecovery][i % 6]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* IN-13 companion — benchmark vs actual dispatch (counterfactual). */
export function DispatchCurve({ log }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={(log || []).slice(0, 120)} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gOpt" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={C.recover} stopOpacity={0.3} /><stop offset="95%" stopColor={C.recover} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAct" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={C.info} stopOpacity={0.25} /><stop offset="95%" stopColor={C.info} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="hour" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <YAxis stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} />
        <Legend wrapperStyle={{ fontSize: 11, color: C.text2 }} />
        <Area type="monotone" dataKey="optimal_action" name="Optimal Dispatch (MW)" stroke={C.recover} fill="url(#gOpt)" strokeWidth={2} dot={false} />
        <Area type="monotone" dataKey="actual_action" name="Actual Dispatch (MW)" stroke={C.info} fill="url(#gAct)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* IN-13 multi-period series — recorded daily leakage history. */
export function LeakageHistory({ histData }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={histData || []} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="day" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <YAxis stroke={C.border} tickFormatter={(v) => `$${v}`} tick={AXIS_TICK} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} formatter={(v) => [`$${v} lost`, 'Daily Leakage']} />
        <Bar dataKey="daily_gap" fill={C.loss} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* IN-07 family — cumulative live gap (PROVISIONAL flow). */
export function LiveGapFlow({ liveData }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={liveData || []} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gGap" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={C.loss} stopOpacity={0.3} />
            <stop offset="95%" stopColor={C.loss} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="step" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <YAxis stroke={C.border} tick={AXIS_TICK} tickLine={false} tickFormatter={(v) => `$${v}`} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} formatter={(v) => [`$${v}`, 'Cumulative Gap']} />
        <Area type="monotone" dataKey="cumulative_gap" stroke={C.loss} fill="url(#gGap)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* IN-01 companion — live capture score over time (PROVISIONAL). */
export function LiveCaptureScore({ liveData }) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <AreaChart data={liveData || []} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="step" stroke={C.border} tick={AXIS_TICK} tickLine={false} />
        <YAxis domain={[0, 100]} stroke={C.border} tick={AXIS_TICK} tickLine={false} tickFormatter={(v) => `${v}%`} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL} itemStyle={TOOLTIP_ITEM} cursor={TOOLTIP_CURSOR} formatter={(v) => [`${v}%`, 'DQ Score']} />
        <Area type="monotone" dataKey="dq_score_live" stroke={C.accent} fill={C.accentSoft} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
