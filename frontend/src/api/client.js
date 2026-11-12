import axios from 'axios';

// Shared axios instance. Phase 5 adds the auth header + refresh-on-401 interceptors.
const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

export default client;
