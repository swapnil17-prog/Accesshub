import { Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './features/auth/LoginPage';
import DashboardPage from './features/dashboard/DashboardPage';
import ComingSoonPage from './pages/ComingSoonPage';
import ForbiddenPage from './pages/ForbiddenPage';
import NotFoundPage from './pages/NotFoundPage';

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
          <Route path="requests" element={<ComingSoonPage title="My requests" />} />
          <Route path="requests/new" element={<ComingSoonPage title="New request" />} />
        </Route>
        {/* Approvers and auditors open requests too; the API decides who may see each one. */}
        <Route path="requests/:requestId" element={<ComingSoonPage title="Request details" />} />
        <Route path="approvals" element={<ComingSoonPage title="Approval inbox" />} />

        <Route element={<ProtectedRoute roles={APP_ADMINS} />}>
          <Route path="admin/applications" element={<ComingSoonPage title="Applications" />} />
        </Route>
        <Route element={<ProtectedRoute roles={ADMIN} />}>
          <Route path="admin/users" element={<ComingSoonPage title="Users" />} />
        </Route>
        <Route element={<ProtectedRoute roles={AUDIT} />}>
          <Route path="audit" element={<ComingSoonPage title="Audit log" />} />
        </Route>

        <Route path="403" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
