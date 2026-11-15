import client from './client';

export async function fetchInbox({ page = 1, perPage = 20 } = {}) {
  const { data } = await client.get('/approvals/inbox', { params: { page, per_page: perPage } });
  return data; // { items, page, per_page, total }
}

export async function approve(id, comment) {
  const { data } = await client.post(`/approvals/${id}/approve`, comment ? { comment } : {});
  return data; // the updated request
}

export async function reject(id, comment) {
  const { data } = await client.post(`/approvals/${id}/reject`, { comment });
  return data;
}
