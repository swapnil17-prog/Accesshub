import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import * as auditApi from '../../api/audit';
import { toApiError } from '../../api/client';
import Button from '../../components/Button';
import DataTable from '../../components/DataTable';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert, Select, TextInput } from '../../components/form';
import { ChevronDownIcon, ChevronRightIcon, ShieldIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import { useToast } from '../../components/toastContext';
import UserPicker from '../../components/UserPicker';
import { saveBlob } from '../../utils/download';
import { formatDateTime } from '../../utils/format';
import { fetchAuditLogs, selectAuditLogs } from './auditSlice';
import { AUDIT_ACTIONS, ENTITY_TYPES } from './constants';
import JsonDiff from './JsonDiff';

const EMPTY_FILTERS = { actorMode: '', actor: null, action: '', entity_type: '', from: '', to: '' };

function toApiFilters(f) {
  return {
    actor: f.actorMode === 'system' ? 'system' : f.actorMode === 'user' && f.actor ? f.actor.id : undefined,
    action: f.action,
    entity_type: f.entity_type,
    from: f.from,
    to: f.to,
  };
}

function actionTone(action) {
  if (/FAILED|REJECTED|DEACTIVATED|DELETED/.test(action)) return 'bg-rose-50 text-rose-700 ring-rose-600/20';
  if (/APPROVED|CREATED|SUCCESS/.test(action)) return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
  if (/ESCALATED|EXPIRED|REMINDER/.test(action)) return 'bg-amber-50 text-amber-800 ring-amber-600/20';
  return 'bg-slate-100 text-slate-700 ring-slate-500/20';
}

const humanize = (value) => value.toLowerCase().replace(/_/g, ' ');

export default function AuditPage() {
  const dispatch = useDispatch();
  const toast = useToast();
  const logs = useSelector(selectAuditLogs);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState(() => new Set());
  const [exporting, setExporting] = useState(false);
  const apiFilters = toApiFilters(filters);
  const filterKey = JSON.stringify(apiFilters);

  useEffect(() => {
    dispatch(fetchAuditLogs({ page, filters: apiFilters }));
    setExpanded(new Set());
    // filterKey captures apiFilters' content
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, page, filterKey]);

  function change(patch) {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  }

  function toggle(id) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function exportCsv() {
    setExporting(true);
    try {
      const { blob, filename } = await auditApi.exportAuditCsv(apiFilters);
      saveBlob(blob, filename);
      toast.success(`Downloaded ${filename}.`);
    } catch (error) {
      toast.error(toApiError(error).message, 'Export failed');
    } finally {
      setExporting(false);
    }
  }

  const columns = [
    {
      key: 'expand',
      header: <span className="sr-only">Details</span>,
      className: 'w-10',
      render: (row) => (
        <button
          type="button"
          onClick={() => toggle(row.id)}
          aria-expanded={expanded.has(row.id)}
          aria-label={`${expanded.has(row.id) ? 'Hide' : 'Show'} changes for event ${row.id}`}
          className="rounded p-1 text-slate-500 hover:bg-slate-100"
        >
          {expanded.has(row.id) ? <ChevronDownIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
        </button>
      ),
    },
    {
      key: 'created_at',
      header: 'When',
      render: (row) => <span className="whitespace-nowrap">{formatDateTime(row.created_at)}</span>,
    },
    {
      key: 'actor',
      header: 'Actor',
      render: (row) =>
        row.actor ? (
          <div>
            <p className="text-slate-900">{row.actor.name}</p>
            <p className="text-xs text-slate-500">{row.actor.email}</p>
          </div>
        ) : (
          <span className="italic text-slate-500">System</span>
        ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (row) => (
        <span className={`whitespace-nowrap rounded px-1.5 py-0.5 font-mono text-xs ring-1 ring-inset ${actionTone(row.action)}`}>
          {row.action}
        </span>
      ),
    },
    {
      key: 'entity',
      header: 'Entity',
      render: (row) => (
        <span className="whitespace-nowrap text-slate-600">
          {humanize(row.entity_type)}
          {row.entity_id != null ? <span className="font-mono text-slate-400"> #{row.entity_id}</span> : null}
        </span>
      ),
    },
    { key: 'ip_address', header: 'IP', render: (row) => <span className="font-mono text-xs">{row.ip_address ?? '—'}</span> },
  ];

  const hasFilters = JSON.stringify(filters) !== JSON.stringify(EMPTY_FILTERS);

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every change and decision, newest first. Entries can never be edited or deleted."
        actions={
          <Button variant="secondary" onClick={exportCsv} loading={exporting}>
            Export CSV
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200 md:grid-cols-2 xl:grid-cols-6">
        <Select aria-label="Actor" value={filters.actorMode} onChange={(e) => change({ actorMode: e.target.value, actor: null })}>
          <option value="">Anyone</option>
          <option value="user">A specific person…</option>
          <option value="system">System (jobs)</option>
        </Select>
        {filters.actorMode === 'user' ? (
          <div className="xl:col-span-2">
            <UserPicker value={filters.actor} onChange={(actor) => change({ actor })} placeholder="Find a person" />
          </div>
        ) : null}
        <Select aria-label="Action" value={filters.action} onChange={(e) => change({ action: e.target.value })}>
          <option value="">All actions</option>
          {AUDIT_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
        <Select aria-label="Entity type" value={filters.entity_type} onChange={(e) => change({ entity_type: e.target.value })}>
          <option value="">All entities</option>
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}
            </option>
          ))}
        </Select>
        <TextInput type="date" aria-label="From" value={filters.from} onChange={(e) => change({ from: e.target.value })} />
        <TextInput type="date" aria-label="To" value={filters.to} onChange={(e) => change({ to: e.target.value })} />
        {hasFilters ? (
          <Button variant="ghost" onClick={() => change(EMPTY_FILTERS)}>
            Clear filters
          </Button>
        ) : null}
      </div>

      {logs.error ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load the audit log">{logs.error.message}</ErrorAlert>
        </div>
      ) : null}

      <DataTable
        caption="Audit log entries"
        columns={columns}
        rows={logs.items}
        loading={logs.status === 'loading'}
        isExpanded={(row) => expanded.has(row.id)}
        renderExpanded={(row) => (
          <div className="space-y-2">
            <JsonDiff oldValue={row.old_value} newValue={row.new_value} />
            {row.user_agent ? <p className="text-xs text-slate-500">User agent: {row.user_agent}</p> : null}
          </div>
        )}
        pagination={{ page: logs.page, perPage: logs.perPage, total: logs.total, onPageChange: setPage }}
        empty={<EmptyState icon={ShieldIcon} title="No audit entries match" description="Try widening the filters." />}
      />
    </>
  );
}
