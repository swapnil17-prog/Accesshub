import client from './client';

function auditParams(filters = {}) {
  const params = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '' && value !== null && value !== undefined) params[key] = value;
  }
  return params;
}

/** filters: { actor (user id or "system"), action, entity_type, from, to } */
export async function listAuditLogs({ page = 1, perPage = 50, filters = {} } = {}) {
  const { data } = await client.get('/audit', { params: { page, per_page: perPage, ...auditParams(filters) } });
  return data;
}

/** The CSV as a Blob plus the server's suggested filename (goes through the auth interceptor). */
export async function exportAuditCsv(filters = {}) {
  const response = await client.get('/audit/export.csv', { params: auditParams(filters), responseType: 'blob' });
  const disposition = response.headers?.['content-disposition'] ?? '';
  const filename = /filename="?([^"]+)"?/.exec(disposition)?.[1] ?? 'audit.csv';
  return { blob: response.data, filename };
}

export async function fetchSummary() {
  const { data } = await client.get('/reports/summary');
  return data;
}
