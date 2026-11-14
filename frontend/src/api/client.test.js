import MockAdapter from 'axios-mock-adapter';

import client, { setAuthFailureHandler, toApiError } from './client';
import { tokenStore } from './tokens';

describe('api client', () => {
  let mock;
  let onFailure;

  beforeEach(() => {
    mock = new MockAdapter(client);
    onFailure = vi.fn();
    setAuthFailureHandler(onFailure);
    tokenStore.set({ access: 'old-access', refresh: 'refresh-token' });
  });

  afterEach(() => mock.restore());

  it('attaches the access token', async () => {
    mock.onGet('/auth/me').reply((config) => [200, { auth: config.headers.Authorization }]);
    const { data } = await client.get('/auth/me');
    expect(data.auth).toBe('Bearer old-access');
  });

  it('refreshes once for concurrent 401s and retries every request', async () => {
    let refreshCalls = 0;
    mock.onPost('/auth/refresh').reply((config) => {
      refreshCalls += 1;
      expect(config.headers.Authorization).toBe('Bearer refresh-token');
      return [200, { access_token: 'new-access' }];
    });
    mock.onGet(/\/(requests|approvals\/inbox)/).reply((config) =>
      config.headers.Authorization === 'Bearer new-access'
        ? [200, { url: config.url }]
        : [401, { error: { code: 'TOKEN_EXPIRED', message: 'Token has expired' } }],
    );

    const results = await Promise.all([client.get('/requests'), client.get('/approvals/inbox')]);

    expect(results.map((r) => r.data.url)).toEqual(['/requests', '/approvals/inbox']);
    expect(refreshCalls).toBe(1);
    expect(tokenStore.getAccess()).toBe('new-access');
    expect(onFailure).not.toHaveBeenCalled();
  });

  it('logs out when the refresh fails', async () => {
    mock.onGet('/requests').reply(401, { error: { code: 'TOKEN_EXPIRED' } });
    mock.onPost('/auth/refresh').reply(401, { error: { code: 'TOKEN_REVOKED' } });

    await expect(client.get('/requests')).rejects.toMatchObject({ response: { status: 401 } });
    expect(onFailure).toHaveBeenCalledTimes(1);
    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });

  it('logs out when the retried request is still unauthorised', async () => {
    mock.onGet('/requests').reply(401, { error: { code: 'USER_INACTIVE' } });
    mock.onPost('/auth/refresh').reply(200, { access_token: 'new-access' });

    await expect(client.get('/requests')).rejects.toBeTruthy();
    expect(onFailure).toHaveBeenCalledTimes(1);
  });

  it('does not try to refresh after a failed login', async () => {
    mock.onPost('/auth/login').reply(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password' } });
    const refresh = vi.fn(() => [200, {}]);
    mock.onPost('/auth/refresh').reply(refresh);

    const error = await client.post('/auth/login', {}).catch((e) => e);
    expect(toApiError(error)).toEqual({
      code: 'INVALID_CREDENTIALS',
      message: 'Invalid email or password',
      details: {},
    });
    expect(refresh).not.toHaveBeenCalled();
    expect(onFailure).not.toHaveBeenCalled();
  });

  it('leaves other errors alone', async () => {
    mock.onGet('/requests').reply(403, { error: { code: 'FORBIDDEN', message: 'Nope' } });
    const error = await client.get('/requests').catch((e) => e);
    expect(error.response.status).toBe(403);
    expect(onFailure).not.toHaveBeenCalled();
  });

  it('describes network failures', () => {
    expect(toApiError({ request: {} }).code).toBe('NETWORK_ERROR');
  });
});
