import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';

import { ButtonLink } from '../../components/Button';
import DataTable from '../../components/DataTable';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert, TextInput } from '../../components/form';
import { GridIcon, PlusIcon, SearchIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import { useAuth } from '../../hooks/useAuth';
import { APPROVER_TYPE_LABELS } from '../../utils/format';
import { fetchAdminApplications, selectAdminApplications } from './applicationsSlice';

const SHORT_TYPE = { MANAGER: 'Manager', APP_OWNER: 'Owner', SPECIFIC_USER: 'Named' };

function chainSummary(steps) {
  if (!steps.length) return <span className="text-amber-700">No workflow</span>;
  return (
    <span title={steps.map((s) => APPROVER_TYPE_LABELS[s.approver_type]).join(' → ')}>
      {steps.map((s) => (s.approver_type === 'SPECIFIC_USER' ? (s.approver_user?.name ?? 'Named') : SHORT_TYPE[s.approver_type])).join(' → ')}
    </span>
  );
}

const COLUMNS = [
  {
    key: 'name',
    header: 'Application',
    sortable: true,
    render: (a) => (
      <div>
        <p className="font-medium text-slate-900">{a.name}</p>
        <p className="max-w-xs truncate text-xs text-slate-500">{a.description || '—'}</p>
      </div>
    ),
  },
  { key: 'owner', header: 'Owner', sortable: true, sortValue: (a) => a.owner?.name, render: (a) => a.owner?.name },
  {
    key: 'levels',
    header: 'Access levels',
    sortable: true,
    sortValue: (a) => a.access_levels.length,
    render: (a) => a.access_levels.length,
  },
  { key: 'workflow', header: 'Approval chain', render: (a) => chainSummary(a.workflow_steps) },
  {
    key: 'is_active',
    header: 'Status',
    sortable: true,
    sortValue: (a) => (a.is_active ? 0 : 1),
    render: (a) => <StatusBadge status={a.is_active ? 'ACTIVE' : 'INACTIVE'} />,
  },
];

export default function ApplicationsAdminPage() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { user, hasRole } = useAuth();
  const isAdmin = hasRole('admin');
  const admin = useSelector(selectAdminApplications);
  const [query, setQuery] = useState('');
  const [includeInactive, setIncludeInactive] = useState(true);

  useEffect(() => {
    dispatch(fetchAdminApplications({ includeInactive: isAdmin && includeInactive }));
  }, [dispatch, isAdmin, includeInactive]);

  // App owners manage only the applications they own.
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return admin.items
      .filter((a) => isAdmin || a.owner?.id === user?.id)
      .filter((a) => !q || a.name.toLowerCase().includes(q));
  }, [admin.items, isAdmin, user, query]);

  return (
    <>
      <PageHeader
        title="Applications"
        description={isAdmin ? 'Every application, its access levels and approval workflow.' : 'Applications you own.'}
        actions={
          isAdmin ? (
            <ButtonLink to="/admin/applications/new">
              <PlusIcon className="h-4 w-4" />
              New application
            </ButtonLink>
          ) : null
        }
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <SearchIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <TextInput
            type="search"
            aria-label="Search applications"
            placeholder="Search applications"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        {isAdmin ? (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
            />
            Show inactive
          </label>
        ) : null}
      </div>
      {admin.error ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load applications">{admin.error.message}</ErrorAlert>
        </div>
      ) : null}
      <DataTable
        caption="Applications"
        columns={COLUMNS}
        rows={rows}
        loading={admin.status === 'loading' && admin.items.length === 0}
        onRowClick={(row) => navigate(`/admin/applications/${row.id}`)}
        empty={
          <EmptyState
            icon={GridIcon}
            title={query ? 'No applications match' : isAdmin ? 'No applications yet' : "You don't own any applications"}
            description={isAdmin && !query ? 'Create one to start taking access requests.' : undefined}
          />
        }
      />
    </>
  );
}
