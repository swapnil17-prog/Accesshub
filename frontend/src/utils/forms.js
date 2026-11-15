const base =
  'block w-full rounded-md border-0 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset placeholder:text-slate-400 focus:ring-2 focus:ring-inset disabled:bg-slate-50 disabled:text-slate-500';

export function controlClass(error) {
  return `${base} ${error ? 'ring-rose-400 focus:ring-rose-500' : 'ring-slate-300 focus:ring-indigo-600'}`;
}

/** aria props tying a control to its Field's error/hint text. */
export function describedBy(id, error, hint) {
  if (error) return { 'aria-invalid': true, 'aria-describedby': `${id}-error` };
  if (hint) return { 'aria-describedby': `${id}-hint` };
  return {};
}

/** First message for each field from an API error's ``details`` ({field: [messages]}). */
export function fieldErrorsFrom(apiError) {
  const result = {};
  for (const [field, messages] of Object.entries(apiError?.details ?? {})) {
    result[field] = Array.isArray(messages) ? messages[0] : String(messages);
  }
  return result;
}
