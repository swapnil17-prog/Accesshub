import client from './client';

export async function fetchInbox({ page = 1, perPage = 20 } = {}) {
  const { data } = await client.get('/approvals/inbox', { params: { page, per_page: perPage } });
  return data; // { items, page, per_page, total }
}
