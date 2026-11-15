import client from './client';

/** Active applications with their access levels and workflow steps. */
export async function listApplications({ q, page = 1, perPage = 100, includeInactive = false } = {}) {
  const params = { page, per_page: perPage };
  if (q) params.q = q;
  if (includeInactive) params.include_inactive = true;
  const { data } = await client.get('/applications', { params });
  return data;
}

export async function getApplication(id) {
  const { data } = await client.get(`/applications/${id}`);
  return data;
}
