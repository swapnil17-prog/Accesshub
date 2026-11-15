import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as applicationsApi from '../../api/applications';
import { toApiError } from '../../api/client';

// The request catalogue: active applications with access levels and workflow steps.
// Phase 7 adds the admin operations to this slice.
export const fetchCatalog = createAsyncThunk('applications/fetchCatalog', async (_, { rejectWithValue }) => {
  try {
    return await applicationsApi.listApplications({ perPage: 100 });
  } catch (error) {
    return rejectWithValue(toApiError(error));
  }
});

const applicationsSlice = createSlice({
  name: 'applications',
  initialState: { catalog: { items: [], status: 'idle', error: null } },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchCatalog.pending, (state) => {
        state.catalog.status = 'loading';
        state.catalog.error = null;
      })
      .addCase(fetchCatalog.fulfilled, (state, action) => {
        state.catalog = { items: action.payload.items, status: 'succeeded', error: null };
      })
      .addCase(fetchCatalog.rejected, (state, action) => {
        state.catalog.status = 'failed';
        state.catalog.error = action.payload;
      });
  },
});

export const selectCatalog = (state) => state.applications.catalog;

export default applicationsSlice.reducer;
