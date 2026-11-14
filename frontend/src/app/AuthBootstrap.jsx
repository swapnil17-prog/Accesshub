import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import { setAuthFailureHandler } from '../api/client';
import { fetchMe, selectAuth, sessionExpired } from '../features/auth/authSlice';

/**
 * On start-up, turns stored tokens into a loaded user (GET /auth/me), and connects the
 * axios client's "refresh failed" signal to the store so the user is signed out.
 */
export default function AuthBootstrap({ children }) {
  const dispatch = useDispatch();
  const { status } = useSelector(selectAuth);

  useEffect(() => {
    setAuthFailureHandler(() => dispatch(sessionExpired()));
    return () => setAuthFailureHandler(() => {});
  }, [dispatch]);

  useEffect(() => {
    if (status === 'idle') dispatch(fetchMe());
  }, [status, dispatch]);

  return children;
}
