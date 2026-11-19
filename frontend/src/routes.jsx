import { lazy } from 'react';
import { Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import InboxPage from './features/approvals/InboxPage';
import LoginPage from './features/auth/LoginPage';
import DashboardPage from './features/dashboard/DashboardPage';
import MyRequestsPage from './features/requests/MyRequestsPage';
import NewRequestPage from './features/requests/NewRequestPage';
import RequestDetailPage from './features/requests/RequestDetailPage';
import ForbiddenPage from './pages/ForbiddenPage';
import NotFoundPage from './pages/NotFoundPage';

// Admin and audit screens (and their heavier code) load on first visit; <Layout> shows
// a spinner in the page area meanwhile.
const ApplicationsAdminPage = lazy(() => import('./features/applications/ApplicationsAdminPage'));
const ApplicationEditPage = lazy(() => import('./features/applications/ApplicationEditPage'));
const UsersAdminPage = lazy(() => import('./features/users/UsersAdminPage'));
const AuditPage = lazy(() => import('./features/audit/AuditPage'));

const EMPLOYEE = ['employee'];
const APP_ADMINS = ['admin', 'app_owner'];
const ADMIN = ['admin'];
const AUDIT = ['auditor', 'admin'];

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />

        <Route element={<ProtectedRoute roles={EMPLOYEE} />}>
          <Route path="requests" element={<MyRequestsPage />} />
          <Route path="requests/new" element={<NewRequestPage />} />
        </Route>
        {/* Approvers and auditors open requests too; the API decides who may see each one. */}
        <Route path="requests/:requestId" element={<RequestDetailPage />} />
        <Route path="approvals" element={<InboxPage />} />

        <Route element={<ProtectedRoute roles={APP_ADMINS} />}>
          <Route path="admin/applications" element={<ApplicationsAdminPage />} />
          <Route path="admin/applications/:appId" element={<ApplicationEditPage />} />
        </Route>
        <Route element={<ProtectedRoute roles={ADMIN} />}>
          <Route path="admin/users" element={<UsersAdminPage />} />
        </Route>
        <Route element={<ProtectedRoute roles={AUDIT} />}>
          <Route path="audit" element={<AuditPage />} />
        </Route>

        <Route path="403" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
