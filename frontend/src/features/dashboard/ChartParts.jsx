import { useState } from 'react';

import { statusLabel } from '../../utils/format';
import { INK, STATUS_COLORS } from './chartTheme';

/** Card around a chart with a "Table" toggle, so every chart has an accessible table view. */
export function ChartCard({ title, description, table, children, className = '' }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className={`rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {description ? <p className="mt-0.5 text-xs text-slate-500">{description}</p> : null}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          aria-pressed={showTable}
          className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
        >
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </div>
      {showTable ? table : children}
    </section>
  );
}

/** Legend for the status series, in stacking order. */
export function StatusLegend({ statuses }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" aria-label="Legend">
      {statuses.map((status) => (
        <li key={status} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: STATUS_COLORS[status] }} aria-hidden="true" />
          {statusLabel(status)}
        </li>
      ))}
    </ul>
  );
}

/** Recharts tooltip body: label, then one line per non-zero series with a colour key. */
export function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value > 0 || payload.length === 1);
  const total = payload.length > 1 ? payload.reduce((sum, p) => sum + (p.value || 0), 0) : null;
  return (
    <div className="rounded-md bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-900/10">
      <p className="mb-1 font-semibold" style={{ color: INK.primary }}>
        {label}
      </p>
      {rows.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2" style={{ color: INK.secondary }}>
          <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: p.payload.fill ?? p.color }} aria-hidden="true" />
          <span className="flex-1">{p.name}</span>
          <span className="font-semibold tabular-nums" style={{ color: INK.primary }}>
            {p.value}
          </span>
        </p>
      ))}
      {total !== null ? (
        <p className="mt-1 border-t border-slate-100 pt-1 text-right font-semibold tabular-nums" style={{ color: INK.primary }}>
          Total {total}
        </p>
      ) : null}
    </div>
  );
}

/** A headline number (the right form for a single value; no chart needed). */
export function StatTile({ label, value, hint, tone = 'default', to, LinkComponent }) {
  const valueClass = tone === 'alert' ? 'text-rose-700' : 'text-slate-900';
  const body = (
    <>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-semibold tabular-nums tracking-tight ${valueClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </>
  );
  const className = 'block rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200';
  if (to && LinkComponent) {
    return (
      <LinkComponent to={to} className={`${className} transition hover:shadow-md hover:ring-indigo-200`}>
        {body}
      </LinkComponent>
    );
  }
  return <div className={className}>{body}</div>;
}
