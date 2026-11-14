import { combineReducers, configureStore } from '@reduxjs/toolkit';

import approvalsReducer from '../features/approvals/approvalsSlice';
import authReducer from '../features/auth/authSlice';

const rootReducer = combineReducers({
  auth: authReducer,
  approvals: approvalsReducer,
});

/** A fresh store; tests pass ``preloadedState`` to start from a known state. */
export function setupStore(preloadedState) {
  return configureStore({ reducer: rootReducer, preloadedState });
}

export const store = setupStore();
