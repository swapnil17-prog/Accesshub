import { combineReducers, configureStore } from '@reduxjs/toolkit';

import applicationsReducer from '../features/applications/applicationsSlice';
import approvalsReducer from '../features/approvals/approvalsSlice';
import authReducer from '../features/auth/authSlice';
import requestsReducer from '../features/requests/requestsSlice';

const rootReducer = combineReducers({
  auth: authReducer,
  approvals: approvalsReducer,
  applications: applicationsReducer,
  requests: requestsReducer,
});

/** A fresh store; tests pass ``preloadedState`` to start from a known state. */
export function setupStore(preloadedState) {
  return configureStore({ reducer: rootReducer, preloadedState });
}

export const store = setupStore();
