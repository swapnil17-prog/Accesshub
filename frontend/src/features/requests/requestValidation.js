export const JUSTIFICATION_MIN = 20;
export const JUSTIFICATION_MAX = 2000;

/**
 * Client-side checks mirroring the API's rules (the API re-checks everything).
 * Returns ``{ errors, body }``; ``body`` is the POST /api/requests payload when valid.
 */
export function validateRequest(form, application) {
  const errors = {};
  if (!form.applicationId) errors.applicationId = 'Choose an application.';
  else if (application && application.workflow_steps.length === 0)
    errors.applicationId = 'This application has no approval workflow yet.';
  if (!form.accessLevelId) errors.accessLevelId = 'Choose an access level.';
  const justification = form.justification.trim();
  if (justification.length < JUSTIFICATION_MIN)
    errors.justification = `Please explain in at least ${JUSTIFICATION_MIN} characters.`;

  let durationDays = null;
  if (form.duration === 'custom') {
    const days = Number(form.customDays);
    if (!Number.isInteger(days) || days < 1 || days > 365) errors.customDays = 'Enter a whole number from 1 to 365.';
    else durationDays = days;
  } else if (form.duration) {
    durationDays = Number(form.duration);
  }

  return {
    errors,
    body: {
      application_id: Number(form.applicationId),
      access_level_id: Number(form.accessLevelId),
      justification,
      duration_days: durationDays,
    },
  };
}
