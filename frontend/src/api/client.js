import axios from 'axios';

import { tokenStore } from './tokens';

/**
 * Shared axios instance for the API.
 *
 * - Request interceptor: attaches `Authorization: Bearer <access token>`.
 * - Response interceptor: on a 401 it refreshes the access token **once** and retries the
 *   request. Concurrent 401s share a single in-flight refresh (they wait on the same
 *   promise), so a burst of expired requests causes exactly one POST /auth/refresh.
 *   If refreshing fails, or the retried request is still 401, tokens are cleared and the
 *   registered auth-failure handler runs (the store logs the user out).
 */
const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Endpoints whose 401 means "bad credentials", not "expired token": never refresh for these.
const NO_REFRESH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout'];

let onAuthFailure = () => {};
export function setAuthFailureHandler(handler) {
  onAuthFailure = handler;
}

client.interceptors.request.use((config) => {
  if (!config.skipAuth) {
    const token = tokenStore.getAccess();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    const refreshToken = tokenStore.getRefresh();
    refreshPromise = (
      refreshToken
        ? client.post('/auth/refresh', null, {
            headers: { Authorization: `Bearer ${refreshToken}` },
            skipAuth: true,
          })
        : Promise.reject(new Error('No refresh token'))
    )
      .then((response) => {
        tokenStore.setAccess(response.data.access_token);
        return response.data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function failAuth(error) {
  tokenStore.clear();
  onAuthFailure();
  return Promise.reject(error);
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const isAuthPath = NO_REFRESH_PATHS.some((path) => config?.url?.startsWith(path));
    if (response?.status !== 401 || !config || isAuthPath) {
      return Promise.reject(error);
    }
    if (config._retried) {
      return failAuth(error);
    }
    try {
      const token = await refreshAccessToken();
      config._retried = true;
      config.headers.Authorization = `Bearer ${token}`;
      return client(config);
    } catch {
      return failAuth(error);
    }
  },
);

/** The API's error body `{error: {code, message, details}}`, or a generic one. */
export function toApiError(error, fallback = 'Something went wrong. Please try again.') {
  const apiError = error?.response?.data?.error;
  if (apiError) return { code: apiError.code, message: apiError.message, details: apiError.details ?? {} };
  if (error?.request && !error?.response) {
    return { code: 'NETWORK_ERROR', message: 'Cannot reach the server. Check your connection.', details: {} };
  }
  return { code: 'UNKNOWN', message: fallback, details: {} };
}

export default client;
