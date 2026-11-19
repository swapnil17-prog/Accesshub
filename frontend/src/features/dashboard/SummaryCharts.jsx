import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { statusLabel } from '../../utils/format';
import { ChartCard, ChartTooltip, StatusLegend } from './ChartParts';
import { INK, STATUS_COLORS, STATUS_ORDER } from './chartTheme';

const AXIS_TICK = { fill: INK.muted, fontSize: 12 };
const BAR_SIZE = 16;

function SimpleTable({ caption, headers, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            {headers.map((h, i) => (
              <th key={h} scope="col" className={`py-2 pr-3 font-semibold ${i > 0 ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row[0]}>
              {row.map((cell, i) => (
                <td key={i} className={`py-2 pr-3 ${i > 0 ? 'text-right tabular-nums' : 'text-slate-900'}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Requests by status: one horizontal bar per status (category names on the axis). */
export function StatusChart({ byStatus }) {
  const data = STATUS_ORDER.map((status) => ({
    name: statusLabel(status),
    status,
    value: byStatus[status] ?? 0,
    fill: STATUS_COLORS[status],
  }));
  return (
    <ChartCard
      title="Requests by status"
      description="All requests ever submitted"
      table={
        <SimpleTable
          caption="Requests by status"
          headers={['Status', 'Requests']}
          rows={data.map((d) => [d.name, d.value])}
        />
      }
    >
      <div className="h-56" role="img" aria-label={`Requests by status: ${data.map((d) => `${d.name} ${d.value}`).join(', ')}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid horizontal={false} stroke={INK.grid} />
            <XAxis type="number" allowDecimals={false} tick={AXIS_TICK} axisLine={{ stroke: INK.axis }} tickLine={false} />
            <YAxis type="category" dataKey="name" width={80} tick={AXIS_TICK} axisLine={{ stroke: INK.axis }} tickLine={false} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }} />
            <Bar dataKey="value" name="Requests" barSize={BAR_SIZE} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.status} fill={d.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

/** Requests by application, stacked by status (fixed status colours, 2px surface gaps). */
export function ApplicationChart({ byApplication }) {
  const data = byApplication.map((app) => ({ name: app.name, total: app.total, ...app.by_status }));
  const height = Math.max(160, data.length * 40 + 40);
  return (
    <ChartCard
      title="Requests by application"
      description="Split by current status"
      table={
        <SimpleTable
          caption="Requests by application and status"
          headers={['Application', ...STATUS_ORDER.map(statusLabel), 'Total']}
          rows={data.map((d) => [d.name, ...STATUS_ORDER.map((s) => d[s] ?? 0), d.total])}
        />
      }
    >
      <StatusLegend statuses={STATUS_ORDER} />
      <div style={{ height }} role="img" aria-label="Requests by application, stacked by status. Use Show table for the numbers.">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid horizontal={false} stroke={INK.grid} />
            <XAxis type="number" allowDecimals={false} tick={AXIS_TICK} axisLine={{ stroke: INK.axis }} tickLine={false} />
            <YAxis type="category" dataKey="name" width={110} tick={AXIS_TICK} axisLine={{ stroke: INK.axis }} tickLine={false} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }} />
            {STATUS_ORDER.map((status, index) => (
              <Bar
                key={status}
                dataKey={status}
                name={statusLabel(status)}
                stackId="status"
                fill={STATUS_COLORS[status]}
                stroke={INK.surface}
                strokeWidth={2}
                barSize={BAR_SIZE + 4}
                radius={index === STATUS_ORDER.length - 1 ? [0, 4, 4, 0] : 0}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

/** Both organisation charts side by side (default export so the dashboard can lazy-load Recharts). */
export default function SummaryCharts({ summary }) {
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-5">
      <div className="xl:col-span-2">
        <StatusChart byStatus={summary.by_status} />
      </div>
      <div className="xl:col-span-3">
        <ApplicationChart byApplication={summary.by_application} />
      </div>
    </div>
  );
}
