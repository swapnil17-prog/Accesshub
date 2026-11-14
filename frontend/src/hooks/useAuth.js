import { useCallback, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import { login as loginThunk, logout as logoutThunk, selectAuth } from '../features/auth/authSlice';

const NO_ROLES = [];

/**
 * Current user and helpers.
 * `hasRole('admin', 'auditor')` is true if the user holds **any** of the given roles.
 */
export function useAuth() {
  const dispatch = useDispatch();
  const { user, status, loggingIn, error, endedBy } = useSelector(selectAuth);
  const roles = user?.roles ?? NO_ROLES;

  const hasRole = useCallback((...wanted) => wanted.flat().some((role) => roles.includes(role)), [roles]);
  const login = useCallback((credentials) => dispatch(loginThunk(credentials)).unwrap(), [dispatch]);
  const logout = useCallback(() => dispatch(logoutThunk()), [dispatch]);

  return useMemo(
    () => ({
      user,
      roles,
      status,
      isAuthenticated: status === 'authenticated',
      isChecking: status === 'idle' || status === 'checking',
      loggingIn,
      error,
      endedBy,
      hasRole,
      login,
      logout,
    }),
    [user, roles, status, loggingIn, error, endedBy, hasRole, login, logout],
  );
}
