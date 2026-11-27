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

/** Change your own password. Returns a fresh token pair (all older tokens stop working). */
export async function changePassword(currentPassword, newPassword) {
  const { data } = await client.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}
