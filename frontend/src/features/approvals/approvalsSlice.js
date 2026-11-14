import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as approvalsApi from '../../api/approvals';
import { logout, sessionExpired } from '../auth/authSlice';

// Phase 5 only needs the inbox count for the top-bar badge; Phase 6 adds the inbox itself.
export const fetchInboxCount = createAsyncThunk('approvals/fetchInboxCount', async () => {
  const data = await approvalsApi.fetchInbox({ page: 1, perPage: 1 });
  return data.total;
});

const approvalsSlice = createSlice({
  name: 'approvals',
  initialState: { inboxCount: 0 },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchInboxCount.fulfilled, (state, action) => {
        state.inboxCount = action.payload;
      })
      .addCase(logout.pending, (state) => {
        state.inboxCount = 0;
      })
      .addCase(sessionExpired, (state) => {
        state.inboxCount = 0;
      });
  },
});

export const selectInboxCount = (state) => state.approvals.inboxCount;

export default approvalsSlice.reducer;
