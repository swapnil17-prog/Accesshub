import { setupStore } from '../../app/store';
import * as authApi from '../../api/auth';
import { tokenStore } from '../../api/tokens';
import reducer, { fetchMe, login, logout, makeInitialState, sessionExpired } from './authSlice';

vi.mock('../../api/auth');

const user = { id: 3, name: 'Morgan Manager', email: 'manager@accesshub.dev', roles: ['employee', 'manager'] };

function apiError(status, code, message) {
  return Object.assign(new Error(message), { response: { status, data: { error: { code, message, details: {} } } } });
}

describe('authSlice', () => {
  it('starts anonymous without stored tokens and idle with them', () => {
    expect(makeInitialState().status).toBe('anonymous');
    tokenStore.set({ access: 'a', refresh: 'r' });
    expect(makeInitialState().status).toBe('idle');
  });

  it('login stores tokens and the user', async () => {
    authApi.login.mockResolvedValue({ access_token: 'acc', refresh_token: 'ref', user });
    const store = setupStore();

    const pending = store.dispatch(login({ email: user.email, password: 'pw' }));
    expect(store.getState().auth.loggingIn).toBe(true);
    await pending;

    expect(authApi.login).toHaveBeenCalledWith(user.email, 'pw');
    expect(store.getState().auth).toMatchObject({ user, status: 'authenticated', loggingIn: false, error: null });
    expect(tokenStore.getAccess()).toBe('acc');
    expect(tokenStore.getRefresh()).toBe('ref');
  });

  it('login failure keeps the user signed out with the API message', async () => {
    authApi.login.mockRejectedValue(apiError(401, 'INVALID_CREDENTIALS', 'Invalid email or password'));
    const store = setupStore();
    const result = await store.dispatch(login({ email: 'x@y.z', password: 'bad' }));

    expect(result.payload.code).toBe('INVALID_CREDENTIALS');
    expect(store.getState().auth).toMatchObject({
      user: null,
      status: 'anonymous',
      loggingIn: false,
      error: 'Invalid email or password',
    });
    expect(tokenStore.getAccess()).toBeNull();
  });

  it('fetchMe loads the user from a stored session', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' });
    authApi.fetchMe.mockResolvedValue(user);
    const store = setupStore();
    expect(store.getState().auth.status).toBe('idle');
    await store.dispatch(fetchMe());
    expect(store.getState().auth).toMatchObject({ user, status: 'authenticated' });
  });

  it('fetchMe failure clears the stored session', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' });
    authApi.fetchMe.mockRejectedValue(apiError(401, 'TOKEN_REVOKED', 'Token has been revoked'));
    const store = setupStore();
    await store.dispatch(fetchMe());
    expect(store.getState().auth.status).toBe('anonymous');
    expect(tokenStore.getAccess()).toBeNull();
  });

  it('logout revokes server-side and always clears locally, even if the API call fails', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' });
    authApi.logout.mockRejectedValue(new Error('offline'));
    const store = setupStore({ auth: { user, status: 'authenticated', loggingIn: false, error: null } });

    await store.dispatch(logout());

    expect(authApi.logout).toHaveBeenCalledWith('r');
    expect(store.getState().auth).toMatchObject({ user: null, status: 'anonymous' });
    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });

  it('sessionExpired signs the user out with an explanation', () => {
    const state = reducer({ user, status: 'authenticated', loggingIn: false, error: null }, sessionExpired());
    expect(state).toMatchObject({ user: null, status: 'anonymous' });
    expect(state.error).toMatch(/session has expired/i);
  });
});
