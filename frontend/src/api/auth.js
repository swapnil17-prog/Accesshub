import client from './client';

export async function login(email, password) {
  const { data } = await client.post('/auth/login', { email, password });
  return data; // { access_token, refresh_token, token_type, user }
}

export async function fetchMe() {
  const { data } = await client.get('/auth/me');
  return data;
}

export async function logout(refreshToken) {
  await client.post('/auth/logout', refreshToken ? { refresh_token: refreshToken } : {});
}
