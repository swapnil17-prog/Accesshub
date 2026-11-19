import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as usersApi from '../../api/users';
import { renderWithProviders } from '../../test/utils';
import WorkflowBuilder from './WorkflowBuilder';

vi.mock('../../api/users');

const steps = [
  { step_order: 1, approver_type: 'MANAGER', approver_user: null, sla_hours: 24 },
  { step_order: 2, approver_type: 'APP_OWNER', approver_user: null, sla_hours: 48 },
];

const rowTypes = () =>
  within(screen.getByRole('list', { name: 'Workflow steps' }))
    .getAllByRole('combobox', { name: 'Approver' })
    .map((select) => select.value);

function renderBuilder(onSave = vi.fn().mockResolvedValue({ ok: true })) {
  renderWithProviders(<WorkflowBuilder steps={steps} onSave={onSave} />);
  return onSave;
}

describe('WorkflowBuilder', () => {
  it('reorders with the arrow buttons and saves the new order', async () => {
    const onSave = renderBuilder();
    expect(screen.getByRole('button', { name: 'Save workflow' })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Move Step 1 down' }));
    expect(rowTypes()).toEqual(['APP_OWNER', 'MANAGER']);
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Save workflow' }));
    expect(onSave).toHaveBeenCalledWith([
      { step_order: 1, approver_type: 'APP_OWNER', approver_user_id: null, sla_hours: 48 },
      { step_order: 2, approver_type: 'MANAGER', approver_user_id: null, sla_hours: 24 },
    ]);
  });

  it('adds a named-approver step that must have a person', async () => {
    usersApi.lookupUsers.mockResolvedValue([{ id: 7, name: 'Sam Specialist', email: 'sam@example.com' }]);
    const onSave = renderBuilder();

    await userEvent.click(screen.getByRole('button', { name: 'Add step' }));
    const step3 = screen.getByRole('listitem', { name: 'Step 3' });
    await userEvent.selectOptions(within(step3).getByRole('combobox', { name: 'Approver' }), 'SPECIFIC_USER');
    await userEvent.click(screen.getByRole('button', { name: 'Save workflow' }));

    expect(within(step3).getByText('Choose the approver.')).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();

    await userEvent.click(within(step3).getByRole('combobox', { name: 'Person' }));
    await userEvent.click(await screen.findByRole('button', { name: /Sam Specialist/ }));
    const sla = within(step3).getByLabelText('SLA (hours)');
    await userEvent.clear(sla);
    await userEvent.type(sla, '8');
    await userEvent.click(screen.getByRole('button', { name: 'Save workflow' }));

    expect(onSave).toHaveBeenCalledWith([
      expect.objectContaining({ step_order: 1 }),
      expect.objectContaining({ step_order: 2 }),
      { step_order: 3, approver_type: 'SPECIFIC_USER', approver_user_id: 7, sla_hours: 8 },
    ]);
  });

  it('removes steps and refuses an empty workflow', async () => {
    const onSave = renderBuilder();
    await userEvent.click(screen.getByRole('button', { name: 'Remove Step 2' }));
    await userEvent.click(screen.getByRole('button', { name: 'Remove Step 1' }));
    expect(screen.getByText(/no approval steps yet/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Save workflow' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/at least one/i);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('shows API validation errors on the right step', async () => {
    const onSave = vi.fn().mockResolvedValue({
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Invalid workflow', details: { 0: { sla_hours: ['Must be between 1 and 168 hours.'] } } },
    });
    renderBuilder(onSave);
    const sla = within(screen.getByRole('listitem', { name: 'Step 1' })).getByLabelText('SLA (hours)');
    await userEvent.clear(sla);
    await userEvent.type(sla, '100');
    await userEvent.click(screen.getByRole('button', { name: 'Save workflow' }));
    expect(await screen.findByText('Must be between 1 and 168 hours.')).toBeInTheDocument();
  });

  it('reset discards unsaved changes', async () => {
    renderBuilder();
    await userEvent.click(screen.getByRole('button', { name: 'Remove Step 1' }));
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(rowTypes()).toEqual(['MANAGER', 'APP_OWNER']);
  });
});
