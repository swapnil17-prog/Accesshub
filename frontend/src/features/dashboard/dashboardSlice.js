import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as approvalsApi from '../../api/approvals';
import * as requestsApi from '../../api/requests';
import { withApiError } from '../../utils/thunks';

/**
 * Personal numbers for the dashboard cards: my pending requests, my inbox and how many of
 * those are overdue. (Organisation-wide numbers come from /reports/summary, in auditSlice.)
 */
export const fetchMyStats = createAsyncThunk(
  'dashboard/fetchMyStats',
  withApiError(async ({ isEmployee }) => {
    const [mine, inbox] = await Promise.all([
      isEmployee
        ? requestsApi.listRequests({ page: 1, perPage: 1, filters: { mine: true, status: 'PENDING' } })
        : Promise.resolve({ total: 0 }),
      approvalsApi.fetchInbox({ page: 1, perPage: 100 }),
    ]);
    return {
      myPending: mine.total,
      inboxTotal: inbox.total,
      inboxOverdue: inbox.items.filter((item) => item.is_overdue).length,
    };
  }),
);

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState: { stats: null, status: 'idle', error: null },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchMyStats.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchMyStats.fulfilled, (state, action) => {
        state.stats = action.payload;
        state.status = 'succeeded';
      })
      .addCase(fetchMyStats.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload;
      });
  },
});

export const selectDashboard = (state) => state.dashboard;

export default dashboardSlice.reducer;
