import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import ForbiddenPage from '../pages/ForbiddenPage';
import { FullPageSpinner } from './Spinner';

/**
 * Guards a route.
 * - While the stored session is being checked: a spinner.
 * - Signed out: redirect to /login, remembering where the user was going (unless they
 *   just signed out on purpose; the next person to sign in starts at the dashboard).
 * - Signed in but lacking every one of ``roles``: the 403 page.
 * Wraps ``children`` if given, otherwise renders nested routes via <Outlet />.
 *
 * This is a UX guard only; the API enforces every permission itself.
 */
export default function ProtectedRoute({ roles, children }) {
  const { isAuthenticated, isChecking, hasRole, endedBy } = useAuth();
  const location = useLocation();

  if (isChecking) return <FullPageSpinner label="Checking your session" />;
  if (!isAuthenticated) {
    const state = endedBy === 'signed_out' ? undefined : { from: location };
    return <Navigate to="/login" replace state={state} />;
  }
  if (roles?.length && !hasRole(...roles)) return <ForbiddenPage />;
  return children ?? <Outlet />;
}
