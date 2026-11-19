import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as usersApi from '../../api/users';
import { authState, renderWithProviders, users } from '../../test/utils';
import EditUserModal from './EditUserModal';

vi.mock('../../api/users');

const target = {
  id: 6,
  name: 'Carl Colleague',
  email: 'carl@example.com',
  department: 'Engineering',
  manager_id: 3,
  manager: { id: 3, name: 'Morgan Manager', email: 'manager@example.com' },
  is_active: true,
  roles: ['employee'],
};

function renderModal(onClose = vi.fn()) {
  renderWithProviders(<EditUserModal user={target} onClose={onClose} />, { preloadedState: authState(users.admin) });
  return { onClose, dialog: screen.getByRole('dialog', { name: 'Edit Carl Colleague' }) };
}

describe('EditUserModal', () => {
  it('saves only what changed: profile fields, then roles', async () => {
    usersApi.updateUser.mockResolvedValue({ ...target, department: 'Platform', is_active: false });
    usersApi.setUserRoles.mockResolvedValue({ ...target, roles: ['employee', 'manager'] });
    const { onClose, dialog } = renderModal();

    const department = within(dialog).getByLabelText(/department/i);
    await userEvent.clear(department);
    await userEvent.type(department, 'Platform');
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Manager' }));
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /active/i }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(usersApi.updateUser).toHaveBeenCalledWith(6, { department: 'Platform', is_active: false });
    expect(usersApi.setUserRoles).toHaveBeenCalledWith(6, ['employee', 'manager']);
    expect(onClose).toHaveBeenCalledWith(true);
  });

  it('shows a manager-cycle error next to the manager field', async () => {
    usersApi.updateUser.mockRejectedValue({
      response: {
        status: 422,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid input',
            details: { manager_id: ['Morgan Manager reports to Carl Colleague; this would create a cycle.'] },
          },
        },
      },
    });
    const { onClose, dialog } = renderModal();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Clear Morgan Manager' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(await within(dialog).findByText(/would create a cycle/)).toBeInTheDocument();
    expect(usersApi.updateUser).toHaveBeenCalledWith(6, { manager_id: null });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('shows lockout errors at the top of the form', async () => {
    usersApi.setUserRoles.mockRejectedValue({
      response: { status: 409, data: { error: { code: 'LAST_ADMIN', message: 'At least one active admin must remain' } } },
    });
    const { dialog } = renderModal();
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Auditor' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('At least one active admin must remain');
    expect(usersApi.updateUser).not.toHaveBeenCalled();
  });

  it('closes without calling the API when nothing changed', async () => {
    const { onClose, dialog } = renderModal();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(usersApi.updateUser).not.toHaveBeenCalled();
    expect(usersApi.setUserRoles).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
});
