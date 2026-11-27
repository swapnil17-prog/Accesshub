import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as authApi from '../../api/auth';
import { tokenStore } from '../../api/tokens';
import { authState, renderWithProviders, users } from '../../test/utils';
import AccountPage from './AccountPage';

vi.mock('../../api/auth');

async function fill({ current = 'Password@123', next = 'Lighthouse#Blue7', confirm = next } = {}) {
  if (current) await userEvent.type(screen.getByLabelText('Current password'), current);
  if (next) await userEvent.type(screen.getByLabelText('New password'), next);
  if (confirm) await userEvent.type(screen.getByLabelText('Confirm new password'), confirm);
  await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
}

describe('AccountPage', () => {
  beforeEach(() => {
    renderWithProviders(<AccountPage />, { preloadedState: authState({ ...users.employee, department: 'Engineering' }) });
  });

  it('shows the profile', () => {
    expect(screen.getByText('Emery Employee')).toBeInTheDocument();
    expect(screen.getByText('Engineering')).toBeInTheDocument();
  });

  it('checks the confirmation and the live policy hints before calling the API', async () => {
    await userEvent.type(screen.getByLabelText('New password'), 'short');
    expect(screen.getByText(/at least 10 characters/i).closest('li')).toHaveTextContent('(not met)');
    await userEvent.clear(screen.getByLabelText('New password'));
    await fill({ next: 'Lighthouse#Blue7', confirm: 'Lighthouse#Blue8' });
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
    expect(authApi.changePassword).not.toHaveBeenCalled();
  });

  it('changes the password and stores the fresh tokens', async () => {
    authApi.changePassword.mockResolvedValue({ access_token: 'new-a', refresh_token: 'new-r', message: 'ok' });
    await fill();
    expect(authApi.changePassword).toHaveBeenCalledWith('Password@123', 'Lighthouse#Blue7');
    expect(await screen.findByText('Password changed')).toBeInTheDocument();
    expect(tokenStore.getAccess()).toBe('new-a');
    expect(tokenStore.getRefresh()).toBe('new-r');
    expect(screen.getByLabelText('Current password')).toHaveValue('');
  });

  it('shows server errors next to the right field', async () => {
    authApi.changePassword.mockRejectedValue({
      response: {
        status: 422,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid input',
            details: { current_password: ['Your current password is incorrect.'] },
          },
        },
      },
    });
    await fill({ current: 'nope' });
    expect(await screen.findByText('Your current password is incorrect.')).toBeInTheDocument();
    expect(screen.getByLabelText('Current password')).toHaveAttribute('aria-invalid', 'true');
  });
});
