import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import { authState, renderWithProviders, users } from '../test/utils';
import ProtectedRoute from './ProtectedRoute';

function renderAt(route, preloadedState, roles) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<p>Login page</p>} />
      <Route
        path="/secret"
        element={
          <ProtectedRoute roles={roles}>
            <p>Secret content</p>
          </ProtectedRoute>
        }
      />
      <Route element={<ProtectedRoute roles={roles} />}>
        <Route path="/nested" element={<p>Nested content</p>} />
      </Route>
    </Routes>,
    { route, preloadedState },
  );
}

describe('ProtectedRoute', () => {
  it('redirects signed-out users to the login page', () => {
    renderAt('/secret', authState(null));
    expect(screen.getByText('Login page')).toBeInTheDocument();
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument();
  });

  it('shows a spinner while the stored session is being checked', () => {
    renderAt('/secret', { auth: { user: null, status: 'checking', loggingIn: false, error: null } });
    expect(screen.getByRole('status')).toHaveTextContent(/checking your session/i);
  });

  it('renders the page for any signed-in user when no roles are required', () => {
    renderAt('/secret', authState(users.employee));
    expect(screen.getByText('Secret content')).toBeInTheDocument();
  });

  it('allows a user holding any of the required roles', () => {
    renderAt('/secret', authState(users.auditor), ['auditor', 'admin']);
    expect(screen.getByText('Secret content')).toBeInTheDocument();
  });

  it('shows the 403 page when the user lacks the role', () => {
    renderAt('/secret', authState(users.employee), ['admin']);
    expect(screen.getByRole('heading', { name: /don't have access/i })).toBeInTheDocument();
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument();
  });

  it('works as a layout route via <Outlet />', () => {
    renderAt('/nested', authState(users.admin), ['admin']);
    expect(screen.getByText('Nested content')).toBeInTheDocument();
  });
});
