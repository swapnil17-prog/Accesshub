import client from './client';

/** Applications with their access levels and workflow steps. Admins may include inactive ones. */
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

export async function createApplication(body) {
  const { data } = await client.post('/applications', body);
  return data;
}

/** Partial update: send only the fields that changed. */
export async function updateApplication(id, changes) {
  const { data } = await client.put(`/applications/${id}`, changes);
  return data;
}

export async function deactivateApplication(id) {
  const { data } = await client.delete(`/applications/${id}`);
  return data;
}

export async function addAccessLevel(appId, name) {
  const { data } = await client.post(`/applications/${appId}/access-levels`, { name });
  return data;
}

export async function renameAccessLevel(appId, levelId, name) {
  const { data } = await client.put(`/applications/${appId}/access-levels/${levelId}`, { name });
  return data;
}

export async function deleteAccessLevel(appId, levelId) {
  await client.delete(`/applications/${appId}/access-levels/${levelId}`);
}

/** Replace the whole ordered step list: [{step_order, approver_type, approver_user_id?, sla_hours}] */
export async function saveWorkflow(appId, steps) {
  const { data } = await client.put(`/applications/${appId}/workflow`, { steps });
  return data;
}
