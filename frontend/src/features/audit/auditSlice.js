import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as auditApi from '../../api/audit';
import { withApiError } from '../../utils/thunks';

export const AUDIT_PER_PAGE = 25;

export const fetchAuditLogs = createAsyncThunk(
  'audit/fetchLogs',
  withApiError(({ page = 1, filters = {} } = {}) => auditApi.listAuditLogs({ page, perPage: AUDIT_PER_PAGE, filters })),
);

export const fetchSummary = createAsyncThunk('audit/fetchSummary', withApiError(() => auditApi.fetchSummary()));

const auditSlice = createSlice({
  name: 'audit',
  initialState: {
    logs: { items: [], page: 1, perPage: AUDIT_PER_PAGE, total: 0, status: 'idle', error: null },
    summary: { data: null, status: 'idle', error: null },
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchAuditLogs.pending, (state) => {
        state.logs.status = 'loading';
        state.logs.error = null;
      })
      .addCase(fetchAuditLogs.fulfilled, (state, action) => {
        const { items, page, per_page: perPage, total } = action.payload;
        state.logs = { items, page, perPage, total, status: 'succeeded', error: null };
      })
      .addCase(fetchAuditLogs.rejected, (state, action) => {
        state.logs.status = 'failed';
        state.logs.error = action.payload;
      })
      .addCase(fetchSummary.pending, (state) => {
        state.summary.status = 'loading';
        state.summary.error = null;
      })
      .addCase(fetchSummary.fulfilled, (state, action) => {
        state.summary = { data: action.payload, status: 'succeeded', error: null };
      })
      .addCase(fetchSummary.rejected, (state, action) => {
        state.summary.status = 'failed';
        state.summary.error = action.payload;
      });
  },
});

export const selectAuditLogs = (state) => state.audit.logs;
export const selectSummary = (state) => state.audit.summary;

export default auditSlice.reducer;
