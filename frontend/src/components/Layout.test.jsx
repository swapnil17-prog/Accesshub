import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as approvalsApi from '../api/approvals';
import * as auditApi from '../api/audit';
import * as authApi from '../api/auth';
import * as requestsApi from '../api/requests';
import * as usersApi from '../api/users';
import { tokenStore } from '../api/tokens';
import AppRoutes from '../routes';
import { authState, renderWithProviders, users } from '../test/utils';

vi.mock('../api/auth');
vi.mock('../api/approvals');
vi.mock('../api/users');
vi.mock('../api/requests');
vi.mock('../api/audit');

beforeEach(() => {
  requestsApi.listRequests.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 0 });
  usersApi.listUsers.mockResolvedValue({ items: [], page: 1, per_page: 15, total: 0 });
  approvalsApi.fetchInbox.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 3 });
  authApi.logout.mockResolvedValue();
  auditApi.fetchSummary.mockReturnValue(new Promise(() => {})); // admin dashboard report: never needed here
});

describe('Layout', () => {
  it('shows only the navigation the user is allowed to use', async () => {
    renderWithProviders(<AppRoutes />, { preloadedState: authState(users.employee) });
    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0];
    expect(within(nav).getByRole('link', { name: /new request/i })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /users/i })).not.toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /audit log/i })).not.toBeInTheDocument();

    expect(await screen.findByTestId('inbox-badge')).toHaveTextContent('3');
  });

  it('shows admin navigation to admins', () => {
    renderWithProviders(<AppRoutes />, { preloadedState: authState(users.admin) });
    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0];
    for (const name of [/applications/i, /users/i, /audit log/i]) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument();
    }
  });

  it('renders the 404 page for unknown paths', () => {
    renderWithProviders(<AppRoutes />, { preloadedState: authState(users.employee), route: '/nope' });
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('signing out lands on a clean login page (no return to the previous page)', async () => {
    authApi.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', user: users.employee });
    tokenStore.set({ access: 'admin-access', refresh: 'admin-refresh' });
    renderWithProviders(<AppRoutes />, { preloadedState: authState(users.admin), route: '/admin/users' });

    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(authApi.logout).toHaveBeenCalledWith('admin-refresh');
    expect(tokenStore.getAccess()).toBeNull();

    // A different user signing in next goes to the dashboard, not to /admin/users (403 for them).
    await userEvent.click(screen.getByRole('button', { name: 'Demo login as Employee' }));
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument();
  });
});
