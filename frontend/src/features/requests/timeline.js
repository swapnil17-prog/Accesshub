/** One row per workflow step: the step and its approval, or null if not reached. */
export function buildTimeline(request) {
  const byStep = new Map(request.approvals.map((a) => [a.step_order, a]));
  return request.steps.map((step) => ({ step, approval: byStep.get(step.step_order) ?? null }));
}
