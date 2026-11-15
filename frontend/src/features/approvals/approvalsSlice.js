import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as approvalsApi from '../../api/approvals';
import { toApiError } from '../../api/client';
import { logout, sessionExpired } from '../auth/authSlice';

export const INBOX_PER_PAGE = 20;

export const fetchInboxCount = createAsyncThunk('approvals/fetchInboxCount', async () => {
  const data = await approvalsApi.fetchInbox({ page: 1, perPage: 1 });
  return data.total;
});

export const fetchInbox = createAsyncThunk('approvals/fetchInbox', async ({ page = 1 } = {}, { rejectWithValue }) => {
  try {
    return await approvalsApi.fetchInbox({ page, perPage: INBOX_PER_PAGE });
  } catch (error) {
    return rejectWithValue(toApiError(error));
  }
});

// Both decisions are optimistic: the item leaves the inbox as soon as the user confirms
// (".pending"), and is put back where it was if the API refuses (".rejected").
export const approveApproval = createAsyncThunk(
  'approvals/approve',
  async ({ id, comment }, { rejectWithValue }) => {
    try {
      return await approvalsApi.approve(id, comment);
    } catch (error) {
      return rejectWithValue(toApiError(error));
    }
  },
);

export const rejectApproval = createAsyncThunk('approvals/reject', async ({ id, comment }, { rejectWithValue }) => {
  try {
    return await approvalsApi.reject(id, comment);
  } catch (error) {
    return rejectWithValue(toApiError(error));
  }
});

const initialState = {
  inboxCount: 0,
  inbox: { items: [], page: 1, perPage: INBOX_PER_PAGE, total: 0, status: 'idle', error: null },
  // id -> { item, index } for decisions in flight, so a failure can restore the row.
  removed: {},
};

function removeOptimistically(state, action) {
  const { id } = action.meta.arg;
  const index = state.inbox.items.findIndex((item) => item.id === id);
  if (index === -1) return;
  state.removed[id] = { item: state.inbox.items[index], index };
  state.inbox.items.splice(index, 1);
  state.inbox.total = Math.max(0, state.inbox.total - 1);
  state.inboxCount = Math.max(0, state.inboxCount - 1);
}

function confirmRemoval(state, action) {
  delete state.removed[action.meta.arg.id];
}

function restore(state, action) {
  const { id } = action.meta.arg;
  const saved = state.removed[id];
  if (!saved) return;
  delete state.removed[id];
  state.inbox.items.splice(Math.min(saved.index, state.inbox.items.length), 0, saved.item);
  state.inbox.total += 1;
  state.inboxCount += 1;
}

const approvalsSlice = createSlice({
  name: 'approvals',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchInboxCount.fulfilled, (state, action) => {
        state.inboxCount = action.payload;
      })
      .addCase(fetchInbox.pending, (state) => {
        state.inbox.status = 'loading';
        state.inbox.error = null;
      })
      .addCase(fetchInbox.fulfilled, (state, action) => {
        const { items, page, per_page: perPage, total } = action.payload;
        state.inbox = { items, page, perPage, total, status: 'succeeded', error: null };
        state.inboxCount = total;
      })
      .addCase(fetchInbox.rejected, (state, action) => {
        state.inbox.status = 'failed';
        state.inbox.error = action.payload;
      })
      .addCase(approveApproval.pending, removeOptimistically)
      .addCase(approveApproval.fulfilled, confirmRemoval)
      .addCase(approveApproval.rejected, restore)
      .addCase(rejectApproval.pending, removeOptimistically)
      .addCase(rejectApproval.fulfilled, confirmRemoval)
      .addCase(rejectApproval.rejected, restore)
      .addCase(logout.pending, () => initialState)
      .addCase(sessionExpired, () => initialState);
  },
});

export const selectInboxCount = (state) => state.approvals.inboxCount;
export const selectInbox = (state) => state.approvals.inbox;

export default approvalsSlice.reducer;
