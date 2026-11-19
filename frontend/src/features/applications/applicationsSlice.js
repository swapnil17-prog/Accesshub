import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import * as applicationsApi from '../../api/applications';
import { withApiError } from '../../utils/thunks';

// Catalogue: active applications offered on the New Request page.
export const fetchCatalog = createAsyncThunk(
  'applications/fetchCatalog',
  withApiError(() => applicationsApi.listApplications({ perPage: 100 })),
);

// Admin list (admins may include inactive applications).
export const fetchAdminApplications = createAsyncThunk(
  'applications/fetchAdmin',
  withApiError(({ includeInactive = false } = {}) => applicationsApi.listApplications({ perPage: 100, includeInactive })),
);

export const fetchApplication = createAsyncThunk(
  'applications/fetchOne',
  withApiError((id) => applicationsApi.getApplication(id)),
);

export const createApplication = createAsyncThunk(
  'applications/create',
  withApiError((body) => applicationsApi.createApplication(body)),
);

export const updateApplication = createAsyncThunk(
  'applications/update',
  withApiError(({ id, changes }) => applicationsApi.updateApplication(id, changes)),
);

export const deactivateApplication = createAsyncThunk(
  'applications/deactivate',
  withApiError((id) => applicationsApi.deactivateApplication(id)),
);

// Level and workflow changes re-read the application so every view sees one consistent copy.
export const addAccessLevel = createAsyncThunk(
  'applications/addLevel',
  withApiError(async ({ appId, name }) => {
    await applicationsApi.addAccessLevel(appId, name);
    return applicationsApi.getApplication(appId);
  }),
);

export const renameAccessLevel = createAsyncThunk(
  'applications/renameLevel',
  withApiError(async ({ appId, levelId, name }) => {
    await applicationsApi.renameAccessLevel(appId, levelId, name);
    return applicationsApi.getApplication(appId);
  }),
);

export const deleteAccessLevel = createAsyncThunk(
  'applications/deleteLevel',
  withApiError(async ({ appId, levelId }) => {
    await applicationsApi.deleteAccessLevel(appId, levelId);
    return applicationsApi.getApplication(appId);
  }),
);

export const saveWorkflow = createAsyncThunk(
  'applications/saveWorkflow',
  withApiError(async ({ appId, steps }) => {
    await applicationsApi.saveWorkflow(appId, steps);
    return applicationsApi.getApplication(appId);
  }),
);

const initialState = {
  catalog: { items: [], status: 'idle', error: null },
  admin: { items: [], status: 'idle', error: null },
  current: { item: null, status: 'idle', error: null },
};

function storeApplication(state, action) {
  const app = action.payload;
  state.current = { item: app, status: 'succeeded', error: null };
  const index = state.admin.items.findIndex((a) => a.id === app.id);
  if (index >= 0) state.admin.items[index] = app;
  else state.admin.items.push(app);
  // The catalogue must be refetched to reflect name/level/workflow changes.
  state.catalog.status = 'idle';
}

const applicationsSlice = createSlice({
  name: 'applications',
  initialState,
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
      })
      .addCase(fetchAdminApplications.pending, (state) => {
        state.admin.status = 'loading';
        state.admin.error = null;
      })
      .addCase(fetchAdminApplications.fulfilled, (state, action) => {
        state.admin = { items: action.payload.items, status: 'succeeded', error: null };
      })
      .addCase(fetchAdminApplications.rejected, (state, action) => {
        state.admin.status = 'failed';
        state.admin.error = action.payload;
      })
      .addCase(fetchApplication.pending, (state, action) => {
        state.current.status = 'loading';
        state.current.error = null;
        if (state.current.item?.id !== Number(action.meta.arg)) state.current.item = null;
      })
      .addCase(fetchApplication.fulfilled, storeApplication)
      .addCase(fetchApplication.rejected, (state, action) => {
        state.current.status = 'failed';
        state.current.error = action.payload;
      });
    for (const thunk of [
      createApplication,
      updateApplication,
      deactivateApplication,
      addAccessLevel,
      renameAccessLevel,
      deleteAccessLevel,
      saveWorkflow,
    ]) {
      builder.addCase(thunk.fulfilled, storeApplication);
    }
  },
});

export const selectCatalog = (state) => state.applications.catalog;
export const selectAdminApplications = (state) => state.applications.admin;
export const selectCurrentApplication = (state) => state.applications.current;

export default applicationsSlice.reducer;
