import { statusLabel } from '../utils/format';

// Request statuses (PENDING, APPROVED, ...) and approval decisions (... SKIPPED) share one badge.

const STYLES = {
  PENDING: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  APPROVED: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  REJECTED: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  CANCELLED: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  SKIPPED: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  EXPIRED: 'bg-violet-50 text-violet-700 ring-violet-600/20',
  ESCALATED: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  OVERDUE: 'bg-rose-50 text-rose-700 ring-rose-600/30',
};

const DOTS = {
  PENDING: 'bg-amber-500',
  APPROVED: 'bg-emerald-500',
  REJECTED: 'bg-rose-500',
  CANCELLED: 'bg-slate-400',
  SKIPPED: 'bg-slate-400',
  EXPIRED: 'bg-violet-500',
  ESCALATED: 'bg-orange-500',
  OVERDUE: 'bg-rose-500',
};

export default function StatusBadge({ status, className = '' }) {
  const key = String(status || '').toUpperCase();
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[key] ?? STYLES.CANCELLED} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOTS[key] ?? DOTS.CANCELLED}`} aria-hidden="true" />
      {statusLabel(key)}
    </span>
  );
}
