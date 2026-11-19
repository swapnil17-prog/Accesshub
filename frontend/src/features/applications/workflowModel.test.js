import { errorsFromApi, hasErrors, moveStep, sameSteps, toEditable, toPayload, validateSteps } from './workflowModel';

const api = [
  { step_order: 2, approver_type: 'APP_OWNER', approver_user: null, sla_hours: 48 },
  { step_order: 1, approver_type: 'MANAGER', approver_user: null, sla_hours: 24 },
  { step_order: 3, approver_type: 'SPECIFIC_USER', approver_user: { id: 9, name: 'Sam' }, sla_hours: 8 },
];

describe('workflowModel', () => {
  it('orders steps and round-trips to the API payload', () => {
    const rows = toEditable(api);
    expect(rows.map((r) => r.approver_type)).toEqual(['MANAGER', 'APP_OWNER', 'SPECIFIC_USER']);
    expect(new Set(rows.map((r) => r.key)).size).toBe(3);
    expect(toPayload(rows)).toEqual([
      { step_order: 1, approver_type: 'MANAGER', approver_user_id: null, sla_hours: 24 },
      { step_order: 2, approver_type: 'APP_OWNER', approver_user_id: null, sla_hours: 48 },
      { step_order: 3, approver_type: 'SPECIFIC_USER', approver_user_id: 9, sla_hours: 8 },
    ]);
  });

  it('moves steps and renumbers by position', () => {
    const rows = moveStep(toEditable(api), 2, 0);
    expect(toPayload(rows).map((s) => [s.step_order, s.approver_type])).toEqual([
      [1, 'SPECIFIC_USER'],
      [2, 'MANAGER'],
      [3, 'APP_OWNER'],
    ]);
    const same = toEditable(api);
    expect(moveStep(same, 0, -1)).toBe(same);
  });

  it('validates like the API', () => {
    expect(validateSteps([]).global).toMatch(/at least one/i);
    const rows = toEditable(api);
    rows[2].approver_user = null;
    rows[0].sla_hours = '0';
    rows[1].sla_hours = '2.5';
    const errors = validateSteps(rows);
    expect(errors.byIndex).toEqual({
      0: { sla_hours: expect.any(String) },
      1: { sla_hours: expect.any(String) },
      2: { approver_user_id: 'Choose the approver.' },
    });
    expect(hasErrors(errors)).toBe(true);
    expect(hasErrors(validateSteps(toEditable(api)))).toBe(false);
  });

  it('maps API 422 details onto steps', () => {
    expect(
      errorsFromApi({
        code: 'VALIDATION_ERROR',
        message: 'Invalid workflow',
        details: { steps: ['step_order values must be 1, 2, 3'], 1: { approver_user_id: ['Must be an active user.'] } },
      }),
    ).toEqual({ global: 'step_order values must be 1, 2, 3', byIndex: { 1: { approver_user_id: 'Must be an active user.' } } });
    expect(errorsFromApi({ message: 'Only an admin or this application’s owner can change it' }).global).toMatch(/owner/);
  });

  it('detects changes ignoring row keys', () => {
    expect(sameSteps(toEditable(api), toEditable(api))).toBe(true);
    const changed = toEditable(api);
    changed[0].sla_hours = '12';
    expect(sameSteps(changed, toEditable(api))).toBe(false);
  });
});
