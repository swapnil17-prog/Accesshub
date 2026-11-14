import { render } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';

import { setupStore } from '../app/store';
import { ToastProvider } from '../components/Toast';
import { ROUTER_FUTURE } from '../app/routerConfig';

export const users = {
  admin: { id: 1, name: 'Alex Admin', email: 'admin@accesshub.dev', roles: ['admin', 'employee'] },
  employee: { id: 5, name: 'Emery Employee', email: 'employee@accesshub.dev', roles: ['employee'] },
  auditor: { id: 2, name: 'Avery Auditor', email: 'auditor@accesshub.dev', roles: ['auditor', 'employee'] },
};

export function authState(user) {
  return user
    ? { auth: { user, status: 'authenticated', loggingIn: false, error: null } }
    : { auth: { user: null, status: 'anonymous', loggingIn: false, error: null } };
}

/** Render with a real store (optionally preloaded), a MemoryRouter and the toast provider. */
export function renderWithProviders(ui, { preloadedState, route = '/', store = setupStore(preloadedState) } = {}) {
  const result = render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]} future={ROUTER_FUTURE}>
        <ToastProvider>{ui}</ToastProvider>
      </MemoryRouter>
    </Provider>,
  );
  return { store, ...result };
}
