import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useSearchParams } from 'react-router-dom';

import Button, { ButtonLink } from '../../components/Button';
import DataTable from '../../components/DataTable';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert, Select, TextInput } from '../../components/form';
import { ListIcon, PlusIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import { formatDate, relativeTime, statusLabel } from '../../utils/format';
import { fetchCatalog, selectCatalog } from '../applications/applicationsSlice';
import { fetchMyRequests, selectMyRequests } from './requestsSlice';

const STATUSES = ['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED'];
const FILTER_KEYS = ['status', 'application_id', 'from', 'to'];

const COLUMNS = [
  { key: 'id', header: 'ID', sortable: true, render: (r) => <span className="font-mono text-slate-500">#{r.id}</span> },
  {
    key: 'application',
    header: 'Application',
    sortable: true,
    sortValue: (r) => r.application.name,
    render: (r) => (
      <div>
        <p className="font-medium text-slate-900">{r.application.name}</p>
        <p className="text-xs text-slate-500">{r.access_level.name}</p>
      </div>
    ),
  },
  { key: 'status', header: 'Status', sortable: true, render: (r) => <StatusBadge status={r.status} /> },
  {
    key: 'progress',
    header: 'Progress',
    render: (r) =>
      r.status === 'PENDING' ? (
        <span className="text-slate-600">
          Step {r.current_step} of {r.total_steps}
        </span>
      ) : (
        <span className="text-slate-400">—</span>
      ),
  },
  {
    key: 'created_at',
    header: 'Submitted',
    sortable: true,
    render: (r) => <span title={formatDate(r.created_at)}>{relativeTime(r.created_at)}</span>,
  },
  {
    key: 'expires_at',
    header: 'Expires',
    sortable: true,
    render: (r) => (r.expires_at ? formatDate(r.expires_at) : <span className="text-slate-400">—</span>),
  },
];

export default function MyRequestsPage() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const list = useSelector(selectMyRequests);
  const catalog = useSelector(selectCatalog);

  const page = Number(searchParams.get('page') ?? 1);
  const filters = Object.fromEntries(FILTER_KEYS.map((key) => [key, searchParams.get(key) ?? '']));
  const filterKey = searchParams.toString();

  useEffect(() => {
    if (catalog.status === 'idle') dispatch(fetchCatalog());
  }, [dispatch, catalog.status]);

  useEffect(() => {
    dispatch(fetchMyRequests({ page, filters }));
    // filterKey captures every filter and the page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, filterKey]);

  function setParam(key, value) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setSearchParams(next);
  }

  const hasFilters = FILTER_KEYS.some((key) => filters[key]);

  return (
    <>
      <PageHeader
        title="My requests"
        description="Everything you've asked for, and where each request stands."
        actions={
          <ButtonLink to="/requests/new">
            <PlusIcon className="h-4 w-4" />
            New request
          </ButtonLink>
        }
      />

      <div className="mb-4 grid gap-3 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:grid-cols-2 lg:grid-cols-5">
        <Select aria-label="Status" value={filters.status} onChange={(e) => setParam('status', e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {statusLabel(status)}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Application"
          value={filters.application_id}
          onChange={(e) => setParam('application_id', e.target.value)}
        >
          <option value="">All applications</option>
          {catalog.items.map((app) => (
            <option key={app.id} value={app.id}>
              {app.name}
            </option>
          ))}
        </Select>
        <TextInput
          type="date"
          aria-label="Submitted from"
          value={filters.from}
          onChange={(e) => setParam('from', e.target.value)}
        />
        <TextInput type="date" aria-label="Submitted to" value={filters.to} onChange={(e) => setParam('to', e.target.value)} />
        <Button variant="ghost" onClick={() => setSearchParams({})} disabled={!hasFilters}>
          Clear filters
        </Button>
      </div>

      {list.error ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load your requests">{list.error.message}</ErrorAlert>
        </div>
      ) : null}

      <DataTable
        caption="My access requests"
        columns={COLUMNS}
        rows={list.items}
        loading={list.status === 'loading'}
        onRowClick={(row) => navigate(`/requests/${row.id}`)}
        pagination={{ page: list.page, perPage: list.perPage, total: list.total, onPageChange: (p) => setParam('page', String(p)) }}
        empty={
          <EmptyState
            icon={ListIcon}
            title={hasFilters ? 'No requests match these filters' : 'No requests yet'}
            description={hasFilters ? 'Try clearing the filters.' : 'Request access to an application to get started.'}
            action={
              hasFilters ? null : (
                <ButtonLink to="/requests/new">New request</ButtonLink>
              )
            }
          />
        }
      />
    </>
  );
}
