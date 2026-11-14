import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';

import AuthBootstrap from './app/AuthBootstrap';
import { store } from './app/store';
import { ToastProvider } from './components/Toast';
import { ROUTER_FUTURE } from './app/routerConfig';
import AppRoutes from './routes';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter future={ROUTER_FUTURE}>
        <ToastProvider>
          <AuthBootstrap>
            <AppRoutes />
          </AuthBootstrap>
        </ToastProvider>
      </BrowserRouter>
    </Provider>
  </React.StrictMode>,
);
