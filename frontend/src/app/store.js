import { combineReducers, configureStore } from '@reduxjs/toolkit';

import applicationsReducer from '../features/applications/applicationsSlice';
import approvalsReducer from '../features/approvals/approvalsSlice';
import auditReducer from '../features/audit/auditSlice';
import authReducer from '../features/auth/authSlice';
import dashboardReducer from '../features/dashboard/dashboardSlice';
import requestsReducer from '../features/requests/requestsSlice';
import usersReducer from '../features/users/usersSlice';

const rootReducer = combineReducers({
  auth: authReducer,
  approvals: approvalsReducer,
  applications: applicationsReducer,
  requests: requestsReducer,
  users: usersReducer,
  audit: auditReducer,
  dashboard: dashboardReducer,
});

/** A fresh store; tests pass ``preloadedState`` to start from a known state. */
export function setupStore(preloadedState) {
  return configureStore({ reducer: rootReducer, preloadedState });
}

export const store = setupStore();
