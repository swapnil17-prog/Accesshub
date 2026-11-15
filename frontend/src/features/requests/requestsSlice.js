import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as requestsApi from '../../api/requests';
import { toApiError } from '../../api/client';

export const PER_PAGE = 10;

const withApiError =
  (fn) =>
  async (arg, { rejectWithValue }) => {
    try {
      return await fn(arg);
    } catch (error) {
      return rejectWithValue(toApiError(error));
    }
  };

export const fetchMyRequests = createAsyncThunk(
  'requests/fetchMine',
  withApiError(({ page = 1, filters = {} } = {}) =>
    requestsApi.listRequests({ page, perPage: PER_PAGE, filters: { ...filters, mine: true } }),
  ),
);

export const fetchRequest = createAsyncThunk('requests/fetchOne', withApiError((id) => requestsApi.getRequest(id)));

export const submitRequest = createAsyncThunk(
  'requests/submit',
  withApiError((body) => requestsApi.createRequest(body)),
);

export const cancelRequest = createAsyncThunk('requests/cancel', withApiError((id) => requestsApi.cancelRequest(id)));

const initialState = {
  list: { items: [], page: 1, perPage: PER_PAGE, total: 0, status: 'idle', error: null },
  detail: { item: null, status: 'idle', error: null },
  submit: { status: 'idle', error: null },
  cancelling: false,
};

const requestsSlice = createSlice({
  name: 'requests',
  initialState,
  reducers: {
    resetSubmit(state) {
      state.submit = initialState.submit;
    },
    /** Put a request fetched elsewhere (e.g. returned by an approval) into the detail view. */
    requestUpdated(state, action) {
      if (state.detail.item?.id === action.payload.id) state.detail.item = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMyRequests.pending, (state) => {
        state.list.status = 'loading';
        state.list.error = null;
      })
      .addCase(fetchMyRequests.fulfilled, (state, action) => {
        const { items, page, per_page: perPage, total } = action.payload;
        state.list = { items, page, perPage, total, status: 'succeeded', error: null };
      })
      .addCase(fetchMyRequests.rejected, (state, action) => {
        state.list.status = 'failed';
        state.list.error = action.payload;
      })
      .addCase(fetchRequest.pending, (state, action) => {
        state.detail.status = 'loading';
        state.detail.error = null;
        if (state.detail.item?.id !== Number(action.meta.arg)) state.detail.item = null;
      })
      .addCase(fetchRequest.fulfilled, (state, action) => {
        state.detail = { item: action.payload, status: 'succeeded', error: null };
      })
      .addCase(fetchRequest.rejected, (state, action) => {
        state.detail.status = 'failed';
        state.detail.error = action.payload;
      })
      .addCase(submitRequest.pending, (state) => {
        state.submit = { status: 'loading', error: null };
      })
      .addCase(submitRequest.fulfilled, (state, action) => {
        state.submit = { status: 'succeeded', error: null };
        state.detail = { item: action.payload, status: 'succeeded', error: null };
      })
      .addCase(submitRequest.rejected, (state, action) => {
        state.submit = { status: 'failed', error: action.payload };
      })
      .addCase(cancelRequest.pending, (state) => {
        state.cancelling = true;
      })
      .addCase(cancelRequest.fulfilled, (state, action) => {
        state.cancelling = false;
        state.detail.item = action.payload;
        const index = state.list.items.findIndex((r) => r.id === action.payload.id);
        if (index >= 0) state.list.items[index] = { ...state.list.items[index], status: action.payload.status };
      })
      .addCase(cancelRequest.rejected, (state) => {
        state.cancelling = false;
      });
  },
});

export const { resetSubmit, requestUpdated } = requestsSlice.actions;

export const selectMyRequests = (state) => state.requests.list;
export const selectRequestDetail = (state) => state.requests.detail;
export const selectSubmit = (state) => state.requests.submit;
export const selectCancelling = (state) => state.requests.cancelling;

export default requestsSlice.reducer;
