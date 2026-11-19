import { toApiError } from '../api/client';

/** Wrap an async API call for createAsyncThunk so failures reject with the API error shape. */
export const withApiError =
  (fn) =>
  async (arg, { rejectWithValue }) => {
    try {
      return await fn(arg);
    } catch (error) {
      return rejectWithValue(toApiError(error));
    }
  };
