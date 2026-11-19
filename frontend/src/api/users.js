import client from './client';

/** Admin user list. filters: { q, role, is_active } */
export async function listUsers({ page = 1, perPage = 20, filters = {} } = {}) {
  const params = { page, per_page: perPage };
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '' && value !== null && value !== undefined) params[key] = value;
  }
  const { data } = await client.get('/users', { params });
  return data;
}

/** Brief active users ({id, name, email}) for pickers; admins and app owners. */
export async function lookupUsers(q) {
  const { data } = await client.get('/users/lookup', { params: q ? { q } : {} });
  return data.items;
}

export async function updateUser(id, changes) {
  const { data } = await client.put(`/users/${id}`, changes);
  return data;
}

export async function setUserRoles(id, roles) {
  const { data } = await client.put(`/users/${id}/roles`, { roles });
  return data;
}
