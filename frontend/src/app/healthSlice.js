import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import { getHealth } from '../api/health';

export const fetchHealth = createAsyncThunk('health/fetch', async (_, { rejectWithValue }) => {
  try {
    return await getHealth();
  } catch (err) {
    // A 503 from the API still carries a JSON body describing what is down.
    return rejectWithValue(err.response?.data ?? { status: 'unreachable', db: 'unknown' });
  }
});

const healthSlice = createSlice({
  name: 'health',
  initialState: { status: 'idle', data: null },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchHealth.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchHealth.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.data = action.payload;
      })
      .addCase(fetchHealth.rejected, (state, action) => {
        state.status = 'failed';
        state.data = action.payload;
      });
  },
});

export default healthSlice.reducer;
