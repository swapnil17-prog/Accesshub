import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as usersApi from '../../api/users';
import { authState, renderWithProviders, users } from '../../test/utils';
import { meetsBasicPolicy } from '../../utils/passwordPolicy';
import CreateUserModal from './CreateUserModal';

vi.mock('../../api/users');

function renderModal() {
  const onClose = vi.fn();
  renderWithProviders(<CreateUserModal onClose={onClose} />, { preloadedState: authState(users.admin) });
  return { onClose, dialog: screen.getByRole('dialog', { name: 'New user' }) };
}

async function fillBasics(dialog) {
  await userEvent.type(within(dialog).getByLabelText('Full name'), 'Nina New');
  await userEvent.type(within(dialog).getByLabelText('Work email'), 'nina@example.com');
}

describe('CreateUserModal', () => {
  it('generates a strong temporary password and creates the user', async () => {
    usersApi.createUser.mockResolvedValue({ id: 99, name: 'Nina New' });
    const { onClose, dialog } = renderModal();
    await fillBasics(dialog);
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Manager' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Generate' }));

    const password = within(dialog).getByLabelText('Temporary password').value;
    expect(password).toHaveLength(16);
    expect(meetsBasicPolicy(password)).toBe(true);
    expect(within(dialog).getByLabelText('Temporary password')).toHaveAttribute('type', 'text');

    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));
    expect(usersApi.createUser).toHaveBeenCalledWith({
      name: 'Nina New',
      email: 'nina@example.com',
      password,
      department: null,
      manager_id: null,
      roles: ['employee', 'manager'],
    });
    expect(onClose).toHaveBeenCalledWith(true);
  });

  it('validates required fields locally', async () => {
    const { dialog } = renderModal();
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Employee' })); // no roles left
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));
    expect(within(dialog).getByText('Name is required.')).toBeInTheDocument();
    expect(within(dialog).getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(within(dialog).getByText(/set a temporary password/i)).toBeInTheDocument();
    expect(within(dialog).getByText('Give the user at least one role.')).toBeInTheDocument();
    expect(usersApi.createUser).not.toHaveBeenCalled();
  });

  it('shows the server password-policy problems and a taken email inline', async () => {
    const policyError = {
      response: {
        status: 422,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Password does not meet the policy',
            details: { password: ['This password is too common.', "Don't include your name or email in your password."] },
          },
        },
      },
    };
    usersApi.createUser.mockRejectedValueOnce(policyError).mockRejectedValueOnce({
      response: {
        status: 409,
        data: { error: { code: 'EMAIL_TAKEN', message: 'A user with this email already exists' } },
      },
    });
    const { onClose, dialog } = renderModal();
    await fillBasics(dialog);
    await userEvent.type(within(dialog).getByLabelText('Temporary password'), 'NinaNew-2026!');

    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));
    expect(await within(dialog).findByText(/too common.*name or email/)).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));
    expect(await within(dialog).findByText('A user with this email already exists')).toBeInTheDocument();
    expect(within(dialog).getByLabelText('Work email')).toHaveAttribute('aria-invalid', 'true');
    expect(onClose).not.toHaveBeenCalled();
  });
});
