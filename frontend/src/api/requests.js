import client from './client';

/** filters: { status, application_id, from, to, mine } — empty values are dropped. */
export async function listRequests({ page = 1, perPage = 10, filters = {} } = {}) {
  const params = { page, per_page: perPage };
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '' && value !== null && value !== undefined) params[key] = value;
  }
  const { data } = await client.get('/requests', { params });
  return data;
}

export async function getRequest(id) {
  const { data } = await client.get(`/requests/${id}`);
  return data;
}

export async function createRequest(body) {
  const { data } = await client.post('/requests', body);
  return data;
}

export async function cancelRequest(id) {
  const { data } = await client.post(`/requests/${id}/cancel`);
  return data;
}
