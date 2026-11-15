/** "PENDING" -> "Pending" */
export function statusLabel(status) {
  if (!status) return '';
  return status.charAt(0) + status.slice(1).toLowerCase();
}

const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});
const relativeFmt = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

export function formatDate(value) {
  return value ? dateFmt.format(new Date(value)) : '—';
}

export function formatDateTime(value) {
  return value ? dateTimeFmt.format(new Date(value)) : '—';
}

const UNITS = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
];

/** "in 5 hours", "2 days ago", "just now". */
export function relativeTime(value, now = Date.now()) {
  if (!value) return '—';
  const seconds = Math.round((new Date(value).getTime() - now) / 1000);
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relativeFmt.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

/** A length of time in words: "2 hours", "1 day", "less than a minute". */
export function spanText(seconds) {
  const abs = Math.abs(seconds);
  for (const [unit, size] of UNITS) {
    if (abs >= size) {
      const n = Math.round(abs / size);
      return `${n} ${unit}${n === 1 ? '' : 's'}`;
    }
  }
  return 'less than a minute';
}

export function isOverdue(dueAt, now = Date.now()) {
  return new Date(dueAt).getTime() < now;
}

/** How an approval's due time reads in the inbox: "Due in 5 hours" / "Overdue by 2 hours". */
export function dueLabel(dueAt, now = Date.now()) {
  const seconds = (new Date(dueAt).getTime() - now) / 1000;
  return seconds >= 0 ? `Due in ${spanText(seconds)}` : `Overdue by ${spanText(seconds)}`;
}

export function durationLabel(days) {
  if (!days) return 'Permanent';
  if (days % 365 === 0) return `${days / 365} year${days === 365 ? '' : 's'}`;
  return `${days} days`;
}

export const APPROVER_TYPE_LABELS = {
  MANAGER: 'Reporting manager',
  APP_OWNER: 'Application owner',
  SPECIFIC_USER: 'Named approver',
};
