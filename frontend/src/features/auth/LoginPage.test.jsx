import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import * as authApi from '../../api/auth';
import { authState, renderWithProviders, users } from '../../test/utils';
import LoginPage from './LoginPage';
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from './loginForm';

vi.mock('../../api/auth');

function renderLogin({ preloadedState = authState(null), from } = {}) {
  const route = { pathname: '/login', state: from ? { from: { pathname: from } } : undefined };
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Dashboard</p>} />
      <Route path="/audit" element={<p>Audit page</p>} />
    </Routes>,
    { preloadedState, route },
  );
}

const tokens = (user) => ({ access_token: 'acc', refresh_token: 'ref', token_type: 'Bearer', user });

describe('LoginPage', () => {
  it('validates required fields before calling the API', async () => {
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(screen.getByText('Email is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it('rejects a malformed email', async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email');
    await userEvent.type(screen.getByLabelText('Password'), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it('signs in and returns to the page the user came from', async () => {
    authApi.login.mockResolvedValue(tokens(users.auditor));
    const { store } = renderLogin({ from: '/audit' });

    await userEvent.type(screen.getByLabelText('Email'), '  auditor@accesshub.dev ');
    await userEvent.type(screen.getByLabelText('Password'), DEMO_PASSWORD);
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Audit page')).toBeInTheDocument();
    expect(authApi.login).toHaveBeenCalledWith('auditor@accesshub.dev', DEMO_PASSWORD);
    expect(store.getState().auth.user).toEqual(users.auditor);
  });

  it('shows the API error when credentials are wrong', async () => {
    authApi.login.mockRejectedValue({
      response: { status: 401, data: { error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password' } } },
    });
    renderLogin();
    await userEvent.type(screen.getByLabelText('Email'), 'employee@accesshub.dev');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
  });

  it('has a demo button for each of the five roles', () => {
    renderLogin();
    for (const account of DEMO_ACCOUNTS) {
      expect(screen.getByRole('button', { name: `Demo login as ${account.role}` })).toBeInTheDocument();
    }
    expect(DEMO_ACCOUNTS).toHaveLength(5);
  });

  it('demo login signs in with the seeded account', async () => {
    authApi.login.mockResolvedValue(tokens(users.admin));
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Demo login as Admin' }));

    await waitFor(() => expect(authApi.login).toHaveBeenCalledWith('admin@accesshub.dev', DEMO_PASSWORD));
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
  });

  it('sends an already signed-in user straight on', () => {
    renderLogin({ preloadedState: authState(users.employee) });
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
