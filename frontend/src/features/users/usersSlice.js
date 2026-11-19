import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as usersApi from '../../api/users';
import { withApiError } from '../../utils/thunks';

export const USERS_PER_PAGE = 15;

export const fetchUsers = createAsyncThunk(
  'users/fetch',
  withApiError(({ page = 1, filters = {} } = {}) => usersApi.listUsers({ page, perPage: USERS_PER_PAGE, filters })),
);

/**
 * Save the edit modal: profile fields first (PUT /users/:id), then roles if they changed
 * (PUT /users/:id/roles). Returns the final user.
 */
export const saveUser = createAsyncThunk(
  'users/save',
  withApiError(async ({ id, changes, roles }) => {
    let user = Object.keys(changes).length ? await usersApi.updateUser(id, changes) : null;
    if (roles) user = await usersApi.setUserRoles(id, roles);
    return user;
  }),
);

const usersSlice = createSlice({
  name: 'users',
  initialState: { list: { items: [], page: 1, perPage: USERS_PER_PAGE, total: 0, status: 'idle', error: null } },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchUsers.pending, (state) => {
        state.list.status = 'loading';
        state.list.error = null;
      })
      .addCase(fetchUsers.fulfilled, (state, action) => {
        const { items, page, per_page: perPage, total } = action.payload;
        state.list = { items, page, perPage, total, status: 'succeeded', error: null };
      })
      .addCase(fetchUsers.rejected, (state, action) => {
        state.list.status = 'failed';
        state.list.error = action.payload;
      })
      .addCase(saveUser.fulfilled, (state, action) => {
        const user = action.payload;
        if (!user) return;
        const index = state.list.items.findIndex((u) => u.id === user.id);
        if (index >= 0) state.list.items[index] = user;
      });
  },
});

export const selectUsers = (state) => state.users.list;

export default usersSlice.reducer;
