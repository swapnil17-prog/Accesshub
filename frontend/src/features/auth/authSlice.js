import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as authApi from '../../api/auth';
import { toApiError } from '../../api/client';
import { tokenStore } from '../../api/tokens';

/**
 * status:
 *   'idle'          tokens exist from a previous visit but haven't been checked yet
 *   'checking'      GET /auth/me in flight
 *   'authenticated' user is loaded
 *   'anonymous'     signed out
 *
 * endedBy: why the last session ended ('signed_out' | 'expired' | null). After a
 * deliberate sign-out the route guard does not remember the page to come back to.
 */
export function makeInitialState() {
  return {
    user: null,
    status: tokenStore.getAccess() ? 'idle' : 'anonymous',
    loggingIn: false,
    error: null,
    endedBy: null,
  };
}

export const login = createAsyncThunk('auth/login', async ({ email, password }, { rejectWithValue }) => {
  try {
    const data = await authApi.login(email, password);
    tokenStore.set({ access: data.access_token, refresh: data.refresh_token });
    return data.user;
  } catch (error) {
    return rejectWithValue(toApiError(error));
  }
});

export const fetchMe = createAsyncThunk('auth/fetchMe', async (_, { rejectWithValue }) => {
  try {
    return await authApi.fetchMe();
  } catch (error) {
    tokenStore.clear();
    return rejectWithValue(toApiError(error));
  }
});

// Revokes the tokens server-side when possible; the local session ends either way.
export const logout = createAsyncThunk('auth/logout', async () => {
  const refreshToken = tokenStore.getRefresh();
  try {
    if (tokenStore.getAccess()) await authApi.logout(refreshToken);
  } catch {
    /* already expired or offline: nothing else to revoke */
  } finally {
    tokenStore.clear();
  }
});

// On success the server revokes every older token, so store the fresh pair it returns.
export const changePassword = createAsyncThunk(
  'auth/changePassword',
  async ({ currentPassword, newPassword }, { rejectWithValue }) => {
    try {
      const data = await authApi.changePassword(currentPassword, newPassword);
      tokenStore.set({ access: data.access_token, refresh: data.refresh_token });
      return data.message;
    } catch (error) {
      return rejectWithValue(toApiError(error));
    }
  },
);

const authSlice = createSlice({
  name: 'auth',
  initialState: makeInitialState,
  reducers: {
    sessionExpired(state) {
      state.user = null;
      state.status = 'anonymous';
      state.error = 'Your session has expired. Please sign in again.';
      state.endedBy = 'expired';
    },
    clearAuthError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.loggingIn = true;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.loggingIn = false;
        state.user = action.payload;
        state.status = 'authenticated';
        state.endedBy = null;
      })
      .addCase(login.rejected, (state, action) => {
        state.loggingIn = false;
        state.error = action.payload?.message ?? 'Sign-in failed.';
      })
      .addCase(fetchMe.pending, (state) => {
        state.status = 'checking';
      })
      .addCase(fetchMe.fulfilled, (state, action) => {
        state.user = action.payload;
        state.status = 'authenticated';
      })
      .addCase(fetchMe.rejected, (state) => {
        state.user = null;
        state.status = 'anonymous';
      })
      .addCase(logout.pending, (state) => {
        state.user = null;
        state.status = 'anonymous';
        state.error = null;
        state.endedBy = 'signed_out';
      });
  },
});

export const { sessionExpired, clearAuthError } = authSlice.actions;

export const selectAuth = (state) => state.auth;
export const selectUser = (state) => state.auth.user;

export default authSlice.reducer;
