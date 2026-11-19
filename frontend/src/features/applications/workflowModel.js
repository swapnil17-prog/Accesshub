// Pure helpers behind the workflow builder (kept out of the component so they're easy to test).

export const APPROVER_TYPES = ['MANAGER', 'APP_OWNER', 'SPECIFIC_USER'];
export const SLA_MIN = 1;
export const SLA_MAX = 168;
export const MAX_STEPS = 10;

let keySeq = 0;
const nextKey = () => `step-${(keySeq += 1)}`;

/** API steps -> editable rows (each with a stable React key). */
export function toEditable(steps = []) {
  return [...steps]
    .sort((a, b) => a.step_order - b.step_order)
    .map((step) => ({
      key: nextKey(),
      approver_type: step.approver_type,
      approver_user: step.approver_user ?? null,
      sla_hours: String(step.sla_hours),
    }));
}

export function newStep() {
  return { key: nextKey(), approver_type: 'MANAGER', approver_user: null, sla_hours: '24' };
}

/** Move the row at ``from`` to position ``to`` (returns a new array). */
export function moveStep(steps, from, to) {
  if (to < 0 || to >= steps.length || from === to) return steps;
  const next = [...steps];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Client-side checks mirroring the API. Returns { global, byIndex: {i: {field: msg}} }. */
export function validateSteps(steps) {
  const byIndex = {};
  let global = null;
  if (steps.length === 0) global = 'Add at least one approval step.';
  if (steps.length > MAX_STEPS) global = `At most ${MAX_STEPS} steps are allowed.`;
  steps.forEach((step, index) => {
    const errors = {};
    if (step.approver_type === 'SPECIFIC_USER' && !step.approver_user) errors.approver_user_id = 'Choose the approver.';
    const sla = Number(step.sla_hours);
    if (!Number.isInteger(sla) || sla < SLA_MIN || sla > SLA_MAX)
      errors.sla_hours = `Whole hours from ${SLA_MIN} to ${SLA_MAX}.`;
    if (Object.keys(errors).length) byIndex[index] = errors;
  });
  return { global, byIndex };
}

export function hasErrors({ global, byIndex }) {
  return Boolean(global) || Object.keys(byIndex).length > 0;
}

/** Editable rows -> PUT /workflow body (step_order is the row position, 1..n). */
export function toPayload(steps) {
  return steps.map((step, index) => ({
    step_order: index + 1,
    approver_type: step.approver_type,
    approver_user_id: step.approver_type === 'SPECIFIC_USER' ? (step.approver_user?.id ?? null) : null,
    sla_hours: Number(step.sla_hours),
  }));
}

/** The API's 422 details ({steps: [...], "0": {field: [...]}}) in the builder's error shape. */
export function errorsFromApi(apiError) {
  const details = apiError?.details ?? {};
  const byIndex = {};
  for (const [key, value] of Object.entries(details)) {
    if (/^\d+$/.test(key) && value && typeof value === 'object') {
      byIndex[Number(key)] = Object.fromEntries(
        Object.entries(value).map(([field, messages]) => [field, Array.isArray(messages) ? messages[0] : messages]),
      );
    }
  }
  const steps = details.steps;
  const global = Array.isArray(steps) ? steps[0] : (steps ?? (Object.keys(byIndex).length ? null : apiError?.message));
  return { global: global ?? null, byIndex };
}

/** True if two step lists would produce the same payload. */
export function sameSteps(a, b) {
  return JSON.stringify(toPayload(a)) === JSON.stringify(toPayload(b));
}
